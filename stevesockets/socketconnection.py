import socket
import collections
import logging


class SocketConnection:

    def __init__(self, sck, address, port, logger=None):
        self.socket = sck
        self.address = address
        self.port = port
        self.handshook = False
        self.to_be_closed = False
        self.closed = False
        self.logger = logger if logger else logging.getLogger()
        self.messages = collections.deque()

    def close(self):
        self.logger.debug("Closing connection at {addr}:{port}".format(addr=self.address, port=self.port))
        self.socket.close()
        self.closed = True

    def read_data(self, size=4096):
        return self.socket.recv(size)

    def send_data(self, data):
        self.socket.sendall(data)

    def queue_message(self, message):
        self.messages.append(message)

    def clear_messages(self):
        self.messages.clear()

    def flush_messages(self):
        for x in range(len(self.messages)):
            msg = self.messages.popleft()
            try:
                self.socket.sendall(msg)
            except socket.error as err:
                self.logger.error("Socket error while sending message: {err}".format(err=err))

    def is_closed(self):
        return self.closed

    def mark_handshook(self):
        self.handshook = True

    def is_handshook(self):
        return self.handshook

    def mark_for_closing(self):
        self.to_be_closed = True

    def is_to_be_closed(self):
        return self.to_be_closed
