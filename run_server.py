import sys
from stevesockets.server import WebSocketServer
import logging
import argparse

if __name__ == "__main__":
    logger = logging.getLogger("stevesockets.server.WebSocketServer")
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
    def handler(conn, data):
        return data

    s.listen()
