#!/usr/bin/env python3

import sys
import logging
import argparse
from stevesockets.websocket import LOGGER_NAME
from stevesockets.messages import MessageTypes
from stevesockets.listeners import TextListener
from stevesockets.websocket.websocket import WebSocketFrame
from stevesockets.websocket.server import WebSocketServer, WebSocketConnection


class CustomListener(TextListener):

    def observe(self,
                message: WebSocketFrame,
                *args,
                connection: WebSocketConnection = None,
                server: WebSocketServer = None,
                **kwargs):
        print(f"Observing incoming message {message}")
        message = f"SteveSockets WebSocketServer has received your message of '{message.message}'!"
        connection.queue_message(WebSocketFrame.get_text_frame(message).to_bytes())


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

    s = WebSocketServer(logger=logger)
    s.register_listener(CustomListener, message_type=MessageTypes.TEXT)

    s.listen()
