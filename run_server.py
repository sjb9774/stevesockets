#!/usr/bin/env python3

import sys
from stevesockets.server import SocketServer, SocketConnection
import logging
import argparse
from stevesockets import LOGGER_NAME
from stevesockets.websocket.websocket import WebSocketFrame, WebSocketFrameHeaders
from stevesockets.listeners import TextListener


class CustomListener(TextListener):

    def observe(self, message, *args, connection=None, server=None, **kwargs):
        message = f"SteveSockets WebSocketServer has received your message of '{message.message}'!"
        connection.queue_message(WebSocketFrame.get_text_frame(message).to_bytes())


if __name__ == "__main__":
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", action="store", default=9000, type=int)
    parser_args = parser.parse_args()

    s = SocketServer(logger=logger)


    @s.message_handler
    def my_business_function(request_message: bytes, send_message: callable):
        content = bytes("<!doctype html><html><body><h1>Hello world</h1></body></html>", "utf-8")
        msg = bytes(f"HTTP/1.1 200 OK\r\n", 'utf-8')
        msg2 = bytes(f"content-type: text/html\r\n\r\n", "utf-8")
        msg3 = content
        send_message(msg)
        send_message(msg2)
        send_message(msg3, close_after=True)
        return "Received data '{data}'".format(data=request_message)

    s.listen()
