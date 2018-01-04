from Tkinter import *
from ttk import *
import socket
import thread
import json
import time

from client import *

class P2PClient(Frame):
    def __init__(self, root):
        Frame.__init__(self, root)
        self.root = root

        self.client = Client({
            'onconnect': self._onconnect,
            'ondisconnect': self._ondisconnect,
            'onfailure': self._onfailure,
            'onstatus': self.status
        })

    def show(self):
        self.root.title("P2P Client")

        parent_frame = Frame(self.root)
        parent_frame.grid(padx=10, pady=10, sticky=E+W+N+S)

        server_info_frame = Frame(parent_frame)

        self.address_var = StringVar()
        self.address_var.set("127.0.0.1")

        address_label = Label(server_info_frame, text="Address:")
        address_label.grid(row=0, column=0)

        self.address_field = Entry(server_info_frame, width=15, textvariable=self.address_var)
        self.address_field.grid(row=0, column=1)

        self.port_var = StringVar()
        self.port_var.set("8090")

        port_label = Label(server_info_frame, text="Port:")
        port_label.grid(row=0, column=2, padx=5)

        self.port_field = Entry(server_info_frame, width=5, textvariable=self.port_var)
        self.port_field.grid(row=0, column=3)

        self.connect_button = Button(server_info_frame, text="Connect to Server", command=self.connect_to_server)
        self.connect_button.grid(row=0, column=4, sticky=E+W, padx=(5, 0))

        server_info_frame.grid(row=0, column=0)

        bottom_frame = Frame(parent_frame)

        self.status_label = Label(bottom_frame)
        self.status_label.grid(row=1, column=0, sticky=W)

        bottom_frame.grid(row=1, column=0, sticky=E+W+S, pady=(5, 0))

    def connect_to_server(self):
        self.status("Connecting...")

        self.client.connect(self.address_var.get().replace(' ', ''), int(self.port_var.get().replace(' ', '')))

    def disconnect_from_server(self):
        self.client.disconnect()

    def _onconnect(self):
        self.connect_button.config(text="Disconnect from Server", command=self.disconnect_from_server)
        self.status("Connected to server.")

    def _ondisconnect(self):
        self.connect_button.config(text="Connect to Server", command=self.connect_to_server)
        self.status("Disconnected from server.")

    def _onfailure(self, e):
        self.connect_button.config(text="Connect to Server", command=self.connect_to_server)
        self.status("Failed to connect to server: {}".format(e))

    def status(self, msg, timeout=None):
        self.status_label.config(text=msg)

        if not timeout is None:
            thread.start_new_thread(lambda: time.sleep(timeout) or self.status(""), ())

def main():
    root = Tk()

    p2p_client = P2PClient(root)
    p2p_client.show()

    root.mainloop()

if __name__ == '__main__':
    main()