import logging
import socket
import select
import threading
import base64
import hashlib
from stevesockets.websocket import WebSocketFrame, SocketException, WebSocketFrameHeaders, SocketBytesReader
from stevesockets.socketconnection import SocketConnection
from stevesockets.messages import MessageManager
from stevesockets.listeners import CloseListener, TextListener, PingListener, MessageSynchronizer


class SocketServer:

    connection_cls = SocketConnection

    def __init__(self, address=('127.0.0.1', 9000), logger=None):
        self.address = address
        self.listening = False
        self.set_logger(logger if logger else logging.getLogger())
        self.connections = []
        self.handle_message = None
        self.message_manager = MessageManager()

    def _create_socket(self):
        self.logger.debug("Creating socket @ {addr}:{port}".format(addr=self.address[0], port=self.address[1]))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind(self.address)
        except OSError as err:
            self.logger.error("Couldn't bind to socket: '{msg}'".format(msg=err.args))
            self.socket = None

    def dlisten(self):
        """ Creates, starts, and returns a threading.Thread that runs the `listen` method """
        t = threading.Thread(target=self.listen)
        t.start()
        return t

    def set_logger(self, logger):
        self.logger = logger

    def _get_client_connection(self):
        sck, addr = self.socket.accept()
        self.logger.debug("{addr}".format(addr=addr))
        connection = self.connection_cls(sck, addr[0], addr[1], logger=self.logger)
        self.logger.debug(
            "New connection created at {addr}:{port}".format(addr=connection.address, port=connection.port))
        return connection

    def prune_connections(self):
        """ Removes connections from the pool that are closed or marked to be closed """
        # this list will be the list of valid connections left (after creating new connections and closing old ones)
        # after we've finished looping through all the currently active connections
        new_connection_list = self.connections[:]
        for connection in self.connections:
            if connection.is_to_be_closed():
                self.logger.warn("Connection @ {addr}:{port} to be closed before receiving data? closing".format(
                    addr=connection.address, port=connection.port))
                new_connection_list.remove(connection)
                self._close_connection(connection)
            elif connection.is_closed():  # this can happen in when running asynchronously
                new_connection_list.remove(connection)
            elif connection.socket.fileno() == -1:
                self.logger.warn("Connection with invalid file descriptor not closed or marked for closure")
                self._close_connection(connection)
                new_connection_list.remove(connection)
        self.connections = new_connection_list

    def _build_connections(self):
        conn, _, _ = select.select([self.socket], [], [], .1)
        for c in conn:
            connection = self._get_client_connection()
            self.connections.append(connection)
            self.logger.debug("Total connections: {n}".format(n=len(self.connections)))

    def listen(self):
        """ Creates and binds a socket connection at `address` on `port`, then listens for incoming
            client connections, reads data from them and sends back the return value of `connection_handler`
            as a response. Business logic should be handled in `handle_message` in subclasses,
            unless there are specialized cases for connections that need to be handled. """
        self._create_socket()
        if not self.socket:
            self.logger.warn("Socket not successfully initialized, check logs for details. Aborting listen()")
            self.stop_listening()
            self._stop_server()
        else:
            self.logger.debug("Listening on socket @ {addr}:{port}".format(addr=self.address[0], port=self.address[1]))
            self.socket.listen(100)

            self.listening = True
            while self.listening:
                try:
                    self._build_connections()
                except KeyboardInterrupt as err:
                    self.logger.warn("Manually interrupting server")
                    self.stop_listening()
                    break

                self.prune_connections()
                for connection in self.connections:
                    try:
                        avail_data, _, _ = select.select([connection.socket], [], [], .1)
                        if avail_data:
                            response = self.connection_handler(connection)
                            if response:
                                self.on_message(connection, response)
                    except socket.error as err:
                        self.logger.warning("Socket error '{err}'".format(err=err))
                        self._close_connection(connection)
                    except KeyboardInterrupt as err:
                        self.logger.warn("Manually interrupting server")
                        self.stop_listening()
                        break
            self._stop_server()

    def on_message(self, connection, response):
        self.logger.debug("Sending message {r}".format(
            r=response.encode() if hasattr(response, "encode") else response))
        self.message_manager.dispatch_message(
            response,
            message_type=self.get_message_type(response),
            connection=connection,
            server=self
        )
        # each message the server receives could queue messages in any given connection, so flush them all
        for conn in self.connections:
            conn.flush_messages()

    def get_message_type(self, message):
        return self.message_manager.default_message_type

    def connection_handler(self, connection):
        """ Takes a SocketConnection as an argument and passes data received from it
            to `handle_message` which should return the appropriate response for the
            application. Can be overridden for pre-processing connections/data before
            building a response such as decoding/encoding data before it's passed to
            the business logic portion of your application """
        data = connection.socket.recv(4096)
        if data:
            response = self.handle_message(self, connection, data)
            return response
        else:
            connection.mark_for_closing()
            return None

    def handle_message(self, connection, data):
        """ Should be overridden by subclasses. Responsible for taking raw bytes and
            returning the business logic response in bytes """
        return "Hello World"

    def message_handler(self, fn):
        """ This decorator can be used to simply set a handle_message without subclassing """
        self.handle_message = fn
        return fn

    def _close_connection(self, connection):
        """ Can be overridden to allow custom behavior around closing SocketConnections """
        connection.close()
        self.logger.debug("Connection @ {addr}:{port} closed".format(addr=connection.address, port=connection.port))

    def _stop_server(self):
        self.logger.debug("Closing {n} connections".format(n=len(self.connections)))
        [self._close_connection(c) for c in self.connections]
        self.connections = []
        if self.socket:
            self.logger.debug("Closing server socket")
            self.socket.close()
        else:
            self.logger.debug("Socket not initialized, no need to close")
        self.logger.debug("Server done listening")

    def stop_listening(self):
        """ Sets a flag for the server to stop taking new requests and then gracefully close all
            connections after finishing processing the current pool. """
        self.logger.debug("Stopping listening")
        self.listening = False


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
        self.setup_listeners()

    def setup_listeners(self):
        self.register_listener(CloseListener, message_type=WebSocketFrame.OPCODE_CLOSE)
        self.register_listener(PingListener, message_type=WebSocketFrame.OPCODE_PING)
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
