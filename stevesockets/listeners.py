from stevesockets.messages import Listener
from stevesockets.websocket import WebSocketFrame, WebSocketFrameHeaders
import logging
from stevesockets import LOGGER_NAME
import json


class WebFrameListener(Listener):

    def __init__(self, fn=None):
        super(WebFrameListener, self).__init__(fn)
        self.logger = logging.getLogger(LOGGER_NAME)

    def close_connection(self, connection, message=None):
        # as soon as we know a CLOSE frame is received, send no other messages and close connection
        connection.clear_messages()
        msg = WebSocketFrame.get_close_frame(message)
        self.send_frame(connection, msg, flush_immediately=True)
        connection.close()

    def send_frame(self, connection, frame, flush_immediately=False):
        frame_bytes = frame.to_bytes()
        self.logger.debug(f'Sending bytes: {frame_bytes}')
        connection.queue_message(frame_bytes)
        if flush_immediately:
            connection.flush_messages()


class CloseListener(WebFrameListener):

    def observe(self, message, *args, connection=None, **kwargs):
        self.close_connection(connection, message=message.message)


class PingListener(WebFrameListener):

    def observe(self, message, *args, connection=None, **kwargs):
        msg = WebSocketFrame.get_pong_frame(message=message)
        self.send_frame(connection, msg)


class TextListener(Listener):

    def observe(self, message, *args, **kwargs):
        logger = logging.getLogger(LOGGER_NAME)
        logger.debug(f"Handling text message: '{message.message}'")


class MessageSynchronizer(WebFrameListener):

    def observe(self, message, *args, connection=None, server=None, **kwargs):
        headers = WebSocketFrameHeaders(payload_length=len(message.message))
        server_message = WebSocketFrame(headers=headers, message=message.message)
        for server_connection in server.connections:
            if server_connection != connection:
                self.send_frame(server_connection, server_message)


class JSONListener(Listener):

    def observe(self, message, *args, connection=None, server=None, **kwargs):
        data = json.loads(message.message)
        self.handle_json(data, *args, connection=None, server=None, **kwargs)

    def handle_json(self, data, *args, **kwargs):
        pass
