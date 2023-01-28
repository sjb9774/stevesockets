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

    def observe(self, message, *args, connection: SocketConnection = None, server=None, **kwargs):
        print(f"Observing incoming HTTP message {message}")
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


    # @s.message_handler
    # def my_business_function(request_message: bytes, send_message: callable):
    #     content = bytes("<!doctype html><html><body><h1>Hello world</h1></body></html>", "utf-8")
    #     msg = bytes(f"HTTP/1.1 200 OK\r\n", 'utf-8')
    #     msg2 = bytes(f"content-type: text/html\r\n\r\n", "utf-8")
    #     msg3 = content
    #     send_message(msg)
    #     send_message(msg2)
    #     send_message(msg3, close_after=True)
    #     return "Received data '{data}'".format(data=request_message)

    s.listen()
