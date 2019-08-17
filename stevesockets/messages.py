class MessageManager:

	default_message_type = "__default"

	def __init__(self, default_message_type=None):
		self.message_listeners = {}
		if default_message_type:
			self.default_message_type = default_message_type

	def listen_for_message(self, listener, message_type=default_message_type):
		self.message_listeners.setdefault(message_type, [])
		self.message_listeners[message_type].append(listener)

	def dispatch_message(self, message, *args, message_type=default_message_type, **kwargs):
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
