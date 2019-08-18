from logging import getLogger
import random

logger = getLogger(__name__)


def bits_value(bits):
    if type(bits) != str:
        raise ValueError("Input should be a bit string")
    p = len(bits) - 1
    total = 0
    for i, bit in enumerate(bits):
        if bit not in ("1", "0"):
            raise ValueError("Invalid bit string")
        total += int(bit) * (2 ** (p - i))
    return total


def to_binary(n, pad_to=None):
    if type(n) != int:
        raise ValueError("Input should be an integer")
    if n < 0:
        raise ValueError("Input should be a positive number")
    if pad_to and pad_to < 0:
        raise ValueError("Can't pad to a length less than 0")
    r = n
    s = ""
    while r > 0:
        s += str(r % 2)
        r = r // 2
    result = s[-1::-1]
    if pad_to and len(result) < pad_to:
        while len(result) < pad_to:
            result = "0" + result
    return result


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

    def get_unmasked_message(self):
        message = ''
        binary_mask = str(to_binary(self.headers.mask, pad_to=32))
        for x in range(self.headers.payload_length):
            char_data = self.message[x:x+1]
            char = chr(bits_value(char_data) ^ bits_value(binary_mask[(x % 4) * 8:((x % 4) * 8) + 8]))
            message += char
        return message

    def to_bytes(self):
        full_bit_str = ""
        full_bit_str += to_binary(self.headers.fin, pad_to=1)
        full_bit_str += to_binary(self.headers.rsv, pad_to=3)
        full_bit_str += to_binary(self.headers.opcode, pad_to=4)
        full_bit_str += to_binary(self.headers.mask_flag, pad_to=1)
        if self.headers.payload_length <= 125:
            full_bit_str += to_binary(self.headers.payload_length, pad_to=7)
        elif (self.headers.payload_length > 125) and (self.headers.payload_length < 2 ** 16):
            full_bit_str += to_binary(126, pad_to=7)
            full_bit_str += to_binary(self.headers.payload_length, pad_to=16)
        elif self.headers.payload_length >= 2 ** 16:
            full_bit_str += to_binary(127, pad_to=7)
            full_bit_str += to_binary(self.headers.payload_length, pad_to=64)
        if bool(self.headers.mask_flag):
            mask_bits = to_binary(self.headers.mask, pad_to=32)
            full_bit_str += mask_bits
            mask_values = [bits_value(mask_bits[x:x + 8]) for x in range(0, len(mask_bits), 8)]
            masked_message = []
            for i, char in enumerate(self.message):
                masked_message.append(ord(char) ^ mask_values[i % 4])
            full_bit_str += "".join(to_binary(x, pad_to=8) for x in masked_message)
        else:
            msg = [to_binary(x, pad_to=8) for x in (ord(y) for y in self.message)]
            full_bit_str += "".join(msg)
        split_to_bytes = [bits_value(full_bit_str[x:x + 8]) for x in range(0, len(full_bit_str), 8)]
        return bytes(split_to_bytes)

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
        headers = WebSocketFrameHeaders(opcode=cls.OPCODE_CLOSE, payload_length=len(message.message) if message else 0)
        return WebSocketFrame(headers=headers, message=message)

    @classmethod
    def get_pong_frame(cls, message=None):
        headers = WebSocketFrameHeaders(opcode=cls.OPCODE_PONG, payload_length=len(message.message) if message else 0)
        return WebSocketFrame(headers=headers, message=message.message)

    @classmethod
    def from_bytes_reader(cls, bytes_reader):
        headers = WebSocketFrameHeaders.from_bytes(bytes_reader)
        
        message = ""
        for x in range(headers.payload_length):
            char_data = bytes_reader.get_next_bytes(1)
            if bool(headers.mask_flag):
                binary_mask = str(to_binary(headers.mask, pad_to=32))
                char = chr(bits_value(char_data) ^ bits_value(binary_mask[(x % 4) * 8:((x % 4) * 8) + 8]))
            else:
                char = chr(bits_value(char_data))
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
        byte_str = bytes_reader.get_next_bytes(2)
        if len(byte_str) < 16:
            raise SocketException('Bytes reader yielded insufficient bytes to build headers')

        fin = bits_value(byte_str[0])
        rsv = bits_value(byte_str[1:4])  # can be safely ignored
        opcode = bits_value(byte_str[4:8])
        mask_flag = bits_value(byte_str[8])
        bits_9_15_val = bits_value(byte_str[9:])

        payload_length = None
        if bits_9_15_val <= 125:
            payload_length = bits_9_15_val
        elif bits_9_15_val == 126:
            payload_length = bits_value(bytes_reader.get_next_bytes(2))
        elif bits_9_15_val == 127:
            payload_length = bits_value(bytes_reader.get_next_bytes(8))

        mask = bytes_reader.get_next_bytes(4) if bool(mask_flag) else None

        return cls(fin=fin,
                   opcode=opcode,
                   rsv=rsv,
                   mask_flag=mask_flag,
                   mask=bits_value(mask) if mask else None,
                   payload_length=payload_length)


class SocketException(Exception):
    pass


class SocketBytesReader:

    def __init__(self, connection):
        self.connection = connection

    def get_next_bytes(self, n):
        return "".join([to_binary(byte, pad_to=8) for byte in self.connection.socket.recv(n)])
