from stevesockets.server import SocketServer
from stevesockets.server import SocketBytesReader


class HttpServer(SocketServer):
    def connection_handler(self, conn):
        bytes_reader = SocketBytesReader(conn)

        self.logger.debug("HTTP server handling incoming data")
        try:
            bit = bytes_reader.get_next_bytes(2)
            chunk = bit
            # while we're getting data, or we're _not_ getting data but we don't have any to process
            while chunk and not chunk.endswith(b'\r\n\r\n'):
                bit = bytes_reader.get_next_bytes(16)
                chunk += bit
            http_in = chunk
        except ConnectionResetError:
            self.logger.warning("Connection closed prematurely, marking for closing")
            conn.mark_for_closing()
            return None

        if not http_in:
            self.logger.warning("Read no data from socket, marking for closing")
            conn.mark_for_closing()
        return http_in
