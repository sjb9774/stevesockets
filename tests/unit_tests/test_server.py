import unittest
from unittest.mock import Mock, MagicMock
from unittest import mock
import stevesockets.server
import socket


class TestSocketServer(unittest.TestCase):

    def setUp(self):
        stevesockets.server.socket = Mock()
        stevesockets.server.select = Mock(select=Mock(return_value=([Mock()], None, None)))
        stevesockets.server.threading = Mock()
        self.server = stevesockets.server.SocketServer()

    @mock.patch("stevesockets.server.socket")
    def test__create_socket(self, socket):
        self.server._create_socket()
        socket.socket.assert_called_once_with(stevesockets.server.socket.AF_INET, stevesockets.server.socket.SOCK_STREAM)
        self.server.socket.bind.assert_called_once_with(("127.0.0.1", 9000))

    def test_close_on_empty_message(self):
        empty_msg = b""
        conn = Mock()
        conn.socket.recv.return_value = empty_msg
        self.server.connection_handler(conn)
        conn.mark_for_closing.assert_called_once_with()

    def test_listen(self):
        self.server._create_socket = Mock()
        mock_conn = Mock()
        self.server.socket = Mock(accept=Mock(return_value=(mock_conn, ["TEST ADDRESS", 5555])))

        # listen just once or we'll never get out of the loop
        def fn(conn):
            self.assertTrue(self.server.listening)
            self.server.stop_listening()
            return "TEST"
        self.server.connection_handler = fn
        self.server.listen()
        self.assertFalse(self.server.listening)
        self.server._create_socket.assert_called_once_with()
        self.server.socket.close.assert_called_once_with()
        self.server.socket.accept()[0].close.assert_called_once_with()
        mock_conn.sendall.assert_called_once_with("TEST".encode())

    @mock.patch("stevesockets.server.threading")
    def test_dlisten(self, threading):
        threading.Thread = Mock(start=Mock())
        self.server.dlisten()
        threading.Thread.assert_called_once_with(target=self.server.listen)
        threading.Thread().start.assert_called_once_with()

    def test_connection_handler_with_resp(self):
        self.server.handle_message = Mock(return_value="TEST")
        connection_mock = Mock(socket=Mock(recv=Mock(return_value="MOCK BYTES")))
        resp = self.server.connection_handler(connection_mock)
        self.assertEqual(resp, "TEST")
        connection_mock.socket.recv.assert_called_once_with(4096)
        self.server.handle_message.assert_called_once_with(connection_mock, "MOCK BYTES")

    def test_connection_handler_without_resp(self):
        c = Mock()
        c.socket.recv = Mock(return_value=None)
        resp = self.server.connection_handler(c)
        self.assertIsNone(resp)

    def test_stop_listening(self):
        self.server._create_socket()
        self.server.dlisten()
        self.server.stop_listening()
        self.assertFalse(self.server.listening)

    def test_connection_removed_before_processing(self):

        def fn():
            self.server.stop_listening()
            return mock.DEFAULT  # so mock will return the return value we set >_>
        self.server._get_client_connection = Mock()
        self.server._get_client_connection.return_value = Mock()
        self.server._get_client_connection.return_value.is_to_be_closed = Mock(return_value=True)
        self.server._get_client_connection.return_value.is_to_be_closed.side_effect = fn

        stevesockets.server.select.select = Mock(return_value=[[Mock()], [], []])
        self.server._create_socket()
        self.server.socket.accept = Mock(return_value=(Mock(), ("TEST ADDRESS", 5555)))
        self.server.handle_connection = Mock()
        self.server.listen()

        self.server.handle_connection.assert_not_called()


