==============
 SteveSockets
==============
-------------------------------------------------------
 A Small Socket Server/WebSocket Server Implementation
-------------------------------------------------------

SteveSockets is an attempt to implement a very general and extensible Socket Server
and a similar WebSocket Server extended from it. Still in it's infancy, it is
largely functional for most text data transfers but still needs work to finish
implementing RFC 6455 (https://datatracker.ietf.org/doc/rfc6455/?include_text=1),
which is the number one priority moving forward.

Usage
======

This library is intended to be minimally invasive and concise to implement. To
get a server (Socket or WebSocket) setup and responding to messages as you wish::
    from stevesockets.server import SocketServer

    s = SocketServer()

    @s.message_handler
    def my_business_function(connection, data):
        return "Received data '{data}'".format(data=data)

    s.listen()