#!/usr/bin/env python3

import sys
from stevesockets.server import WebSocketServer
import logging
import argparse
from stevesockets import LOGGER_NAME

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
    args = parser.parse_args()

    s = WebSocketServer(address=('127.0.0.1', args.port), logger=logger)

    @s.message_handler
    def handler(server, conn, data):
        logger.debug('Decoded data: {data}'.format(data=data))
        return "This is Steve's server saying 'Hello!'"

    s.listen()
