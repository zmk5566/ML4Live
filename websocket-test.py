# Import the necessary modules
import asyncio
import websockets

# Define your WebSocket server
async def websocket_server(websocket, path):
    message = await websocket.recv()  # Receive message from client
    print(f"Received message: {message}")

    response = "Message received!"
    await websocket.send(response)  # Send response to client
    print(f"Sent message: {response}")

# Start the server
start_server = websockets.serve(websocket_server, "localhost", 8765)

# Run the server
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()