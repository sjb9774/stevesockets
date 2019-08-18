from stevesockets.messages import Listener
from stevesockets.websocket import WebSocketFrame, WebSocketFrameHeaders
import logging
from stevesockets import LOGGER_NAME


class CloseListener(Listener):

    def observe(self, message, *args, connection=None, **kwargs):
        # as soon as we know a CLOSE frame is received, send no other messages and close connection
        connection.clear_messages()
        connection.queue_message(WebSocketFrame.get_close_frame(message.message).to_bytes())
        connection.flush_messages()
        connection.close()


class PingListener(Listener):

    def observe(self, message, *args, connection=None, **kwargs):
        logger = logging.getLogger(LOGGER_NAME)
        logger.debug("Received PING, sending PONG")
        connection.queue_message(WebSocketFrame.get_pong_frame(message=message).to_bytes())


class TextListener(Listener):

    def observe(self, message, *args, **kwargs):
        logger = logging.getLogger(LOGGER_NAME)
        logger.debug(f"Handling text message: '{message.message}'")


class MessageSynchronizer(Listener):

    def observe(self, message, *args, connection=None, server=None, **kwargs):
        headers = WebSocketFrameHeaders(payload_length=len(message.message))
        server_message = WebSocketFrame(headers=headers, message=message.message)
        for server_connection in server.connections:
            if server_connection != connection:
                server_connection.queue_message(server_message.to_bytes())
