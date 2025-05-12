from dotenv import load_dotenv
from yarl import Query
from rocketbotte import Bot, Subscriptions, Message
import asyncio,aiohttp,  os, sys
from websockets.asyncio.client import connect
import websockets
from enum import Enum
import json, time
from loguru import logger

load_dotenv(override=True)
USER_ID = os.getenv('USER_ID')
AUTH_TOKEN = os.getenv('AUTH_TOKEN')
SERVER_URL = os.getenv('SERVER_URL')

                    
class Status(Enum):
    OFF = 'OFF'
    CONNECTED = 'CONNECTED'
    LOGGED = 'LOGGED'
    READY = 'READY'
                    
async def test2():
    print('mebut')
    async for websocket in connect(SERVER_URL):
        print('asyon')
        try:
            print('try')
            
            status:Status = Status.OFF
            subscriptions:dict[str, Subscriptions] =  {}
            sub_ready = set()
            await websocket.send('{"msg": "connect","version": "1","support": ["1"]}')
            async for message in websocket:
                message:dict = json.loads(message)
                if status == Status.OFF:
                    if message.get('msg')  == 'connected':
                        status = Status.CONNECTED
                        await websocket.send(json.dumps({"msg": "method", 'id': 'login', "method": "login", "params":[{ "resume": AUTH_TOKEN}]}))
                else : 
                    if message.get('msg') == 'ping':
                        #await websocket.send('{"msg": "pong"}')]
                        await websocket.pong()
                        continue
                    
                    if status == Status.CONNECTED:               
                        if message.get('id') == 'login':
                            status = Status.LOGGED
                            logger.info(f'Logged as {message.get('result', {}).get('id')}')
                            await websocket.send('{"msg": "method",  "method": "subscriptions/get",  "id": "subscribe", "params": []}')
                            continue
                        
                    if status == Status.LOGGED:
                        if message.get('id') == 'subscribe':
                            subs = message.get('result', [])
                            logger.info(f'Suscribing to {len(subs)} rooms')
                            
                            for sub in subs:
                                subscription = Subscriptions(sub)
                                subscriptions[subscription.room_id] = subscription
                                q =  {"msg": "sub", "id": f"retrieve_{subscription.room_id}", "name": "stream-room-messages", "params":[subscription.room_id, False ]}
                                await websocket.send(json.dumps(q))
                            continue
                    
                        if message.get('msg') == 'ready' and message.get('subs') is not None and 'retrieve_' in message.get('subs')[0]:
                            rid = message.get('subs')[0].split('_')[1]
                            sub_ready.add(rid)
                            logger.debug(f'watching {subscriptions[rid]}')
                            
                            if len(sub_ready) == len(subscriptions):
                                logger.info('Bot ready and listenning')
                                status = Status.READY
                            continue
                    if status == Status.READY:
                        if message.get('collection') is not None and message.get('collection') == 'stream-room-messages':
                            # editedBy var si edit, sinon on met dans une dequeue les messages déjà traité,
                            if len(message.get('fields', {}).get('args')) == 1:
                                msg = Message(message.get('fields', {}).get('args'))
                                print(msg)
                                print(message)
                            #                     {'msg': 'changed', 'collection': 'stream-room-messages', 'id': 'id', 'fields': {'eventName': '67c1e5e3e2e364b2cf0d9520', 'args': [{'_id': 'uopNc4BDaTTNc9Lme', 'rid': '67c1e5e3e2e364b2cf0d9520', 'msg': 'titi', 'ts': {'$date': 1745772412094}, 'u': {'_id': 'EydHKNZax6ekuERew', 'username': 'Thomas', 'name': 'Thomas'}, '_updatedAt': {'$date': 1745772412136}, 'urls': [], 'mentions': [], 'channels': [], 'md': [{'type': 'PARAGRAPH', 'value': [{'type': 'PLAIN_TEXT', 'value': 'titi'}]}]}]}}
                            # {'msg': 'changed', 'collection': 'stream-room-messages', 'id': 'id', 'fields': {'eventName': 'BrBwrnYGyv78ayLLnEydHKNZax6ekuERew', 'args': [{'_id': 'WXhEf9Dhw6JmZBEfj', 'rid': 'BrBwrnYGyv78ayLLnEydHKNZax6ekuERew', 'msg': 'toutout', 'ts': {'$date': 1745772416991}, 'u': {'_id': 'EydHKNZax6ekuERew', 'username': 'Thomas', 'name': 'Thomas'}, '_updatedAt': {'$date': 1745772417045}, 'urls': [], 'mentions': [], 'channels': [], 'md': [{'type': 'PARAGRAPH', 'value': [{'type': 'PLAIN_TEXT', 'value': 'toutout'}]}]}]}}
        except Exception as e:
            logger.warning(e)
            print('Exception')
            continue

async def main():
    await test2()
    
asyncio.run(main())