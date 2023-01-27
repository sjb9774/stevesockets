import base64
import hashlib
from stevesockets.websocket.websocket import WebSocketFrame, SocketException, SocketBytesReader
from stevesockets.socketconnection import SocketConnection
from stevesockets.listeners import CloseListener, TextListener, PingListener
from stevesockets.server import SocketServer


class WebSocketConnection(SocketConnection):

    CLOSED = "closed"
    CONNECTING = "connecting"
    CONNECTED = "connected"

    def __init__(self, sck, address="127.0.0.1", port=9000, logger=None):
        super(WebSocketConnection, self).__init__(sck, address=address, port=port, logger=logger)
        self.status = WebSocketConnection.CLOSED

    def mark_handshook(self):
        self.set_status(WebSocketConnection.CONNECTED)
        super(WebSocketConnection, self).mark_handshook()

    def mark_for_closing(self):
        super(WebSocketConnection, self).mark_for_closing()
        self.set_status(WebSocketConnection.CLOSED)

    def set_status(self, status):
        self.logger.debug(
            "Setting connection @ {addr}:{port} status to '{status}'".format(addr=self.address, port=self.port,
                                                                             status=status))
        self.status = status

    def get_status(self):
        return self.status


class WebSocketServer(SocketServer):

    connection_cls = WebSocketConnection
    WEBSOCKET_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    MAX_BUFFER_SIZE = 4096

    def __init__(self, address=('127.0.0.1', 9000), logger=None):
        super(WebSocketServer, self).__init__(address=address, logger=logger)
        self.fragmented_messages = {}
        self.setup_control_listeners()
        self.setup_message_listeners()

    def setup_control_listeners(self):
        self.register_listener(CloseListener, message_type=WebSocketFrame.OPCODE_CLOSE)
        self.register_listener(PingListener, message_type=WebSocketFrame.OPCODE_PING)

    def setup_message_listeners(self):
        self.register_listener(TextListener, message_type=WebSocketFrame.OPCODE_TEXT)

    def register_listener(self, listener_cls, message_type=None):
        self.message_manager.listen_for_message(listener_cls(), message_type=message_type)

    def _get_client_connection(self):
        conn = super(WebSocketServer, self)._get_client_connection()
        self.logger.debug("Executing handshake with new connection")
        handshake_input = conn.socket.recv(4096)
        self.handle_websocket_handshake(conn, handshake_input)
        return conn

    def connection_handler(self, conn):
        bytes_reader = SocketBytesReader(conn)

        self.logger.debug("Websocket server handling incoming data")
        try:
            frame = WebSocketFrame.from_bytes_reader(bytes_reader)
        except (SocketException, ConnectionResetError):
            self.logger.warning("Connection closed prematurely, marking for closing")
            conn.mark_for_closing()
            return None

        return frame

    def get_message_type(self, message):
        return message.headers.opcode

    def _close_connection(self, connection, close_message="Connection closing"):
        self.logger.debug("Connection @ {addr}:{port} starting graceful closure".format(addr=connection.address,
                                                                                        port=connection.port))
        super(WebSocketServer, self)._close_connection(connection)

    def _get_websocket_accept(self, key):
        return base64.b64encode(hashlib.sha1((key + self.WEBSOCKET_MAGIC).encode()).digest()).decode()

    @staticmethod
    def send_http_response(conn, status, headers=None):
        descriptions = {
            101: "Switching Protocols",

            200: "OK",

            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            429: "Too Many Requests",

            500: "Internal Server Error",
            501: "Not Implemented",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout"
        }
        msg = "HTTP/1.1 {status} {status_description}\r\n".format(status=status,
                                                                  status_description=descriptions.get(status, ""))
        if headers:
            for header, value in headers.items():
                msg += "{header}: {value}\r\n".format(header=header, value=value)
        msg += "\r\n"
        conn.socket.sendall(msg.encode())

    def handle_websocket_handshake(self, conn, data):
        self.logger.debug("Starting handshake")
        conn.set_status(WebSocketConnection.CONNECTING)
        split_data = data.decode().split("\r\n")
        try:
            method, path, http = split_data[0].split(" ")
            headers = {}
            for header in split_data[1:]:
                if ": " in header:
                    key, value = header.split(": ")
                    headers[key] = value
            accept = self._get_websocket_accept(headers.get("Sec-WebSocket-Key"))
        except (TypeError, ValueError) as err:
            self.logger.error("Malformed headers in client handshake, closing connection")
            self.send_http_response(conn, 400)
            conn.mark_for_closing()
        except BaseException as err:
            self.logger.error("Unexpected error encountered, closing connection: {msg}".format(msg=err))
            self.send_http_response(conn, 500)
            conn.mark_for_closing()
        else:
            self.send_http_response(conn, 101, headers={
                "Upgrade": "websocket",
                "Connection": "Upgrade",
                "Sec-WebSocket-Accept": accept
            })
            conn.mark_handshook()
            self.logger.debug("Handshake successful @ {addr}:{port}".format(addr=conn.address, port=conn.port))
