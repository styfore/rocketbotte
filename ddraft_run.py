from dotenv import load_dotenv
from yarl import Query
from rocketbotte import Bot, Subscriptions, Message
import asyncio,aiohttp,  os, sys
from websockets.asyncio.client import connect
import websockets
import json, time
from loguru import logger

load_dotenv(override=True)
USER_ID = os.getenv('USER_ID')
AUTH_TOKEN = os.getenv('AUTH_TOKEN')
SERVER_URL = os.getenv('SERVER_URL')


headers = {'X-User-Id': USER_ID, 'X-Auth-Token': AUTH_TOKEN}
connect_ = {
"msg": "connect",
"version": "1",
"support": ["1"]
}

async def test1():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(SERVER_URL) as ws:
            print('test')
            await ws.send_json(connect_)
            await ws.send_json({"msg": "method", "method": "rooms/get", "id": "getRooms", "params": [ { "$date": 0 } ]})
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(msg.data['msg'])
                    
                    if msg.data['id'] == 'getRooms':
                        rooms = msg.data['update']
                        
                    
                    
async def test2():
    async for websocket in connect(SERVER_URL):
        try:
            is_connected = False
            is_logged = False
            print('connected')
            connexion = await websocket.send(json.dumps(connect_))
            id = str(int(time.time()))
            subscriptions:dict[str, Subscriptions]=  {}
            
            async for message in websocket:
                message:dict = json.loads(message)
                if not is_connected:
                    if message.get('msg')  == 'connected':
                        print('conuco', message)
                        is_connected = True
                        await websocket.send(json.dumps({"msg": "method", 'id': 'login', "method": "login", "params":[{ "resume": AUTH_TOKEN}]}))
                else :                   
                    if message.get('id') == 'login':
                        print('conuco 1', message)
                        is_logged = True
                        logger.info(f'Logged as {message.get('result', {}).get('id')}')
                        await websocket.send(json.dumps({"msg": "method",  "method": "subscriptions/get",  "id": "sub", "params": []}))
                        continue
                    if message.get('msg') == 'ping':
                        await websocket.pong()
                        continue
                    
                    if message.get('id') == 'sub':
                        subs = message.get('result', [])
                        logger.info(f'Suscribing to {len(subs)} rooms')
                        for sub in subs:
                            subscription = Subscriptions(sub)
                            subscriptions[subscription.room_id] = subscription
                            q =  {"msg": "sub", "id": f"retrieve_{subscription.room_id}", "name": "stream-room-messages", "params":[subscription.room_id, False ]}
                            await websocket.send(json.dumps(q))
                        continue
                    
                    if message.get('msg') == 'ready' and message.get('subs') is not None and 'retrieve_' in message.get('subs')[0]:
                        logger.info(f'watching {subscriptions[message.get('subs')[0].split('_')[1]]}')
                        continue
                    if message.get('collection') is not None and message.get('collection') == 'stream-room-messages':
                        # editedBy var si edit, sinon on met dans une dequeue les messages déjà traité,
                        if len(message.get('fields', {}).get('args')) == 1:
                            msg = Message(message.get('fields', {}).get('args'))
                            print(msg)
                            print(message)
#                     {'msg': 'changed', 'collection': 'stream-room-messages', 'id': 'id', 'fields': {'eventName': '67c1e5e3e2e364b2cf0d9520', 'args': [{'_id': 'uopNc4BDaTTNc9Lme', 'rid': '67c1e5e3e2e364b2cf0d9520', 'msg': 'titi', 'ts': {'$date': 1745772412094}, 'u': {'_id': 'EydHKNZax6ekuERew', 'username': 'Thomas', 'name': 'Thomas'}, '_updatedAt': {'$date': 1745772412136}, 'urls': [], 'mentions': [], 'channels': [], 'md': [{'type': 'PARAGRAPH', 'value': [{'type': 'PLAIN_TEXT', 'value': 'titi'}]}]}]}}
# {'msg': 'changed', 'collection': 'stream-room-messages', 'id': 'id', 'fields': {'eventName': 'BrBwrnYGyv78ayLLnEydHKNZax6ekuERew', 'args': [{'_id': 'WXhEf9Dhw6JmZBEfj', 'rid': 'BrBwrnYGyv78ayLLnEydHKNZax6ekuERew', 'msg': 'toutout', 'ts': {'$date': 1745772416991}, 'u': {'_id': 'EydHKNZax6ekuERew', 'username': 'Thomas', 'name': 'Thomas'}, '_updatedAt': {'$date': 1745772417045}, 'urls': [], 'mentions': [], 'channels': [], 'md': [{'type': 'PARAGRAPH', 'value': [{'type': 'PLAIN_TEXT', 'value': 'toutout'}]}]}]}}
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(e)
            continue

async def main():
    await test2()
asyncio.run(main())