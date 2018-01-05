from Tkinter import *
from ttk import *
import socket
import thread
import json
import time
import datetime

from client import *

class Server:
    def __init__(self, blockchain, onstatus):
        self.onstatus = onstatus

        self.blockchain = blockchain
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
        print "connect %s:%s" % client_address

        self.clients["%s:%s" % client_address] = client_socket
        thread.start_new_thread(self.handle_client_messages, (client_socket, client_address))
        self.onstatus("Server is running ({} active connections)".format(len(self.clients)))

    def remove_client(self, client_socket, client_address):
        print "disconnect %s:%s" % client_address
        del self.clients["%s:%s" % client_address]
        self.onstatus("Server is running ({} active connections)".format(len(self.clients)))

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

    def respond_to_command(self, client_socket, obj):
        msg_type = obj["type"]

        print "msg_type = {}".format(msg_type)

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

            client_socket.send(json.dumps({
                'type': 'retrievelatestblock',
                'block': self.blockchain.latestblock().serialize_obj()
            }))
        elif msg_type == 'fetchblocks':
            if obj['blockidgt'] is None:
                raise InvalidMessage(obj)

            client_socket.send(json.dumps({
                'type': 'retrieveblocks',
                'blocks': [block.serialize_obj() for block in self.blockchain.blocks if block.blockid > obj['blockidgt']]
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


class P2PServer(Frame):
    def __init__(self, root):
        Frame.__init__(self, root)
        self.root = root


        self.client = Client({
            'onconnect': self._onselfconnect,
            'ondisconnect': self._onselfdisconnect,
            'onfailure': self._onselffailure,
            'onstatus': self.client_status,
            'onerror': self.client_error
        }) # so it can connect to other servers as a client
    
        self.server = Server(blockchain=self.client.blockchain, onstatus=self.server_status)

    def _onselfconnect(self):
        self.client_status("Connected to server successfully")
        self.connect_to_server_button.config(text="Disconnect", command=self.disconnect_from_server)
    
    def _onselfdisconnect(self):
        self.client_status("Client not connected")
        self.connect_to_server_button.config(text="Connect", command=self.connect_to_server, state=NORMAL)
    
    def _onselffailure(self, e):
        self.client_status("Failed to connect to server: {}".format(e))

    def show(self):
        self.root.title("P2P Server")

        parent_frame = Frame(self.root)
        parent_frame.grid(padx=10, pady=10, sticky=E+W+N+S)

        self._create_start_server_frame(parent_frame)
        self._create_connect_to_server_frame(parent_frame)
        self._create_log_frame(parent_frame)

    def _create_start_server_frame(self, parent_frame):
        server_info_frame = Frame(parent_frame)

        server_info_label = Label(server_info_frame, text="Run Server")
        server_info_label.grid(row=0, column=0)

        self.address_var = StringVar()
        self.address_var.set("127.0.0.1")

        address_label = Label(server_info_frame, text="Address:")
        address_label.grid(row=1, column=0)

        self.address_field = Entry(server_info_frame, width=15, textvariable=self.address_var)
        self.address_field.grid(row=1, column=1)

        self.port_var = StringVar()
        self.port_var.set("8090")

        port_label = Label(server_info_frame, text="Port:")
        port_label.grid(row=1, column=2, padx=5)

        self.port_field = Entry(server_info_frame, width=5, textvariable=self.port_var)
        self.port_field.grid(row=1, column=3)

        self.start_server_button = Button(server_info_frame, text="Start Server", command=self.start_server)
        self.start_server_button.grid(row=1, column=4, padx=(5, 0))

        bottom_frame = Frame(server_info_frame)

        self.server_status_label = Label(bottom_frame, text="Server not running")
        self.server_status_label.grid(row=2, column=0, sticky=W)

        bottom_frame.grid(row=2, column=0, sticky=E+W+S, pady=(5, 0))

        server_info_frame.grid(row=0, column=0, sticky=W+E)

    def _create_connect_to_server_frame(self, parent_frame):
        connect_to_server_frame = Frame(parent_frame)

        connect_to_server_label = Label(connect_to_server_frame, text="Connect to Server")
        connect_to_server_label.grid(row=0, column=0)

        self.connect_address_var = StringVar()
        self.connect_address_var.set("127.0.0.1")

        address_label = Label(connect_to_server_frame, text="Address:")
        address_label.grid(row=1, column=0)

        self.connect_address_field = Entry(connect_to_server_frame, width=15, textvariable=self.connect_address_var)
        self.connect_address_field.grid(row=1, column=1)

        self.connect_port_var = StringVar()
        self.connect_port_var.set("8090")

        port_label = Label(connect_to_server_frame, text="Port:")
        port_label.grid(row=1, column=2, padx=5)

        self.connect_port_field = Entry(connect_to_server_frame, width=5, textvariable=self.connect_port_var)
        self.connect_port_field.grid(row=1, column=3)

        self.connect_to_server_button = Button(connect_to_server_frame, text="Connect", command=self.connect_to_server)
        self.connect_to_server_button.grid(row=1, column=4, sticky=E+W, padx=(5, 0))
        
        bottom_frame = Frame(connect_to_server_frame)

        self.client_status_label = Label(bottom_frame, text="Client not connected")
        self.client_status_label.grid(row=2, column=0, sticky=W)

        bottom_frame.grid(row=2, column=0, sticky=E+W+S, pady=(5, 0))

        connect_to_server_frame.grid(row=1, column=0, sticky=W+E)

    def _create_log_frame(self, parent_frame):
        log_frame = Frame(parent_frame)

        self.text_area = Text(log_frame, height=15)
        self.text_area.grid(row=1, column=1, sticky=N+E+W+S)

        log_frame.grid(row=3, column=0, sticky=W+E+N+S)

    def log(self, message):
        self.text_area.insert(END, "\n{}: {}".format(str(datetime.datetime.now()), message))

    def connect_to_server(self):
        self.client.connect(self.connect_address_var.get().replace(' ', ''), int(self.connect_port_var.get().replace(' ', '')))

    def disconnect_from_server(self):
        self.client.disconnect()
        self.client_status('Disconnecting from server...')
        self.connect_to_server_button.config(state=DISABLED)

    def start_server(self):
        self.server.start(self.address_var.get().replace(' ', ''), int(self.port_var.get().replace(' ', '')))
        self.start_server_button.config(text="Stop Server", command=self.stop_server)

    def stop_server(self):
        self.server.stop()
        self.start_server_button.config(text="Start Server", command=self.start_server)

    def _status(self, status_label, msg, timeout=None):
        status_label.config(text=msg)
        self.log(msg)

        if not timeout is None:
           thread.start_new_thread(lambda: time.sleep(timeout) or self._status(status_label, ""), ())

    def server_status(self, msg, timeout=None):
        self._status(self.server_status_label, msg, timeout)

    def client_status(self, msg, timeout=None):
        self._status(self.client_status_label, msg, timeout)

    def client_error(self, msg, timeout=None):
        self._status(self.client_status_label, '*** ERROR ***: {}'.format(msg), timeout)


def main():
    root = Tk()

    p2p_server = P2PServer(root)
    p2p_server.show()

    root.mainloop()

if __name__ == '__main__':
    main()