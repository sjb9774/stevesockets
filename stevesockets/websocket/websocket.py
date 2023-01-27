from __future__ import annotations
from logging import getLogger
import random
import math

logger = getLogger(__name__)


def bytes_to_int(bytes_in):
    return int.from_bytes(bytes_in, 'little')


def int_to_bytes(int_in, num_bytes=None):
    # use the submitted amount or calculate the minimum possible
    num_bytes = num_bytes if num_bytes is not None else math.ceil(math.log(int_in, 2))
    return int.to_bytes(int_in, num_bytes, 'little')


class SocketBytesReader:

    def __init__(self, connection):
        self.connection = connection

    def get_next_bytes(self, n) -> bytes:
        try:
            return self.connection.socket.recv(n)
        except StopIteration:
            return b''


class WebSocketFrame:
    OPCODE_CONTINUATION = 0
    OPCODE_TEXT = 1
    OPCODE_BINARY = 2

    OPCODE_CLOSE = 8
    OPCODE_PING = 9
    OPCODE_PONG = 10
    MAX_BUFFER_SIZE = 4096

    def __init__(self, headers=None, message=None):
        self.headers = headers if headers else WebSocketFrameHeaders()
        self.message = None
        self.set_message(message)

    def set_message(self, message):
        self.message = message
        self.headers.payload_length = len(self.message) if self.message else 0

    def to_bytes(self):
        byte_1 = 0
        byte_1 += self.headers.fin << 7
        byte_1 += self.headers.rsv << 4
        byte_1 += self.headers.opcode
        compiled_bytes = int_to_bytes(byte_1, 1)

        byte_2 = self.headers.mask_flag << 7
        payload_length_bytes = 0
        payload_length_byte_count = 0
        if self.headers.payload_length <= 125:
            byte_2 += self.headers.payload_length
        elif (self.headers.payload_length > 125) and (self.headers.payload_length < 2 ** 16):
            payload_length_byte_count = 2
            byte_2 += 126
            payload_length_bytes += self.headers.payload_length
        elif self.headers.payload_length >= 2 ** 16:
            payload_length_byte_count = 8
            byte_2 += 127
            payload_length_bytes += self.headers.payload_length

        compiled_bytes += int_to_bytes(byte_2, 1)
        compiled_bytes += int_to_bytes(payload_length_bytes, payload_length_byte_count)

        if bool(self.headers.mask_flag):
            mask = self.headers.mask
            compiled_bytes += int_to_bytes(mask, 4)
            for x, char in enumerate(self.message):
                mask_index = x % 4
                shift_distance = 8 * mask_index
                mask_byte = mask & (255 << shift_distance)  # shift 11111111 and bitwise-AND to get the right mask byte
                mask_byte >>= shift_distance  # shift the mask byte back so its value is the correct magnitude
                masked_char = ord(char) ^ mask_byte
                compiled_bytes += int_to_bytes(masked_char, 1)
        elif self.message:
            for char in self.message:
                compiled_bytes += int_to_bytes(ord(char), 1)
        return compiled_bytes

    def encode(self):
        # alias for to_bytes
        return self.to_bytes()

    @staticmethod
    def generate_mask():
        return random.randint(0, (2 ** 32) - 1)

    @classmethod
    def get_text_frame(cls, message):
        headers = WebSocketFrameHeaders(payload_length=len(message))
        frame = WebSocketFrame(headers=headers, message=message)
        return frame

    @classmethod
    def get_close_frame(cls, message=None):
        headers = WebSocketFrameHeaders(opcode=cls.OPCODE_CLOSE, payload_length=len(message) if message else 0)
        return WebSocketFrame(headers=headers, message=message)

    @classmethod
    def get_pong_frame(cls, message=None):
        headers = WebSocketFrameHeaders(opcode=cls.OPCODE_PONG, payload_length=len(message) if message else 0)
        return WebSocketFrame(headers=headers, message=message)

    @classmethod
    def from_bytes_reader(cls, bytes_reader: SocketBytesReader) -> WebSocketFrame:
        headers = WebSocketFrameHeaders.from_bytes(bytes_reader)

        message = ""
        mask = headers.mask
        for x in range(headers.payload_length):
            char_data = bytes_to_int(bytes_reader.get_next_bytes(1))
            if bool(headers.mask_flag):
                # unmasking cycles through each of the four bytes of the mask, bitwise-XOR'ing with the masked character
                # byte to get the unmasked character
                mask_index = x % 4
                shift_distance = 8 * mask_index
                mask_byte = mask & (255 << shift_distance)  # shift 11111111 and bitwise-AND to get the right mask byte
                mask_byte >>= shift_distance  # shift the mask byte back so its value is the correct magnitude
                char = chr(char_data ^ mask_byte)
            else:
                char = chr(char_data)
            message += char

        return cls(headers=headers, message=message)

    @classmethod
    def read_from_connection(cls, connection):
        reader = SocketBytesReader(connection)
        return cls.from_bytes_reader(reader)


class WebSocketFrameHeaders:

    def __init__(self, fin=1, opcode=1, rsv=0, mask_flag=0, mask=None, payload_length=0):
        self.fin = fin
        self.opcode = opcode
        self.mask_flag = mask_flag
        self.mask = mask
        self.payload_length = payload_length
        self.rsv = rsv

    @classmethod
    def from_bytes(cls, bytes_reader):
        message_bytes = bytes_reader.get_next_bytes(2)
        if len(message_bytes) != 2:
            raise SocketException('Bytes reader yielded insufficient bytes to build headers')

        byte_1, byte_2 = message_bytes
        fin = byte_1 >> 7
        rsv = byte_1 & 112  # 01110000
        opcode = byte_1 & 15  # 00001111
        mask_flag = byte_2 >> 7
        bits_9_15_val = byte_2 & 127  # 01111111

        payload_length = None
        if bits_9_15_val <= 125:
            payload_length = bits_9_15_val
        elif bits_9_15_val == 126:
            # next two bytes as a single value
            payload_length = bytes_to_int(bytes_reader.get_next_bytes(2))
        elif bits_9_15_val == 127:
            # next eight bytes as a single value
            next_8 = bytes_reader.get_next_bytes(8)
            payload_length = bytes_to_int(next_8)

        mask = None
        if bool(mask_flag):
            # next four bytes as a single value
            mask = bytes_to_int(bytes_reader.get_next_bytes(4))

        return cls(fin=fin,
                   opcode=opcode,
                   rsv=rsv,
                   mask_flag=mask_flag,
                   mask=mask if mask else None,
                   payload_length=payload_length)


class SocketException(Exception):
    pass


