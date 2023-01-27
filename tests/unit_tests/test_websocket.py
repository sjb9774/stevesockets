import unittest
from unittest.mock import Mock
from tests import utils
from stevesockets.websocket.websocket import WebSocketFrame, SocketBytesReader
from stevesockets.websocket.websocket import WebSocketFrameHeaders


class TestWebSocketFrame(unittest.TestCase):

    def _get_mock_bytes_reader(self, bytes_to_return=None, handshook=True) -> SocketBytesReader:
        conn = utils.get_mock_connection(returns=bytes_to_return, handshook=handshook)
        reader = SocketBytesReader(conn)
        return reader

    def test_webframe_from_bytes_non_fragmented(self):
        data = b'\x81\x89I\x96k\xa8\x1d\xd38\xfci\xd2*\xfc\x08'
        reader = self._get_mock_bytes_reader(bytes_to_return=data)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA")
        self.assertEqual(f.headers.payload_length, 9)
        self.assertEqual(f.headers.opcode, 1)
        self.assertEqual(f.headers.mask_flag, 1)
        # self.assertEqual(f.headers.mask, bits_value("01001001100101100110101110101000"))

    def test_webframe_to_bytes_non_fragmented_no_mask(self):
        f = WebSocketFrame(message="TEST DATA")
        bts = f.to_bytes()
        self.assertEqual(bts, b'\x81\tTEST DATA')

    def test_webframe_to_bytes_non_fragmented_with_mask(self):
        # generating a mask is usually random which is not good for testing
        WebSocketFrame.generate_mask = Mock(return_value=525161)
        f = WebSocketFrame(
            message="TEST DATA",
            headers=WebSocketFrameHeaders(mask=WebSocketFrame.generate_mask(), mask_flag=1)
        )
        self.assertEqual(f.to_bytes(), b'\x81\x89\x00\x08\x03iTMP= LB=A')

    def test_webframe_from_bytes_non_fragmented_no_mask(self):
        bstr = b'\x81\tTEST DATA'
        reader = self._get_mock_bytes_reader(bytes_to_return=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA")
        self.assertEqual(f.headers.payload_length, 9)
        self.assertIsNone(f.headers.mask)

    def test_webframe_from_bytes_non_fragmented_with_mask(self):
        bstr = b'\x81\x89\xb7\xfd}\x13\xe3\xb8.G\x97\xb9<G\xf6'
        reader = self._get_mock_bytes_reader(bytes_to_return=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.headers.mask, 327024055)
        self.assertEqual(f.headers.payload_length, 9)
        self.assertEqual(f.message, "TEST DATA")

    def test_webframe_from_bytes_fragmented_126_payload_no_mask(self):
        bstr = b'\x81~~\x00TEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATA'
        reader = self._get_mock_bytes_reader(bytes_to_return=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA" * 14)
        self.assertEqual(f.headers.payload_length, 126)
        self.assertIsNone(f.headers.mask)

    # def test_webframe_from_bytes_fragmented_127_payload_no_mask(self):
    #     bstr = b'\x81\x7f\x00\x00\x00\x00\x00\x00\x00\x87TEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATA'
    #     reader = self._get_mock_bytes_reader(bytes=bstr)
    #     f = WebSocketFrame.from_bytes_reader(reader)
    #     self.assertEqual(f.message, "TEST DATA" * 15)
    #     self.assertEqual(f.headers.payload_length, 135)
    #     self.assertIsNone(f.headers.mask)

    def test_webframe_premature_ending(self):
        bstr = b'\x819'
        reader = self._get_mock_bytes_reader(bytes_to_return=bstr)
        with self.assertRaises(StopIteration):
            WebSocketFrame.from_bytes_reader(reader)
