import thread
import socket
import json
import time
from functools import reduce

from block import *
from chain import *

class InvalidMessage(Exception):
    def __init__(self, msg):
        self.msg = "Invalid message: {}".format(msg)

class Client:
    def __init__(self, tx_chain, tx_cnf_chain, blk_chain, blk_cnf_chain, handlers):
        self.handlers = handlers

        self.socket = None
        self.peers = []
        self.is_connected = False

        self.tx_chain = tx_chain
        self.tx_cnf_chain = tx_cnf_chain
        self.blk_chain = blk_chain
        self.blk_cnf_chain = blk_cnf_chain

    def connect(self, server_address, server_port):
        assert not self.is_connected
        thread.start_new_thread(self._connect, (server_address, server_port))

    def _connect(self, server_address, server_port):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(3)
            self.socket.connect((server_address, server_port))
            self.is_connected = True

            thread.start_new_thread(self.listen_for_server_messages, ())
            thread.start_new_thread(self.periodically_resync_with_peers, ())
            thread.start_new_thread(self.check_for_blocks_to_mine, (self.tx_chain, self.tx_cnf_chain))

            self.handlers['onconnect']()
        except Exception as e:
            self.handlers['onfailure'](e)


    def disconnect(self):
        assert self.is_connected
        assert not self.socket is None

        self.socket.close()
        self.is_connected = False

        for bc in [self.tx_chain, self.tx_cnf_chain, self.blk_chain, self.blk_cnf_chain]:
            bc.remote_diff = 0

        #if self.is_connected:
        #    thread.start_new_thread(self.periodically_resync_with_peers, ())

    def _getblockchain(self, msg):
        assert type(msg) == dict

        if msg['bc'] is None:
            raise InvalidMessage('bc not specified')

        if msg['bc'] == 'tx':
            return self.tx_chain
        elif msg['bc'] == 'tx_cnf':
            return self.tx_cnf_chain
        elif msg['bc'] == 'blk':
            return self.blk_chain
        elif msg['bc'] == 'blk_cnf':
            return self.blk_cnf_chain
        else:
            raise InvalidMessage('not a valid blockchain type')

    def check_for_blocks_to_mine(self, bc, cnf_bc):
        my_id = 'TEST'
        while self.is_connected:
            self.handlers['onstatus']("checking for blocks in '{}' chain to validate...".format(bc.key))

            for block in bc.blocks:
                if not block.isgenesis():
                    cnf_blocks = filter(lambda x: x.data['linkedblock'] == block.blockid, cnf_bc.blocks)

                    if len(cnf_blocks) < 6:
                        self.handlers['onstatus']("block {} requires {} more confirmations".format(block.blockid, 6 - len(cnf_blocks)))

                        can_mine_block = True

                        for cnf in cnf_blocks:
                            if cnf.data['validator'] == my_id:
                                can_mine_block = False
                                break

                        if can_mine_block:
                            self.handlers['onstatus']("mining block {}...".format(block.blockid))

                            self._confirmblock(bc, block)
                        else:
                            self.handlers['onstatus']("block {} already mined".format(block.blockid))

            time.sleep(30)

    def respond_to_message(self, obj):
        msg_type = obj["type"]

        if msg_type is None:
            raise InvalidMessage(obj)

        if msg_type == "pong":
            pass
        elif msg_type == "updatepeers":
            self._updatepeers(obj["peers"])
        elif msg_type == 'retrievelatestblock':
            # retrieve latest block after running latestblock to node
            if obj['block'] is not None:
                if obj['bc'] == 'blk':
                    remote_blk = Block.deserialize_obj(obj['block'])
                elif obj['bc'] == 'tx':
                    remote_blk = Transaction.deserialize_obj(obj['block'])
                elif obj['bc'].endswith('_cnf'):
                    remote_blk = Confirmation.deserialize_obj(obj['block'])

                bc = self._getblockchain(obj)
                bc.remote_diff = remote_blk.blockid - (bc.latestblock().blockid if len(bc.blocks) != 0 else 0)

                if bc.remote_diff != 0:
                    if bc.remote_diff > 0:
                        self.handlers['onstatus']('Local out of date with remote by {} blocks.'.format(bc.remote_diff))
                        self._fetchremoteblocks(bc)
                    else:
                        self.handlers['onstatus']('Local ahead of remote by {} blocks.'.format(-1 * bc.remote_diff))
                        #todo

        elif msg_type == 'retrieveblocks':
            assert obj['blocks'] is not None, "obj['blocks'] should not be None"
            assert isinstance(obj['blocks'], list), "obj['blocks'] should be of type `list`"
            assert len(obj['blocks']) > 0, "len(obj['blocks']) should be > 0"

            # validate each block
            bc = self._getblockchain(obj)
            prevblockid = bc.latestblock().blockid if len(bc.blocks) != 0 else 0

            for block in obj['blocks']:
                assert isinstance(block, dict), "block should be of type `dict`"

                if prevblockid is not None:
                    assert block['parent'] == prevblockid, "block['parent'] should be equal to previous block id ({})".format(prevblockid)
    
                prevblockid = block['blockid']

            for block in obj['blocks']:
                blk = None

                if obj['bc'] == 'tx':
                    blk = Transaction.deserialize_obj(block)
                elif obj['bc'] == 'blk':
                    blk = Block.deserialize_obj(block)
                elif obj['bc'].endswith('_cnf'):
                    blk = Confirmation.deserialize_obj(block)

                self._onnewremoteblock(bc, blk)

            bc.remote_diff = 0
            self.handlers['onstatus']('Local and remote are now in sync.')
            #self.handlers['onstatus']('Syncing clients...')

    def _onnewremoteblock(self, bc, blk):
        assert blk is not None

        # write block
        blk.savelocal(bc)
        bc.blocks.append(blk)

    def _confirmblock(self, bc, blk):
        self.handlers['onstatus']('Confirming block #{} for {} chain...'.format(blk.blockid, bc.key))

        # TODO move this to a more efficient way of calculating balance.
        total_balance, unconfirmed_balance = self._calcbalance(blk.data['sender'])

        value = blk.data['amt']
        assert isinstance(value, int), "block amt should be int"

        last_cnf = self.tx_cnf_chain.latestblock() if len(self.tx_cnf_chain.blocks) > 0 else None
        last_cnf_id = last_cnf.blockid if last_cnf is not None else -1

        if total_balance >= blk.data['amt']:
            cnf_blk = Confirmation(last_cnf_id + 1, datetime.datetime.now(), blk.blockid, 'TEST', 'SUCCESS', last_cnf_id)
            self.handlers['onstatus']('Confirming block #{} confirmed for {} chain'.format(blk.blockid, bc.key))
        else:
            cnf_blk = Confirmation(last_cnf_id + 1, datetime.datetime.now(), blk.blockid, 'TEST', 'FAILURE', last_cnf_id)
            self.handlers['onstatus']('Confirming block #{} confirmation marked FAILED for {} chain'.format(blk.blockid, bc.key))

        self.tx_cnf_chain.blocks.append(cnf_blk)
        cnf_blk.savelocal(self.tx_cnf_chain)


    def _calcbalance(self, acct):
        # TODO verify ONLY confirmed txs
        total_balance = 0
        unconfirmed_balance = 0

        txs = filter(lambda x: (x.data['sender'] == acct or x.data['receiver'] == acct), self.tx_chain.blocks)
        for blk in txs:
            blk_confirmations = filter(lambda x: x.data['linkedblock'] == blk.blockid and x.data['result'] == 'SUCCESS', self.tx_cnf_chain.blocks)

            block_bal = 0

            if blk.data['receiver'] == acct:
                block_bal += blk.data['amt']

            elif blk.data['sender'] == acct:
                block_bal -= blk.data['amt']

            if len(blk_confirmations) >= 6 or blk.isgenesis():
                total_balance += block_bal

            unconfirmed_balance += block_bal

        return (total_balance, unconfirmed_balance)

    def listen_for_server_messages(self):
        thread.start_new_thread(self.heartbeat, ())

        while 1:
            if not self.is_connected:
                return

            try:
                data = self.socket.recv(1024)

                if not data:
                    break

                obj = None

                try:
                    obj = json.loads(data)
                except:
                    raise InvalidMessage(data)

                self.respond_to_message(obj)

            except InvalidMessage as e:
                self.handlers['onstatus'](str(e))
                continue

            except Exception as e:
                print("Error while listening for server messages: {}".format(e))
                break

        if self.is_connected:
            self.disconnect()

        self.handlers['ondisconnect']()

    def heartbeat(self):
        while self.is_connected:
            self.socket.send(json.dumps({
                'type': 'ping'
            }))

            time.sleep(1)

    def periodically_resync_with_peers(self):
        while self.is_connected:
            for bc, bcname in [(self.blk_chain, 'model'), (self.blk_cnf_chain, 'model_confirmations'), (self.tx_chain, 'transaction'), (self.tx_cnf_chain, 'transaction_confirmations')]:                
                if not self.is_connected:
                    return

                if bc.remote_diff == 0:
                    self.handlers['onstatus']("Checking sync state for '{}' blockchain...".format(bcname))

                    if bc.local_blocks_loaded:
                        self.request_latest_block(bc)
                    else:
                        self.handlers['onstatus']("Awaiting local blocks for '{}' blockchain...".format(bcname))
                else:
                   self.handlers['onstatus']("Awaiting local blocks for '{}' blockchain...".format(bcname))

                if not self.is_connected:
                    return

                time.sleep(5)

    # request the latest transaction from the connected node
    # this is done periodically to make sure we are in sync
    def request_latest_block(self, blockchain):
        assert self.is_connected

        self.socket.send(json.dumps({
            'type': 'latestblock',
            'bc': blockchain.key
        }))

    def _updatepeers(self, peerlist):
        self.peers = peerlist

    # fetch $(blockchain.remote_diff) blocks from the node
    def _fetchremoteblocks(self, blockchain):
        self.socket.send(json.dumps({
            'type': 'fetchblocks',
            'blockidgt': blockchain.latestblock().blockid if len(blockchain.blocks) != 0 else -1,
            'bc': blockchain.key
        }))

