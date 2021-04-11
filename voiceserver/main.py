from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRelay, MediaPlayer, MediaRecorder, MediaBlackhole
from tinyMQ import Producer, Consumer
from typing import Set, Dict, List, Tuple
import logging
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
import asyncio
import json

TMQ_HOST = "localhost"
TMQ_PORT = 9800
TOPIC_FROM_ROOT_SERVER = "fromRootServer"
TOPIC_TO_ROOT_SERVER = "fromVoiceServer"
logging.basicConfig(level=logging.ERROR)


class Room:
    def __init__(self, id: int, q : Connection):
        self.id = id
        self.outQ : Connection = q


class LiveRoom:
    """
    This will run in a separate process for every live room

    It recieves new connection request from the inQ. New connection request if of the format:
        { 
            type:  
            room_id: 
            user_id: 
            sdp: 
        }
    
    It writes answer to outQ, which is been consumed by the RootServer which will be sent to the client. Answer is of format
    { type , room_id , user_id ,sdp}

    """
    def __init__(self, room_id:int, q: Connection ):
        self.room_id = room_id
        self.relay = MediaRelay()
        self.active_users : Dict[int, Tuple[RTCPeerConnection, MediaStreamTrack] ] = dict()
        # outQ is listened by RootServer
        self.outQ = Producer(TMQ_HOST,TMQ_PORT,TOPIC_TO_ROOT_SERVER)
        self.inQ : Connection = q
        self.logger = logging.getLogger(f"LiveRoom_{self.room_id}")
        self.logger.setLevel(logging.DEBUG)

        self.blackhole = MediaBlackhole()


    async def listen_inq(self):
        """
        This is the main loop for the live rooms
        """
        while True:
            # because inQ.get is sychronous, running it in a thread so that main event loop is not blocked
            data = await asyncio.get_running_loop().run_in_executor(None, self.inQ.recv)

            if not isinstance(data, dict)  or "type" not in data:
                self.logger.debug("Invald data read. Message will be discarded.")
                continue

            if data["type"] == "offer":
                if "sdp" not in data:
                    self.logger.debug("Offer recieved without sdp. Message will be discarded.")
                    continue
                if "user_id" not in data:
                    self.logger.debug("Offer recieved without user_id. Message will be discarded.")
                    continue
                
                await self.handle_incoming_offer(data["sdp"], data["user_id"])


    async def handle_incoming_offer(self, sdp, user_id):

        player = MediaPlayer("./test.mp3")

        if user_id in self.active_users:
            self.logger.debug(f"User {user_id} already in room_id")
            return

        pc = RTCPeerConnection()
        
        @pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            async def on_message(message):
                if isinstance(message, str):
                    channel.send("pong")

            # Do nothing, but still defining it
            # TODO: Try removing this and see if it still works

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            self.logger.debug(f"Connecting state changed to {pc.connectionState} for user {user_id} in room {self.room_id}")
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                await pc.close()
                if user_id in self.active_users:
                    del self.active_users[user_id]

        @pc.on("track")
        async def on_track(track):
            self.logger.debug(f"Got {track.kind} track from user {user_id} in room {self.room_id}")
            if track.kind == "audio":
                self.active_users[user_id] = [pc,track]
                

            @track.on("ended")
            async def on_ended():
                pass
                # IDK what to do here

        
        for uid, value in self.active_users.items():
            if value[1]:
                pc.addTrack(self.relay.subscribe(value[1]))
               


        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        ans = await pc.createAnswer()
        await pc.setLocalDescription(ans)

        if user_id not in self.active_users:
            self.active_users[user_id] = [pc,None]

        _ans = {
            "type"      : "answer",
            "user_id"   : user_id,
            "room_id"   : self.room_id,
            "sdp"       : pc.localDescription.sdp
        }

        await self.outQ.send(json.dumps(_ans), self.room_id)


    async def __run_server(self):
        await self.outQ.init_conn()
        await self.listen_inq()

    def start_room(self):
        self.logger.info(f"Starting room {self.room_id}")
        asyncio.run(self.__run_server())



        

class VoiceServer:
    """
    Voice server creates live rooms and send new connection request to a live voice room when it is
    """
    def __init__(self):
        self.active_rooms : Dict[int, Room] = dict()
        self.inQ = Consumer(TMQ_HOST,TMQ_PORT,TOPIC_FROM_ROOT_SERVER)
        self.logger = logging.getLogger("VoiceServer")
        self.logger.setLevel(logging.DEBUG)


    async def poll_forever(self):
        """
        Data recieved from root server looks like the following
        (user_id , data)
        
        data is a dict
        {
            type: <type of action to be taken. Allowed types : type, killroom, kickuser>
            <other things>
        }
        
        """
        while True:
            msg = await self.inQ.poll()
            if not msg:
                await asyncio.sleep(0.1)
                continue

            user_id = msg[0]
            data = json.loads(msg[1])

            if "type" not in data:
                self.logger.debug(f"Recieved message from RootServer without 'type'. Message will be discarded.")
                continue

            if "room_id" not in data:
                self.logger.debug(f"Recieved message from RootServer without 'room_id'. Message will be discarded.")
                continue

            if data["type"] == "offer" and "sdp" not in data:
                self.logger.debug(f"Recieved offer from RootServer without 'sdp'. Message will be discarded.")
                continue

            
            # Initiate connecting new connection
            if data["type"] == "offer" :
                self.logger.debug(f"Initiating connection. User id : {user_id}, Room_id:{data['room_id']}")
                await self.init_connection(data["room_id"], user_id, data["sdp"])
                continue

    async def init_connection(self,room_id:int, user_id:int, sdp: str):
        if room_id not in self.active_rooms:
            recver, sender = Pipe()
            room = Room(room_id, sender)
            self.active_rooms[room_id] = room

            lr = LiveRoom(room_id, recver)
            Process(target=lr.start_room).start()
            sender.send({
                "type" : "offer",
                "sdp"  : sdp,
                "user_id": user_id
            })
        else:
            self.active_rooms[room_id].outQ.send({
                "type" : "offer",
                "sdp"  : sdp,
                "user_id": user_id
            })


    async def __run_server(self):
        await self.inQ.init_conn()
        await self.poll_forever()

    def start(self):
        asyncio.run(self.__run_server())


if __name__ == "__main__":
    VoiceServer().start()

