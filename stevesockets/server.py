import logging
import socket
import select
import threading
from stevesockets.socketconnection import SocketConnection
from stevesockets.messages import MessageTypes, MessageManager


class SocketServer:
    connection_cls = SocketConnection
    connections: list[SocketConnection]

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
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

    def _get_client_connection(self) -> SocketConnection:
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
                self.logger.warning(
                    "Connection closure initiated by peer @ {addr}:{port}".format(
                        addr=connection.address,
                        port=connection.port
                    )
                )
                new_connection_list.remove(connection)
                self._close_connection(connection)
            elif connection.is_closed():  # this can happen in when running asynchronously
                new_connection_list.remove(connection)
            elif connection.socket.fileno() == -1:
                self.logger.warning("Connection with invalid file descriptor not closed or marked for closure")
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
            self.logger.warning("Socket not successfully initialized, check logs for details. Aborting listen()")
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
                    self.logger.warning("Manually interrupting server")
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
                    except OSError as err:
                        self.logger.warning("Socket error '{err}'".format(err=err))
                        self._close_connection(connection)
                    except KeyboardInterrupt as err:
                        self.logger.warning("Manually interrupting server")
                        self.stop_listening()
                        break
                    except Exception as err:
                        self.logger.error(f"General error encountered, attempting graceful shutdown. Error: {err}")
                        self.stop_listening()
                        break
            self._stop_server()

    def on_message(self, connection, response):
        self.logger.debug("Handling bytes {r}".format(
            r=response.encode() if hasattr(response, "encode") else response)
        )
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
        # TODO: Use some logic or configuration to determine message types
        return MessageTypes.DEFAULT

    @staticmethod
    def get_send_message_closure(connection: SocketConnection):
        def send_message_closure(message: bytes, close_after: bool = False):
            connection.queue_message(message)
            if close_after:
                connection.mark_for_closing()
            return connection

        return send_message_closure

    def connection_handler(self, connection: SocketConnection):
        """ Takes a SocketConnection as an argument and passes data received from it
            to `handle_message` which should return the appropriate response for the
            application. Can be overridden for pre-processing connections/data before
            building a response such as decoding/encoding data before it's passed to
            the business logic portion of your application """
        data = connection.socket.recv(4096)
        if data:
            response = self.handle_message(data, self.get_send_message_closure(connection))
            return response
        else:
            connection.mark_for_closing()
            return None

    def handle_message(self, connection, data):
        """ Should be overridden by subclasses. Responsible for taking raw bytes and
            returning the business logic response in bytes """
        return "Hello World"

    def message_handler(self, fn: callable):
        """ This decorator can be used to simply set a handle_message without subclassing """
        self.handle_message = fn
        return fn

    def _close_connection(self, connection: SocketConnection):
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
