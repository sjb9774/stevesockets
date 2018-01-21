from logging import getLogger as get_logger

logger = get_logger(__name__)


def bits_value(bits):
    if type(bits) != str:
        raise ValueError("Input should be a bit string")
    p = len(bits) - 1
    total = 0
    for i, bit in enumerate(bits):
        if bit not in ("1", "0"):
            raise ValueError("Invalid bit string")
        total += int(bit) * (2**(p-i))
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

import select
import random


class WebSocketFrame:

    OPCODE_CLOSE    = 8
    OPCODE_PING     = 9
    OPCODE_PONG     = 10

    def __init__(self, fin=1, opcode=1, rsv=0, mask=None, message=""):
        self.fin = fin
        self.opcode = opcode
        self.mask_flag = 1 if mask else 0
        self.mask = mask
        self.message = message
        self.payload_length = len(message)
        self.rsv = rsv

    def to_bytes(self):
        full_bit_str = ""
        full_bit_str += to_binary(self.fin, pad_to=1)
        full_bit_str += to_binary(self.rsv, pad_to=3)
        full_bit_str += to_binary(self.opcode, pad_to=4)
        full_bit_str += to_binary(self.mask_flag, pad_to=1)
        if self.payload_length <= 125:
            full_bit_str += to_binary(self.payload_length, pad_to=7)
        elif self.payload_length == 126:
            full_bit_str += to_binary(126, pad_to=7)
            full_bit_str += to_binary(self.payload_length, pad_to=16)
        elif self.payload_length > 126:
            full_bit_str += to_binary(127, pad_to=7)
            full_bit_str += to_binary(self.payload_length, pad_to=64)
        if bool(self.mask_flag):
            mask_bits = to_binary(self.mask, pad_to=32)
            full_bit_str += mask_bits
            mask_values = [bits_value(mask_bits[x:x+8]) for x in range(0, len(mask_bits), 8)]
            masked_message = []
            for i, char in enumerate(self.message):
                masked_message.append(ord(char) ^ mask_values[i % 4])
            full_bit_str += "".join(to_binary(x, pad_to=8) for x in masked_message)
        else:
            msg = [to_binary(x, pad_to=8) for x in (ord(y) for y in self.message)]
            full_bit_str += "".join(msg)
        split_to_bytes = [bits_value(full_bit_str[x:x+8]) for x in range(0, len(full_bit_str), 8)]
        return bytes(split_to_bytes)

    @staticmethod
    def generate_mask():
        return random.randint(0, (2 ** 32) - 1)

    @classmethod
    def from_bytes(cls, in_bytes):
        full_bit_str = "".join([to_binary(byte, pad_to=8) for byte in in_bytes])
        bit_generator = (bit for bit in full_bit_str)
        get_next_bits = lambda x: "".join(next(bit_generator) for i in range(x))

        fin = bits_value(get_next_bits(1))
        rsv = bits_value(get_next_bits(3)) # can be safely ignored
        opcode = bits_value(get_next_bits(4))
        mask_flag = bits_value(get_next_bits(1))
        bits_9_15_val = bits_value(get_next_bits(7))
        if bits_9_15_val <= 125:
            payload_length = bits_9_15_val
        elif bits_9_15_val == 126:
            payload_length = bits_value(get_next_bits(16))
        elif bits_9_15_val == 127:
            payload_length = bits_value(get_next_bits(64))

        mask = get_next_bits(32) if bool(mask_flag) else None
        message = ""
        for x in range(payload_length):
            char_data = get_next_bits(8)
            if bool(mask_flag):
                char = chr(bits_value(char_data) ^ bits_value(mask[(x % 4) * 8:((x % 4) * 8) + 8]))
            else:
                char = chr(bits_value(char_data))
            message += char
        f = cls(fin=fin, opcode=opcode, rsv=rsv, mask=bits_value(mask) if mask else None, message=message)
        return f
