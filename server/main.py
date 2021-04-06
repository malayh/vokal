import websockets
import asyncio
import random
from typing import List, Dict, Set
from tinyMQ import Producer, Consumer
import logging
import json

HOST = "localhost"
PORT = 8500

TMQ_HOST = "localhost"
TMQ_PORT = 9800
TOPIC_TO_VOICE_SERVER = "fromRootServer"
TOPIC_FROM_VOICE_SERVER = "fromVoiceServer"

logging.basicConfig(level=logging.INFO)




class ActiveConnection:
    def __init__(self,ws:websockets.WebSocketClientProtocol, name: str, room_id: int):
        self.ws : websockets.WebSocketClientProtocol = ws
        self.name : str = name
        self.room_id = room_id
        

class RootSever:
    """
    Root server handles signling voice server, creating rooms, adding/removing people from room

    Response sent back to client are of structure
    {
        type : <type of message>,
        <other things>
    }
    """
    def __init__(self) -> None:
        # active_connections is map of { room_id , set of active connections
        self.active_connections : Dict[int, Set[ActiveConnection]] = dict()
        
        self.logger = logging.getLogger("RootServer")
        self.logger.setLevel(logging.DEBUG)


    async def listen_forever(self, conn : ActiveConnection) -> None:
        """
        If ws connection is broken, remove the user from active connections and send signal to voice server
        If new user is added to the room, send a message to the client about it
        """
        self.logger.info(f"Connection initiated by {conn.name} for room {conn.room_id}")

        

    async def handle_connection_init(self, ws:websockets.WebSocketClientProtocol, path:str):
        try:
            data = await ws.recv()
            data = json.loads(data)
        except json.JSONDecodeError:
            self.logger.debug("Invalid initial JSON. Closing connection.")
            return

        self.logger.debug("Following data is recieved:\n"+json.dumps(data,indent=2))


        if "name" not in data:
            self.logger.debug("Username must be sent. Closing connection.")
            return

        if "room_id" not in data:
            self.logger.debug("Room id must be sent. Closing connection.")
            return

        try:
            room_id = int(data["room_id"])
        except ValueError:
            room_id = None

        if not room_id:
            self.logger.info("room_id is not an integer. Will be creating a new Room.")
            
            _rid = random.randint(1000, 100000)
            while _rid in self.active_connections:
                _rid = random.randint(1000, 100000)

            room_id = _rid        


        conn = ActiveConnection(ws, data["name"],room_id)
        
        if room_id in self.active_connections:
            self.active_connections[room_id].add(conn)
        else:
            self.active_connections[room_id] = set([conn])

        await self.listen_forever(conn)

    async def __run_server(self):
        server = await websockets.serve(self.handle_connection_init,HOST,PORT) # TODO: host and port are still global vars
        await server.wait_closed()

    def start(self):
        asyncio.run(self.__run_server())
        


if __name__ == "__main__":
    RootSever().start()