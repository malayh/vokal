import aiortc
from tinyMQ import Producer, Consumer
from typing import Set, Dict, List
import logging
import multiprocessing

TMQ_HOST = "localhost"
TMQ_PORT = 9800
TOPIC_FROM_ROOT_SERVER = "fromRootServer"
TOPIC_TO_ROOT_SERVER = "fromVoiceServer"


class Room:
    def __init__(self, id: int, q : multiprocessing.connection.Connection):
        self.id = id
        self.queue : multiprocessing.connection.Connection = q


class LiveRoom:
    def __init__(self):
        self.outQ = Producer(TMQ_HOST,TMQ_PORT,TOPIC_TO_ROOT_SERVER)

class VoiceServer:
    def __init__(self):
        self.active_rooms : Dict[int, Room] = dict()
        self.inQ = Consumer(TMQ_HOST,TMQ_PORT,TOPIC_FROM_ROOT_SERVER)

    async def poll_forever(self):
        pass

    async def start(self):
        await self.inQ.init_conn()
        await self.poll_forever()



