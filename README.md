# SteveSockets
**For demonstration and educational purposes only — this server cannot support production projects**
__Note: Test are not currently passing, need to be updated with recent refactor__
A Small Socket Server Implementation in Python 3.10 with HTTP and WebSocket extensions.

## Usage
Each different server can be started using the corresponding "run" script:
1. Socket server: `run_socket_server.py`
2. WebSocket server: `run_websocket_server.py`
3. HTTP server: `run_http_server.py`

Each server uses an event-observer system built into the base server itself to allow for 
listening for certain message types and responding appropriately. To register a new listener, refer
to the `register_listener` calls in each "run" script. Listeners can be assigned to respond based
on message "type", the determination of which is determined from the incoming data and can be handled
by adding overriding the `get_message_type` class in the server class; currently this is only done
in the WebSocket server class (`websocket/server.py`) since the other two classes, for demo purposes,
need only treat the incoming data as bytes/text. WebSockets need to understand specific message types
based on incoming headers to negotiate the handshake appropriately.

## Demo Server Functionality
### Socket Server
1. Run the socket server with `python run_socket_server.py`
2. In a separate terminal window, use the `nc` (netcat) tool to communicate with the server
   1. Using command like `echo "Hello I am the client!" | nc 127.0.0.1 8080`
3. You should see the message successfully being received and logged by the server, and a response given to the client

### WebSocket Server
1. Run the websocket server with `python run_websocket_server.py`
2. In a web browser, open up the Javascript console
3. Using Javascript
   1. Create a new websocket connection
      1. `wsClient = new WebSocket("ws://127.0.0.1:9000");`
   2. Initialize the appropriate listener to ensure you see the server response
      1. `wsClient.onmessage = console.log`
   3. Send a message to the server
      1. `wsClient.send("Hello I am the client!")`
4. You should see the message being received and logged by the server, and a response emitted in the JS console

### HTTP Server
1. Run the HTTP server with `python run_http_server.py`
2. In the web browser, open a new tab at the server address of http://127.0.0.1:9000
3. You should see the HTTP message received and logged by the server, and a valid HTML page rendered in the browser