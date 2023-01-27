import enum


class MessageTypes(enum.Enum):
	DEFAULT = "__default"
	TEXT = 1
	BINARY = 2

	CLOSE = 8
	PING = 9
	PONG = 10


class MessageManager:

	default_message_type = MessageTypes.DEFAULT

	def __init__(self):
		self.message_listeners = {}

	def listen_for_message(self, listener, message_type: MessageTypes = MessageTypes.DEFAULT):
		self.message_listeners.setdefault(message_type, [])
		self.message_listeners[message_type].append(listener)

	def dispatch_message(self, message, *args, message_type: MessageTypes = MessageTypes.DEFAULT, **kwargs):
		if message_type not in self.message_listeners.keys():
			return

		for listener in self.message_listeners[message_type]:
			listener.observe(message, *args, **kwargs)


class Listener:

	def __init__(self, fn=None):
		self.fn = fn

	def observe(self, message, *args, **kwargs):
		if self.fn:
			self.fn(message, *args, **kwargs)
