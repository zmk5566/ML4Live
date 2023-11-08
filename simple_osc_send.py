from pythonosc import udp_client

# Define OSC client
ip = "127.0.0.1"  # IP address of the server you want to send to.
port = 6000  # Port number.

client = udp_client.SimpleUDPClient(ip, port)  # Create client.

# Send single message.
address = "/prediction"  # Address pattern of the OSC message.
message = "Hello, World!"  # Content of the OSC message.

client.send_message(address, message)  # Send message.
