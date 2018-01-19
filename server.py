import logging
import socket, select, threading
import collections

class SocketConnection:

    def __init__(self, sck, address, port, logger=None):
        self.socket = sck
        self.address = address
        self.port = port
        self.handshook = False
        self.to_be_closed = False
        self.closed = False
        self.logger = logger if logger else logging.getLogger()
        self.messages = collections.deque()

    def close(self):
        self.logger.debug("Closing connection at {addr}:{port}".format(addr=self.address, port=self.port))
        self.socket.close()
        self.closed = True

    def queue_message(self, message):
        self.messages.append(message)

    def flush_messages(self):
        for x in range(len(self.messages)):
            msg = self.messages.popleft()
            self.socket.sendall(msg)

    def peek_message(self, n=0):
        if len(self.messages) > n:
            return self.messages[n]
        else:
            return None

    def is_closed(self):
        return self.closed

    def mark_handshook(self):
        self.handshook = True

    def is_handshook(self):
        return self.handshook

    def mark_for_closing(self):
        self.to_be_closed = True

    def is_to_be_closed(self):
        return self.to_be_closed

class SocketServer:

    def __init__(self, address=('127.0.0.1', 9000), logger=None):
        self.address = address
        self.listening = False
        self.set_logger(logger if logger else logging.getLogger())
        self.connections = []

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
                    conn, _, _ = select.select([self.socket], [], [], .1)
                    for c in conn:
                        sck, addr = self.socket.accept()
                        self.logger.debug("{addr}".format(addr=addr))
                        connection = SocketConnection(sck, addr[0], addr[1], logger=self.logger)
                        self.connections.append(connection)
                        self.logger.debug("New connection created at {addr}:{port}".format(addr=self.connections[-1].address, port=self.connections[-1].port))
                        self.logger.debug("Total connections: {n}".format(n=len(self.connections)))
                except KeyboardInterrupt as err:
                    self.logger.warn("Manually interrupting server")
                    self.stop_listening()
                    break
                # this list will be the list of valid connections left (after creating new connections and closing old ones)
                # after we've finished looping through all the currently active connections
                new_connection_list = self.connections[:]
                for connection in self.connections:
                    if connection.is_to_be_closed():
                        self.logger.warn("Connection @ {addr}:{port} to be closed before recieving data? closing".format(addr=connection.address, port=connection.port))
                        new_connection_list.remove(connection)
                        self._close_connection(connection)
                        continue
                    try:
                        avail_data, _, _ = select.select([connection.socket], [], [], .1)
                        if avail_data:
                            response = self.connection_handler(connection)
                            # TODO: Figure out a way to allow connections to be closed via client-sent close frame while echoing
                            #       that frame's message and not distrupting gracefully closing on KeyboardInterrupt or error
                            if response:
                                self.logger.debug("Sending message {r}".format(r=response.encode() if hasattr(response, "encode") else response))
                                connection.queue_message(response.encode() if hasattr(response, "encode") else response)
                            if connection.is_to_be_closed():
                                self.logger.debug("Closing connection marked for closure")
                                new_connection_list.remove(connection)
                                self._close_connection(connection)
                        connection.flush_messages()
                    except socket.error as err:
                        self.logger.warning("Socket error '{err}'".format(err=err))
                        new_connection_list.remove(connection)
                        self._close_connection(connection)
                    except KeyboardInterrupt as err:
                        self.logger.warn("Manually interrupting server")
                        self.stop_listening()
                        break
                self.connections = new_connection_list
            self._stop_server()

    def connection_handler(self, connection):
        """ Takes a SocketConnection as an argument and passes data recieved from it
            to `handle_message` which should return the appropriate response for the
            application. Can be overriden for preprocessing connections/data before
            building a response such as decoding/encoding data before it's passed to
            the business logic portion of your application """
        data = connection.socket.recv(4096)
        if data:
            response = self.handle_message(connection, data)
            return response
        else:
            return None

    def handle_message(self, connection, data):
        """ Should be overriden by subclasses. Responsible for taking raw bytes and
            returning the business logic response in bytes """
        return "Hello world"

    def message_handler(self, fn):
        self.handle_message = fn
        return fn

    def _close_connection(self, connection):
        """ Can be overridden to allow custom behavior around closing SocketConnections """
        connection.close()
        self.logger.debug("Connection @ {addr}:{port} closed".format(addr=connection.address, port=connection.port))

    def _stop_server(self):
        self.logger.debug("Closing {n} connections".format(n=len(self.connections)))
        [self._close_connection(c) for c in self.connections]
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

