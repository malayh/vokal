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
    def __init__(self,ws:websockets.WebSocketClientProtocol, name: str, room_id: int, user_id : int):
        self.ws : websockets.WebSocketClientProtocol = ws
        self.name : str = name
        self.room_id = room_id
        self.user_id = user_id
        

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

        self.user_id_seq = 1

        self.outQ = Producer(TMQ_HOST, TMQ_PORT, TOPIC_TO_VOICE_SERVER)
        self.inQ = Consumer(TMQ_HOST, TMQ_PORT, TOPIC_FROM_VOICE_SERVER)

        # This a future for self.poll_from_voice_server coroutine.
        # This will be initialized at the first call to self.__run_server
        # Doing this so that multiple versions of self.poll_from_voice_server are not added to event_loop
        # And this future will never be awaited. 
        # TODO: Not sure how to teminate this gracefully when RootServer goes down
        self.inQ_polling = None

    async def maintain_client_connection(self, conn : ActiveConnection) -> None:
        """
        If ws connection is broken, remove the user from active connections and send signal to voice server
        If new user is added to the room, send a message to the client about it

        Once instance of this function will be added to the event loop for every active connection
        """
        self.logger.info(f"Connection initiated. Name:{conn.name} UserID:{conn.user_id} RoomID: {conn.room_id}")
        while True:
            await asyncio.sleep(1)

    async def poll_from_voice_server(self):
        """
        This function will be put in the event loop at the start of the server. It will keep polling for
        messages from voice server and do actions accodingly. 
        """
        while True:
            msg = await self.inQ.poll()
            if not msg:
                await asyncio.sleep(0.1)
                continue

            room_id = msg[0]
            data = json.loads(msg[1])

            if "type" not in data:
                self.logger.debug(f"Voice server send msg without type. Message will be discarded")
                continue

            if data["type"] == "answer":
                if "user_id" not in data:
                    self.logger.debug(f"Voice server sent answer without user_id. Message will be discarded")
                    continue

                if "sdp" not in data:
                    self.logger.debug(f"Voice server sent answer without sdp. Message will be discarded")
                    continue

                if room_id not in self.active_connections:
                    self.logger.error(f"Voice server sent a answer for room_id {room_id} which doesnot exist yet. Panic!!")
                    continue

                user = None
                for i in self.active_connections[room_id]:
                    if i.user_id == data["user_id"]:
                        user = i
                        break

                if not user:
                    self.logger.error(f"Voice server sent a answer for user_id {data['user_id']} which doesnot exist yet. Panic!!")
                    continue
                
                self.logger.debug("Sending sdp to client:\n"+data["sdp"])
                _to_client = {
                    "type"  : "answer",
                    "sdp"   : data["sdp"],
                    "room_id": room_id
                }
                await user.ws.send(json.dumps(_to_client))    

    async def handle_connection_init(self, ws:websockets.WebSocketClientProtocol, path:str):
        """
        At the start of the connection the client is expected to send the following
        {
            name    : Name of user,
            room_id : which is an int, if not, new room will be created
            sdp     : connection ICEs of client
        }
        """
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

        if "sdp" not in data:
            self.logger.debug("SDP not sent. Clossing connection.")
            return

        if not room_id:
            self.logger.info("room_id is not an integer. Will be creating a new Room.")
            
            _rid = random.randint(1000, 100000)
            while _rid in self.active_connections:
                _rid = random.randint(1000, 100000)

            room_id = _rid        


        conn = ActiveConnection(ws, data["name"],room_id,self.user_id_seq+1)
        self.user_id_seq+=1
        
        if room_id in self.active_connections:
            self.active_connections[room_id].add(conn)
        else:
            self.active_connections[room_id] = set([conn])

        # Send to voice server
        _vs = {
            "type"      : "offer",
            "sdp"       : data["sdp"],
            "room_id"   : conn.room_id,
            "user_id"   : conn.user_id
        }
        await self.outQ.send(json.dumps(_vs), conn.user_id)
        await self.maintain_client_connection(conn)

    async def __run_server(self):
        await self.outQ.init_conn()
        await self.inQ.init_conn()
        
        if not self.inQ_polling:
            self.inQ_polling = asyncio.ensure_future(self.poll_from_voice_server())

        server = await websockets.serve(self.handle_connection_init,HOST,PORT) # TODO: host and port are still global vars
        await server.wait_closed()

    def start(self):        
        asyncio.run(self.__run_server())
        


if __name__ == "__main__":
    RootSever().start()