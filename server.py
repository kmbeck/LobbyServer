import random
import string
import sys
import time
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor


class ServerProtocol(DatagramProtocol):

	def __init__(self):
		self.active_sessions = {}
		self.registered_clients = {}

	def name_is_registered(self, name):
		return name in self.registered_clients

	def create_session(self, client_list):
		"""Create a new Session and return it's unique ID."""
		s_id = self.gen_session_uid()
		while s_id in self.active_sessions:
			s_id = self.gen_session_uid()
		self.active_sessions[s_id] = Session(s_id, client_list, self)
		return s_id

	def remove_session(self, s_id):
		try:
			del self.active_sessions[s_id]
		except KeyError:
			print("Tried to terminate non-existing session")

	def register_client(self, c_name, c_session_uid, c_ip, c_local_ip, c_port):
		if self.name_is_registered(c_name):
			print("Client %s is already registered." % [c_name])
			return
		if not c_session_uid in self.active_sessions:
			print("Client registered for non-existing session %s" % [c_session_uid])
		else:
			new_client = Client(c_name, c_session_uid, c_ip, c_local_ip, c_port)
			self.registered_clients[c_name] = new_client
			self.active_sessions[c_session_uid].client_registered(new_client)

	def exchange_info(self, c_session):
		if not c_session_uid in self.active_sessions:
			return
		self.active_sessions[c_session_uid].exchange_peer_info()

	def client_checkout(self, name):
		try:
			del self.registered_clients[name]
		except KeyError:
			print("Tried to checkout unregistered client")

	def datagramReceived(self, datagram, address):
		"""Handle incoming datagram messages."""
		data_string = datagram.decode("utf-8")
		print(data_string)
		msg_type = data_string[:2]

		if msg_type == "rs":
			# register session
			c_ip, c_port = address
			split = data_string.split(":")
			max_clients = split[1]
			s_id = self.create_session(max_clients)	 # Create new Session & returns unique id (join code) of new session.
			self.transport.write(bytes('ok:'+str(c_port) + ":" + c_ip + ":" + s_id ,"utf-8"), address)

		elif msg_type == "rc":
			# register client
			split = data_string.split(":")
			c_name = split[1]
			c_local_ip = split[2]
			c_session_uid = split[3]
			c_ip, c_port = address
			self.transport.write(bytes('ok:'+str(c_port) + ':' + c_ip,"utf-8"), address)
			self.register_client(c_name, c_session_uid, c_ip, c_local_ip, c_port)

		elif msg_type == "ep":
			# exchange peers
			split = data_string.split(":")
			c_session = split[1]
			self.exchange_info(c_session)

		elif msg_type == "cc":
			# checkout client
			split = data_string.split(":")
			c_name = split[1]
			self.client_checkout(c_name)

		elif msg_type == "hb":
			# recieved hearbeat from a host client.
			split = data_string.split(":")
			c_session_uid = split[1]
			self.active_sessions[c_session_uid].last_hb_time = time.time()
			print(f"updated hb time for session: {c_session_uid} ({self.active_sessions[c_session_uid].last_hb_time})")

	# Generate a unique ID for a new Session. This is also the join code.
	def gen_session_uid(self):
		characters = string.ascii_lowercase + string.digits  # a-z, A-Z, 0-9
		session_uid = ''.join(random.choices(characters, k=5))
		return session_uid

class Session:

	def __init__(self, session_id, max_clients, server):
		self.id = session_id
		self.client_max = max_clients
		self.server = server
		self.last_hb_time = time.time()
		self.registered_clients = []

	def client_registered(self, client):
		if client in self.registered_clients: return
		print(f"Client {client.name} registered for Session {self.id}")
		self.registered_clients.append(client)
		if len(self.registered_clients) > 1:
			time.sleep(5)
			self.exchange_peer_info()
		# if len(self.registered_clients) == int(self.client_max):
		# 	sleep(5)
		# 	print("waited for OK message to send, sending out info to peers")
		# 	self.exchange_peer_info()

	def exchange_peer_info(self):
		for addressed_client in self.registered_clients:
			address_list = []
			for client in self.registered_clients:
				if not client.name == addressed_client.name:
					address_list.append(':'.join([client.name,client.ip,client.local_ip,str(client.port)]))
			address_string = ",".join(address_list)
			message = bytes( "peers:" + address_string, "utf-8")
			print(message)
			self.server.transport.write(message, (addressed_client.ip, addressed_client.port))

		print("Updated peer info has been sent.")
		# for client in self.registered_clients:
		# 	self.server.client_checkout(client.name)
		# self.server.remove_session(self.id)


class Client:

	def confirmation_received(self):
		self.received_peer_info = True

	def __init__(self, c_name, c_session, c_ip, c_local_ip, c_port):
		self.name = c_name
		self.session_id = c_session
		self.ip = c_ip				# Public IP
		self.local_ip = c_local_ip	# LAN IP
		self.port = c_port
		self.received_peer_info = False

if __name__ == '__main__':
	if len(sys.argv) < 2:
		print("Usage: ./server.py PORT")
		sys.exit(1)

	port = int(sys.argv[1])
	reactor.listenUDP(port, ServerProtocol())
	print('Listening on *:%d' % (port))
	reactor.run()
