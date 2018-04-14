import sys
from stevesockets.server import WebSocketServer
import logging

if __name__ == "__main__":
    logger = logging.getLogger("stevesockets.server.WebSocketServer")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    s = WebSocketServer(address=('127.0.0.1', 9000), logger=logger)

    @s.message_handler
    def handler(conn, data):
        return data

    s.listen()
