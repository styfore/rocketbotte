from dotenv import load_dotenv
from rocketbotte import Bot
import asyncio,aiohttp,  os, sys
from websockets.asyncio.client import connect
import websockets
import json, time

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
            print('connected')
            connexion = await websocket.send(json.dumps(connect_))
            id = str(int(time.time()))
            rooms = {
            "msg": "method",
            "method": "rooms/get",
            "id": "42",
            "params": [ { "$date": 0 } ]
            }
            
            noti = {
            "msg": "sub",
            "id": "89494",
            "name": "stream-room-messages",
            "params":[
                "67c1e5e3e2e364b2cf0d9520",
                False
            ]
        }
            await websocket.send(json.dumps({"msg": "method", 'id': id, "method": "login", "params":[{ "resume": AUTH_TOKEN}]}))
            await websocket.send(json.dumps(rooms))
            await websocket.send(json.dumps(noti))
            
            async for message in websocket:
                message = json.loads(message)
                if message['msg'] == 'ping':
                    websocket.pong()
                print('mes', message)
            pass
        except websockets.exceptions.ConnectionClosed:
            continue

async def main():
    await test1()
asyncio.run(main())