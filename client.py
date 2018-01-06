import thread
import socket
import json
import time

from block import *
from chain import *

class InvalidMessage(Exception):
    def __init__(self, msg):
        self.msg = "Invalid message: {}".format(msg)

class Client:
    def __init__(self, tx_chain, blk_chain, cnf_chain, handlers):
        self.handlers = handlers

        self.socket = None
        self.peers = []
        self.is_connected = False

        self.tx_chain = tx_chain
        self.blk_chain = blk_chain
        self.cnf_chain = cnf_chain

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


            self.handlers['onconnect']()
        except Exception as e:
            self.handlers['onfailure'](e)


    def disconnect(self):
        assert self.is_connected
        assert not self.socket is None

        self.socket.close()
        self.is_connected = False

        for bc in [self.tx_chain, self.cnf_chain, self.blk_chain]:
            bc.remote_diff = 0

        #if self.is_connected:
        #    thread.start_new_thread(self.periodically_resync_with_peers, ())

    def _getblockchain(self, msg):
        assert type(msg) == dict

        if msg['bc'] is None:
            raise InvalidMessage('bc not specified')

        if msg['bc'] == 'tx':
            return self.tx_chain
        elif msg['bc'] == 'blk':
            return self.blk_chain
        elif msg['bc'] == 'cnf':
            return self.cnf_chain
        else:
            raise InvalidMessage('not a valid blockchain type')

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

                assert blk is not None

                # write block
                blk.savelocal()
                bc.blocks.append(blk)

            bc.remote_diff = 0
            self.handlers['onstatus']('Local and remote are now in sync.')
            #self.handlers['onstatus']('Syncing clients...')

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
            for bc, bcname in [(self.blk_chain, 'model'), (self.cnf_chain, 'confirmation'), (self.tx_chain, 'transaction')]:                
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

