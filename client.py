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
    def __init__(self, handlers):
        self.handlers = handlers

        self.socket = None
        self.peers = []
        self.is_connected = False
        self.local_blocks_loaded = False
        self.blockchain_remote_diff = 0

        self.blockchain = Chain()
        self.blockchain.loadlocal(handlers={
            'onstatus': handlers['onstatus'],
            'onerror': handlers['onerror'],
            'oncomplete': self._onlocalblockscomplete
        })

    def connect(self, server_address, server_port):
        assert not self.is_connected
        thread.start_new_thread(self._connect, (server_address, server_port))

    def _connect(self, server_address, server_port):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(2)
            self.socket.connect((server_address, server_port))

            thread.start_new_thread(self.listen_for_server_messages, ())
            thread.start_new_thread(self.periodically_resync_with_peers, ())

            self.is_connected = True

            self.handlers['onconnect']()
        except Exception as e:
            self.handlers['onfailure'](e)


    def disconnect(self):
        assert self.is_connected
        assert not self.socket is None

        self.socket.close()
        self.is_connected = False
        self.blockchain_remote_diff = 0

    def _onlocalblockscomplete(self):
        self.local_blocks_loaded = True

        #if self.is_connected:
        #    thread.start_new_thread(self.periodically_resync_with_peers, ())

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
            assert obj['block'] is not None

            remote_blk = Block.deserialize_obj(obj['block'])

            self.handlers['onstatus']('remote: {}, local: {}'.format(remote_blk.serialize_json(), self.blockchain.latestblock().serialize_json()))

            self.blockchain_remote_diff = remote_blk.blockid - self.blockchain.latestblock().blockid

            if self.blockchain_remote_diff == 0:
                self.handlers['onstatus']('Local and remote are in sync.')
            else:
                if self.blockchain_remote_diff > 0:
                    self.handlers['onstatus']('Local out of date with remote by {} blocks.'.format(self.blockchain_remote_diff))
                    self._fetchremoteblocks()
                else:
                    self.handlers['onstatus']('Local ahead of remote by {} blocks.'.format(-1 * self.blockchain_remote_diff))
                    #todo

        elif msg_type == 'retrieveblocks':
            assert obj['blocks'] is not None
            assert isinstance(obj['blocks'], list)
            assert len(obj['blocks']) > 0

            # validate each block
            prevblockid = self.blockchain.latestblock().blockid

            for block in obj['blocks']:
                assert isinstance(block, dict)
                assert block['parent'] == prevblockid
                prevblockid = block['blockid']

            for block in obj['blocks']:
                blk = Block.deserialize_obj(block)
                # write block
                blk.savelocal()
                self.blockchain.blocks.append(blk)

            self.blockchain_remote_diff = 0
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
            if self.blockchain_remote_diff == 0:
                self.handlers['onstatus']("Checking sync state...")

                if self.local_blocks_loaded:
                    self.request_latest_block()
                else:
                    self.handlers['onstatus']('Awaiting local blocks...')
            else:
                # still awaiting a current sync...
                self.handlers['onstatus']('Awaiting local blocks...')

            time.sleep(5)

    # request the latest transaction from the connected node
    # this is done periodically to make sure we are in sync
    def request_latest_block(self):
        assert self.is_connected

        self.socket.send(json.dumps({
            'type': 'latestblock'
        }))

    def _updatepeers(self, peerlist):
        self.peers = peerlist

    # fetch $(self.blockchain_remote_diff) blocks from the node
    def _fetchremoteblocks(self):
        self.socket.send(json.dumps({
            'type': 'fetchblocks',
            'blockidgt': self.blockchain.latestblock().blockid
        }))

