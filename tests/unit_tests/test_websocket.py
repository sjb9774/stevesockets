import unittest
from unittest.mock import Mock
from tests import utils
from stevesockets.websocket import WebSocketFrame, bits_value, to_binary, SocketException, SocketBytesReader
from stevesockets.websocket import WebSocketFrameHeaders


class TestBitsFunctions(unittest.TestCase):

    def test_to_binary_valid_input(self):
        num = 201
        bstr = to_binary(num)
        self.assertEqual(bstr, "11001001")

    def test_to_binary_neg_input(self):
        with self.assertRaises(ValueError):
            to_binary(-100)

    def test_to_binary_neg_pad_to(self):
        with self.assertRaises(ValueError):
            to_binary(100, pad_to=-1)

    def test_to_binary_pad_to(self):
        result = to_binary(205, pad_to=10)
        self.assertEqual(result, "0011001101")

    def test_to_binary_invalid_input(self):
        inputs = [None, False, "test", ["t", "e", "s", "t"], {"t": "e", "s": "t"}]
        for i in inputs:
            with self.subTest(i=i):
                with self.assertRaises(ValueError):
                    to_binary(i)

    def test_to_binary_pad_to_smaller_than_input(self):
        result = to_binary(205, pad_to=5)
        self.assertEqual(result, "11001101")

    def test_bits_value_valid_input(self):
        v = bits_value("10010100")
        self.assertEqual(148, v)

    def test_bits_value_invalid_bits(self):
        inputs = ["102332", "0000kkksm", "hello world", "1100 1"]
        for i in inputs:
            with self.subTest(i=i):
                with self.assertRaises(ValueError):
                    bits_value(i)

    def test_bits_value_invalid_input(self):
        with self.assertRaises(ValueError):
            bits_value(10010110)


class TestWebSocketFrame(unittest.TestCase):

    def _get_mock_bytes_reader(self, bytes=None, handshook=True):
        conn = utils.get_mock_connection(returns=bytes, handshook=handshook)
        reader = SocketBytesReader(conn)
        return reader

    def test_webframe_from_bytes_non_fragmented(self):
        data = b'\x81\x89I\x96k\xa8\x1d\xd38\xfci\xd2*\xfc\x08'
        reader = self._get_mock_bytes_reader(bytes=data)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA")
        self.assertEqual(f.headers.payload_length, 9)
        self.assertEqual(f.headers.opcode, 1)
        self.assertEqual(f.headers.mask_flag, 1)
        self.assertEqual(f.headers.mask, bits_value("01001001100101100110101110101000"))

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
        reader = self._get_mock_bytes_reader(bytes=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA")
        self.assertEqual(f.headers.payload_length, 9)
        self.assertIsNone(f.headers.mask)

    def test_webframe_from_bytes_non_fragmented_with_mask(self):
        bstr = b'\x81\x89\x13}\xfd\xb7G8\xae\xe339\xbc\xe3R'
        reader = self._get_mock_bytes_reader(bytes=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.headers.mask, 327024055)
        self.assertEqual(f.headers.payload_length, 9)
        self.assertEqual(f.message, "TEST DATA")

    def test_webframe_from_bytes_fragmented_126_payload_no_mask(self):
        bstr = b'\x81~\x00~TEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATA'
        reader = self._get_mock_bytes_reader(bytes=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA" * 14)
        self.assertEqual(f.headers.payload_length, 126)
        self.assertIsNone(f.headers.mask)

    def test_webframe_from_bytes_fragmented_127_payload_no_mask(self):
        bstr = b'\x81\x7f\x00\x00\x00\x00\x00\x00\x00\x87TEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATATEST DATA'
        reader = self._get_mock_bytes_reader(bytes=bstr)
        f = WebSocketFrame.from_bytes_reader(reader)
        self.assertEqual(f.message, "TEST DATA" * 15)
        self.assertEqual(f.headers.payload_length, 135)
        self.assertIsNone(f.headers.    mask)

    def test_webframe_premature_ending(self):
        bstr = b'\x819'
        reader = self._get_mock_bytes_reader(bytes=bstr)
        with self.assertRaises(StopIteration):
            WebSocketFrame.from_bytes_reader(reader)