from stevesockets.websocket import WebSocketFrame
import base64, hashlib

class WebSocketServer(SocketServer):

    WEBSOCKET_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, address=('127.0.0.1', 9000), logger=None):
        super(WebSocketServer, self).__init__(address=address, logger=logger)
        self.fragmented_messages = {}

    def connection_handler(self, conn):
        data = conn.socket.recv(4096)
        self.logger.debug("Websocket server handling data: {data}".format(data=data))
        if not conn.is_handshook():
            return self.handle_websocket_handshake(conn, data)
        else:
            frame = WebSocketFrame.from_bytes(data)
            if not bool(frame.fin):
                self.fragmented_messages.setdefault(conn, [])
                self.fragmented_messages[conn].append(frame)
                return None
            else: # is final frame
                message_fragments = self.fragmented_messages.get(conn)
                if message_fragments:
                    complete_message = "".join(f.message for f in message_fragments)
                    complete_message += frame.message
                    self.fragmented_messages[conn] = []
                # check for special frames (PING, close, etc)
                elif frame.opcode == WebSocketFrame.OPCODE_PING:
                    self.logger.debug("Recieved PING, sending PONG")
                    return WebSocketFrame(message=frame.message, opcode=WebSocketFrame.OPCODE_PONG).to_bytes()
                elif frame.opcode == WebSocketFrame.OPCODE_PONG:
                    self.logger.debug("Recieved PONG, ignoring")
                    return None # ignore pongs
                elif frame.opcode == WebSocketFrame.OPCODE_CLOSE:
                    self.logger.debug("Recieved close frame with message: {m}".format(m=frame.message))
                    if conn.is_to_be_closed():
                        self.logger.warn("Connection is already marked for closing, ignoring addtional close frame")
                        return None
                    else:
                        conn.mark_for_closing()
                        return WebSocketFrame(message=frame.message, opcode=WebSocketFrame.OPCODE_CLOSE).to_bytes()
                else: #normal message
                    complete_message = frame.message
            response = self.handle_message(conn, complete_message)
            return WebSocketFrame(message=response).to_bytes()

    def _close_connection(self, connection, close_message="Connection closing"):
        self.logger.debug("Connection @ {addr}:{port} starting graceful closure".format(addr=connection.address, port=connection.port))
        last_msg = connection.peek_message()
        if not last_msg or WebSocketFrame.from_bytes(last_msg).opcode != WebSocketFrame.OPCODE_CLOSE:
            self.logger.debug("Close frame not already queued up, adding one")
            connection.queue_message(WebSocketFrame(message=close_message, opcode=WebSocketFrame.OPCODE_CLOSE).to_bytes())
        connection.flush_messages()
        # get the one last closing frame that should be incoming
        self.connection_handler(connection)
        if not connection.is_to_be_closed():
            self.logger.warn("Connection @ {addr}:{port} didn't recieve close frame back from client".format(addr=connection.address, port=connection.port))
        super(WebSocketServer, self)._close_connection(connection)

    def _get_websocket_accept(self, key):
        return base64.b64encode(hashlib.sha1((key + self.WEBSOCKET_MAGIC).encode()).digest()).decode()

    def handle_websocket_handshake(self, conn, data):
        self.logger.debug("Starting handshake")
        split_data = data.decode().split("\r\n")
        method, path, http = split_data[0].split(" ")
        headers = {}
        try:
            for header in split_data[1:]:
                if ": " in header:
                    key, value = header.split(": ")
                    headers[key] = value
        except TypeError as err:
            self.logger.error("Malformed headers in client handshake, closing connection")
            conn.mark_for_closing()
            response = ""
        except BaseException as err:
            self.logger.error("Unexpected error encountered, closing connection: {msg}".format(msg=err))
            conn.mark_for_closing()
            response = ""
        else:
            accept = self._get_websocket_accept(headers.get("Sec-WebSocket-Key"))
            response = "".join(["HTTP/1.1 101 Switching Protocols\r\n",
                                "Upgrade: websocket\r\n",
                                "Connection: Upgrade\r\n",
                                "Sec-WebSocket-Accept: {accept}\r\n\r\n".format(accept=accept)])
            conn.mark_handshook()
            self.logger.debug("Handshake successful @ {addr}:{port}".format(addr=conn.address, port=conn.port))
        return response
