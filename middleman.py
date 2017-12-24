from Tkinter import *
from ttk import *
import socket
import thread
import json

class Server:
  def __init__(self, onstatus):
    self.onstatus = onstatus

    self.socket = None
    self.clients = []
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
    except Exception as e:
      self.onstatus("Failed to start server: %s" % (e))

  def stop(self):
    assert self.is_running
    assert not self.socket is None

    self.socket.close()
    self.is_running = False

  def add_client(self, client_socket, client_address):
    self.onstatus("Client connected: {}:{}".format(*client_address))

    self.clients.append(client_socket)
    client_socket.send("welcome")
    thread.start_new_thread(self.handle_client_messages, (client_socket, client_address))

  def remove_client(self, client_socket, client_address):
    self.pnstatus("Client disconnected: {}:{}".format(*client_address))

    self.clients.remove(client_socket)

  def listen_for_connections(self):
    while 1:
      client_socket, client_address = self.socket.accept()
      self.add_client(client_socket, client_address)

    self.socket.close()

  def handle_client_messages(self, client_socket, client_address):
    while 1:
      try:
        data = client_socket.recv(1024)

        if not data:
          break

        if data == "listclients":
          client_socket.send(json.dumps(self.clients))

      except:
        break
    
    self.remove_client(client_socket, client_address)
    client_socket.close()


class P2PServer(Frame):
  def __init__(self, root):
    Frame.__init__(self, root)
    self.root = root

    self.server = Server(onstatus=self.status)
    self.setup_ui()

  def setup_ui(self):
    self.root.title("P2P Server")

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

    self.start_server_button = Button(bottom_frame, text="Start Server", command=self.start_server)
    self.start_server_button.grid(row=0, column=0, sticky=E+W)

    self.status_label = Label(bottom_frame)
    self.status_label.grid(row=1, column=0, sticky=W)

    bottom_frame.grid(row=1, column=0, sticky=E+W+S, pady=(5, 0))

  def start_server(self):
    self.server.start(self.address_var.get().replace(' ', ''), int(self.port_var.get().replace(' ', '')))
    self.start_server_button.config(text="Stop Server", command=self.stop_server)

  def stop_server(self):
    self.server.stop()
    self.start_server_button.config(text="Start Server", command=self.start_server)

  def status(self, msg, timeout=None):
    self.status_label.config(text=msg)

    if not timeout is None:
      thread.start_new_thread(lambda: time.sleep(timeout) or self.status(""), ())


def main():
  root = Tk()
  p2p_server = P2PServer(root)
  root.mainloop()

if __name__ == '__main__':
  main()