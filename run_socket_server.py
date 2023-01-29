#!/usr/bin/env python3

import sys
from stevesockets.server import SocketServer, SocketConnection
import logging
import argparse
from stevesockets import LOGGER_NAME
from stevesockets.listeners import TextListener


class CustomListener(TextListener):

    def observe(self, message: bytes, *args, connection: SocketConnection = None, server: SocketServer = None, **kwargs):
        message = f"SteveSockets SocketServer has received your message of '{message.decode('utf-8').strip()}'\n"
        connection.queue_message(bytes(message, "utf-8"))


if __name__ == "__main__":
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s [%(filename)s:%(lineno)5s %(name)s:%(funcName)20s() ] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", action="store", default=9000, type=int)
    parser_args = parser.parse_args()

    s = SocketServer(logger=logger)

    s.register_listener(CustomListener)

    s.listen()
