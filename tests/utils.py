from unittest.mock import Mock


def get_mock_connection(returns=None, handshook=True):
	m = Mock()
	m.socket = Mock()
	return_value_generator = (returns[i:i + 1] for i in range(len(returns))) if returns else (x for x in [None])

	def mock_recv(n):
		bytes_value = b''
		for x in range(n):
			bytes_value += next(return_value_generator)
		return bytes(bytes_value)

	m.socket.recv = mock_recv
	m.handshook = handshook
	return m