class TestWebSocketServer(unittest.TestCase):

    def setUp(self):
        stevesockets.server.socket = Mock()
        stevesockets.server.select = Mock(select=Mock(return_value=([Mock()], None, None)))
        stevesockets.server.threading = Mock()
        self.server = stevesockets.server.WebSocketServer()

    def _mock_connection(self, returns=None, handshook=True):
        m = Mock()
        m.socket = Mock()
        m.socket.recv.return_value = returns
        m.handshook = handshook
        return m

    def test_handle_message_without_mask(self):
        msg = b'\x81\tTEST DATA'
        mock_connection = self._mock_connection(returns=msg)
        self.server.handle_message = lambda self, message: message
        resp = self.server.connection_handler(mock_connection)
        self.assertEqual(resp, b'\x81\tTEST DATA')

    def test_handle_message_with_mask(self):
        msg = b'\x81\x89\xc0\x9c}"\x94\xd9.v\xe0\xd8<v\x81'
        mock_connection = self._mock_connection(returns=msg)
        self.server.handle_message = lambda self, message: message
        resp = self.server.connection_handler(mock_connection)
        self.assertEqual(resp, b'\x81\tTEST DATA')

    def test_handle_handshake(self):
        client_handshake = bytes("GET / HTTP/1.1\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n", "utf-8")
        self.server.send_http_response = Mock()
        mock_conn = self._mock_connection()
        self.server.handle_websocket_handshake(mock_conn, client_handshake)
        self.server.send_http_response.assert_called_once_with(mock_conn, 101, headers={
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Accept": "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        })

    def test_connection_handler_ping(self):
        conn_mock = self._mock_connection(returns=b'\x89\x00')
        resp = self.server.connection_handler(conn_mock)
        self.assertEqual(resp, b'\x8a\x00') # messageless PONG response

    def test_connection_handler_pong(self):
        conn_mock = self._mock_connection(returns=b'\x8a\x00')
        resp = self.server.connection_handler(conn_mock)
        self.assertIsNone(resp)

    def test__close_connection(self):
        mock_connection = self._mock_connection()
        close_frame = b'\x88\x00'
        mock_connection.peek_message = Mock(return_value=close_frame)
        self.server.connection_handler = Mock()
        self.server._close_connection(mock_connection)
        mock_connection.peek_message.assert_called_once_with()
        mock_connection.queue_message.assert_not_called()

    def test_connection_close(self):
        conn_mock = self._mock_connection(returns=b'\x88\x00')
        conn_mock.is_to_be_closed = Mock(return_value=False)
        resp = self.server.connection_handler(conn_mock)
        conn_mock.is_to_be_closed.assert_called_once_with()
        conn_mock.mark_for_closing.assert_called_once_with()
        self.assertEqual(resp, b'\x88\x00')

    def test_connection_close_twice(self):
        conn_mock = self._mock_connection(returns=b'\x88\x00')
        conn_mock.is_to_be_closed.return_value = False
        resp = self.server.connection_handler(conn_mock)
        conn_mock.mark_for_closing.assert_called_once_with()

        conn_mock.is_to_be_closed.return_value = True
        resp2 = self.server.connection_handler(conn_mock)
        self.assertEqual(conn_mock.is_to_be_closed.call_count, 2)
        self.assertIsNone(resp2)

    def test_connection_handler_fragmented_message_no_mask(self):
        self._test_connection_handler_fragmented_message(b'\x01\x11partial message 1',
                                                         b'\x01\x11partial message 2',
                                                         b'\x81\rfinal message',
                                                         "partial message 1",
                                                         "partial message 2",
                                                         "final message")

    def test_connection_handler_fragmented_message_with_mask(self):
        self._test_connection_handler_fragmented_message(b'\x01\x91\xfcT\x81\xb0\x8c5\xf3\xc4\x955\xed\x90\x911\xf2\xc3\x9d3\xe4\x90\xcd',
                                                         b'\x01\x91\x95\xc9\xbf\xb6\xe5\xa8\xcd\xc2\xfc\xa8\xd3\x96\xf8\xac\xcc\xc5\xf4\xae\xda\x96\xa7',
                                                         b'\x81\x8d\xfa\xa2\x9d\xa4\x9c\xcb\xf3\xc5\x96\x82\xf0\xc1\x89\xd1\xfc\xc3\x9f',
                                                         "partial message 1",
                                                         "partial message 2",
                                                         "final message")

    def _test_connection_handler_fragmented_message(self, msg1, msg2, msg3, text1, text2, text3):
        mock_connection = self._mock_connection(returns=msg1)
        r1 = self.server.connection_handler(mock_connection)
        self.assertIsNone(r1)
        mock_connection.socket.recv = Mock(return_value=msg2)
        r2 = self.server.connection_handler(mock_connection)
        self.assertIsNone(r2)
        mock_connection.socket.recv = Mock(return_value=msg3)
        self.server.handle_message = Mock(return_value="TEST")
        r3 = self.server.connection_handler(mock_connection)
        self.server.handle_message.assert_called_once_with(mock_connection, text1+text2+text3)
        self.assertEqual(r3, b'\x81\x04TEST')
