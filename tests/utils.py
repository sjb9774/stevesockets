from unittest.mock import Mock
from stevesockets.server import WebSocketConnection


def get_mock_connection(returns=None, handshook=True, to_be_closed=False, closed=False):
	ws = WebSocketConnection(Mock())
	ws.is_to_be_closed = Mock(return_value=to_be_closed)
	ws.is_closed = Mock(return_value=closed)
	return_value_generator = (returns[i:i + 1] for i in range(len(returns))) if returns else (x for x in [None])

	def mock_recv(n):
		bytes_value = b''
		for x in range(n):
			bytes_value += next(return_value_generator)
		return bytes(bytes_value)

	ws.socket.recv = mock_recv
	ws.handshook = handshook
	return ws

