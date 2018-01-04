import thread
import socket
import json
import time

class InvalidMessage(Exception):
    def __init__(self, msg):
        self.msg = "Invalid message: {}".format(msg)

class Client:
    def __init__(self, handlers):
        self.handlers = handlers

        self.socket = None
        self.peers = []
        self.is_connected = False

    def connect(self, server_address, server_port):
        assert not self.is_connected
        thread.start_new_thread(self._connect, (server_address, server_port))

    def _connect(self, server_address, server_port):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(2)
            self.socket.connect((server_address, server_port))

            thread.start_new_thread(self.listen_for_server_messages, ())

            self.is_connected = True

            self.handlers['onconnect']()
        except Exception as e:
            self.handlers['onfailure'](e)


    def disconnect(self):
        assert self.is_connected
        assert not self.socket is None

        self.socket.close()
        self.is_connected = False

    def respond_to_message(self, obj):
        msg_type = obj["type"]

        if msg_type is None:
            raise InvalidMessage(obj)

        if msg_type == "pong":
            pass
        elif msg_type == "updatepeers":
            self._updatepeers(obj["peers"])

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
            print "ping"
            self.socket.send(json.dumps({
                'type': 'ping'
            }))

            time.sleep(1)
            

    # request the latest transaction from the connected node
    # this is done periodically to make sure we are in sync
    def request_latest_transaction(self):
        self.socket.send('latestblock')

    def _updatepeers(self, peerlist):
        self.peers = peerlist
