import unittest
from unittest.mock import Mock, MagicMock
from unittest import mock
from tests import utils
import stevesockets.server


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

    @mock.patch("stevesockets.server.threading")
    def test_dlisten(self, threading):
        threading.Thread = Mock(start=Mock())
        self.server.dlisten()
        threading.Thread.assert_called_once_with(target=self.server.listen)
        threading.Thread().start.assert_called_once_with()

    def test_connection_handler_with_resp(self):
        def handle(request_msg, send_msg):
            self.assertEqual(request_msg, "MOCK BYTES")
            send_msg("TEST", close_after=False)
            self.server.stop_listening()
            return "TEST"

        self.server.handle_message = Mock(return_value="TEST", side_effect=lambda: self.server.stop_listening())
        self.server.handle_message = handle

        self.server.on_message = Mock()
        connection_mock = Mock(socket=Mock(recv=Mock(return_value="MOCK BYTES")))
        self.server.peer_connections = [connection_mock]
        self.server._build_peer_connections = Mock()
        self.server.prune_peer_connections = Mock()
        self.server.listen()
        connection_mock.socket.recv.assert_called_once_with(4096)
        self.server.on_message.assert_called_once_with(connection_mock, "TEST")

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
