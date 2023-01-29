#!/usr/bin/env python3

import sys
from stevesockets.http.server import HttpServer
import logging
import argparse
from stevesockets.socketconnection import SocketConnection
from stevesockets.http import LOGGER_NAME
from stevesockets.messages import MessageTypes
from stevesockets.listeners import TextListener


class CustomListener(TextListener):

    def observe(self, message: bytes, *args, connection: SocketConnection = None, server=None, **kwargs):
        print(f"Observing incoming HTTP message {message.decode('utf-8')}")
        content = bytes("HTTP/1.1 200 OK\r\n\r\n<!doctype html><html><body><h1>Hello world</h1></body></html>", "utf-8")
        connection.queue_message(content)
        connection.mark_for_closing()


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

    s = HttpServer(logger=logger)
    s.register_listener(CustomListener, message_type=MessageTypes.DEFAULT)

    print(f"Listening at http://127.0.0.1:{parser_args.port}")


    s.listen()
