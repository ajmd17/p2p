from Tkinter import *
from ttk import *
import socket
import thread
import json
import time

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
      self.socket.connect((server_address, server_port))

      thread.start_new_thread(self.listen_for_server_messages, ())

      self.is_connected = True

      self.handlers['onconnect']()
    except Exception as e:
      print("Failed to connect to server: %s" % e.message)
      self.handlers['onfailure']()


  def disconnect(self):
    assert self.is_connected
    assert not self.socket is None

    self.socket.close()
    self.is_connected = False

    self.handlers['ondisconnect']()

  def listen_for_server_messages(self):
    while 1:
      try:
        data = self.socket.recv(1024)

        if not data:
          break

        print("Received message from server: {}".format(data))

      except:
        break

    self.disconnect()


class P2PClient(Frame):
  def __init__(self, root):
    Frame.__init__(self, root)
    self.root = root

    self.client = Client({
      'onconnect': self._onconnect,
      'ondisconnect': self._ondisconnect,
      'onfailure': self._onfailure
    })
    self.setup_ui()

  def setup_ui(self):
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
    port_label.grid(row=0, column=2)

    self.port_field = Entry(server_info_frame, width=5, textvariable=self.port_var)
    self.port_field.grid(row=0, column=3)

    server_info_frame.grid(row=0, column=0)

    bottom_frame = Frame(parent_frame)

    self.connect_button = Button(bottom_frame, text="Connect to Server", command=self.connect_to_server)
    self.connect_button.grid(row=0, column=0, sticky=E+W)

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

  def _onfailure(self):
    self.connect_button.config(text="Connect to Server", command=self.connect_to_server)
    self.status("Failed to connect to server.")

  def status(self, msg, timeout=None):
    self.status_label.config(text=msg)

    if not timeout is None:
      thread.start_new_thread(lambda: time.sleep(timeout) or self.status(""), ())

def main():
  root = Tk()
  p2p_client = P2PClient(root)
  root.mainloop()

if __name__ == '__main__':
  main()