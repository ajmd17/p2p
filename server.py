import socket
import thread
import json
import time
import datetime

from chain import *

class Server:
    def __init__(self, tx_chain, blk_chain, cnf_chain, onstatus):
        self.onstatus = onstatus

        self.tx_chain = tx_chain
        self.blk_chain = blk_chain
        self.cnf_chain = cnf_chain

        self.socket = None
        self.clients = {}
        self.is_running = False

    def start(self, address, port):
        assert not self.is_running

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((address, port))
            self.socket.listen(5)

            thread.start_new_thread(self.listen_for_connections, ())

            self.is_running = True

            self.onstatus("Server is running")
        except Exception as e:
            self.onstatus("Failed to start server; Consider restarting the application. The error message was: {}".format(e))

    def stop(self):
        assert self.is_running
        assert not self.socket is None

        self.socket.close()
        self.is_running = False
        self.clients = {}
        self.peers = []
        
        self.onstatus("Server not running")

    def add_client(self, client_socket, client_address):
        assert self.is_running

        self.clients["%s:%s" % client_address] = client_socket
        thread.start_new_thread(self.handle_client_messages, (client_socket, client_address))
        # self.onstatus("Server is running ({} active connections)".format(len(self.clients)))

    def remove_client(self, client_socket, client_address):
        del self.clients["%s:%s" % client_address]
        # self.onstatus("Server is running ({} active connections)".format(len(self.clients)))

    def listen_for_connections(self):
        while self.is_running:
            try:
                client_socket, client_address = self.socket.accept()
                client_socket.settimeout(2)
                self.add_client(client_socket, client_address)
            except:
                break
        
        if self.is_running:
            self.stop()

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

    def respond_to_command(self, client_socket, obj):
        msg_type = obj["type"]

        if msg_type is None:
            raise InvalidMessage(obj)

        if msg_type == 'ping':
            client_socket.send(json.dumps({
                'type': 'pong'
            }))
        elif msg_type == "listclients":
            client_socket.send(json.dumps(self.clients))
        elif msg_type == 'latestblock':
            # latest block was requested from a child node,
            # so we make sure we are in sync first, and if we are, send it along.
            # if not, we resync first.
            #self._checksync()
            bc = self._getblockchain(obj)

            client_socket.send(json.dumps({
                'type': 'retrievelatestblock',
                'block': bc.latestblock().serialize_obj() if len(bc.blocks) != 0 else None,
                'bc': bc.key
            }))
        elif msg_type == 'fetchblocks':
            if obj['blockidgt'] is None:
                raise InvalidMessage(obj)

            bc = self._getblockchain(obj)

            client_socket.send(json.dumps({
                'type': 'retrieveblocks',
                'blocks': [block.serialize_obj() for block in bc.blocks if block.blockid > obj['blockidgt']],
                'bc': bc.key
            }))
        elif msg_type == "broadcast":
            if obj["msg"] is None:
                raise InvalidMessage(obj)

            self.socket.sendall(obj["msg"])

    def handle_client_messages(self, client_socket, client_address):
        while self.is_running:
            try:
                data = client_socket.recv(1024)

                if (not data) or len(data) == 0:
                    break

                obj = None

                try:
                    obj = json.loads(data)
                except:
                    raise InvalidMessage(data)

                self.respond_to_command(client_socket, obj)

            except InvalidMessage, e:
                self.onstatus(str(e))
                continue

            except Exception, e:
                break

        self.remove_client(client_socket, client_address)

    def _checksync(self):
        self.onstatus("Updating sync state...")

        for peer in self.peers:
            pass
