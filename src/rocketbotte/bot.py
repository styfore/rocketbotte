import traceback
from loguru import logger 
import asyncio, json, aiohttp
from websockets.asyncio.client import connect,  ClientConnection
from datetime import datetime, timezone
from yarl import URL
from enum import Enum
from typing import Coroutine
from collections import deque
from .models import User, Message, Subscriptions

class Bot():
    API:str = 'api/v1'
    def __init__(self,server_url:str, auth_token:str, delay=1, command_prefix='!'):
        super().__init__()
        self.status:Status= Status.OFF
        self.server_url = server_url
        self.auth_token = auth_token
        self.command_prefix = command_prefix
        
        self.subscriptions:dict[str, Subscriptions] = {}
        
        self.commands = {}
        self.events = {}
        
        self.background_task = set()
        self.pending_requests = set()

    
    def run(self):
        asyncio.run(self.__run())
    
    async def __run(self):
        async for websocket in connect(self.server_url):
            try:
                self.status:Status= Status.OFF
                subscriptions:dict[str, Subscriptions] =  {}
                sub_ready = set()
                await self._connect(websocket)
                async for message in websocket:
                    message:dict = json.loads(message)
                    if self.status != Status.READY:
                        await self._log_if_not(message, websocket)
                        await self._subscribe(message, websocket)
                        
                    await self.pong(message, websocket)
                    await self.__process_messages(message, websocket)
            except Exception as e:
                logger.error(e)
                traceback.print_exc()
                await asyncio.sleep(5)
                continue

    async def _connect(self, websocket:ClientConnection):
        if self.status == Status.OFF:
            logger.info(f'Connection to {self.auth_token}')
            await websocket.send('{"msg": "connect","version": "1","support": ["1"]}')               

        
    async def pong(self, message:dict, websocket:ClientConnection):
        if message.get('msg') == 'ping':
            logger.trace(f'pong')
            await websocket.send('{"msg": "pong"}')
            
    async def __process_messages(self, message:dict, websocket:ClientConnection):
        if message.get('collection') is not None and message.get('collection') == 'stream-room-messages':
            if len(message.get('fields', {}).get('args')) == 1:
                msg = Message(message.get('fields', {}).get('args'))
                if msg.edited_at is None:
                    print(msg)
                    print(message)
                else:
                    print('edited')
    
    async def _log_if_not(self, message:dict, websocket:ClientConnection):
        if self.status == Status.OFF:
            if message.get('msg')  == 'connected':
                logger.info(f'Connected to {self.auth_token}')
                self.status = Status.CONNECTED
                await websocket.send(json.dumps({"msg": "method", 'id': 'login', "method": "login", "params":[{ "resume": self.auth_token}]}))
                self.pending_requests.add('login')
                
        elif self.status == Status.CONNECTED and message.get('id') == 'login':               
            if 'login' in self.pending_requests and message.get('id') == 'login':
                logger.info(f'Logged as {message.get('result', {}).get('id')}')
                self.pending_requests.remove('login')
                self.status = Status.LOGGED

                
    async def _subscribe(self, message:dict, websocket:ClientConnection):
        if self.status == Status.LOGGED:
            await websocket.send('{"msg": "method",  "method": "subscriptions/get",  "id": "get_subscriptions", "params": []}')
            self.pending_requests.add('get_subscriptions')
            self.status = Status.SUSCRIBING
        elif self.status == Status.SUSCRIBING:
            if 'get_subscriptions' in self.pending_requests and message.get('id') == 'get_subscriptions':
                subs = message.get('result', [])
                logger.info(f'Suscribing to {len(subs)} rooms')
                for sub in subs:
                    subscription = Subscriptions(sub)
                    self.subscriptions[subscription.room_id] = subscription
                    self.pending_requests.add(f'retrieve_{subscription.room_id}')
                    q =  {"msg": "sub", "id": f"retrieve_{subscription.room_id}", "name": "stream-room-messages", "params":[subscription.room_id, False ]}
                    await websocket.send(json.dumps(q))
            elif message.get('msg') == 'ready' and message.get('subs') is not None and message.get('subs')[0] in self.pending_requests:
                rid = message.get('subs')[0].split('_')[1]
                self.pending_requests.remove(message.get('subs')[0])
                logger.debug(f'watching {self.subscriptions[rid]}')
                
                if not any([pr.startswith('retrieve_') for pr in self.pending_requests]):
                    logger.info('Bot ready and listenning')
                    self.status = Status.READY
                
                
            
            
            

    async def __process_messages2(self, session:aiohttp.ClientSession, subscription:Subscriptions):
        # retrieve history
        max_date = self.last_update
        status, history = await self.__call_api(session, f'{subscription.room_type.endpoint}.history', roomId=subscription.room_id, oldest=self.last_update)
        if status == 200:
            for message in history.get('messages', []):
                message = Message(message)
                self.fire_event('on_message', message)
                max_date = max(max_date, message.created_at) if message.created_at is not None else max_date
        else:
            raise Exception(f'{history['status']} {history.status} : unable to connect, check auth_token or user_id : {history['message']}')
        return max_date
    

    def  add_listener(self, func:Coroutine, name: str = None) -> None:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError('Listeners must be coroutines')
        name = func.__name__ if name is None else name

        if name in self.events:
            self.events[name].append(func)
        else:
            self.events[name] = [func]
    
    def remove_listener(self, func:Coroutine, name: str = None) -> None:
        name = func.__name__ if name is None else name

        if name in self.events:
            try:
                self.events[name].remove(func)
            except ValueError:
                pass
            
    def fire_event(self, name, *args, **kwargs):
        for event in self.events.get(name, []):
            task = asyncio.create_task(event(*args, **kwargs))
            self.background_task.add(task)
            task.add_done_callback(self.background_task.discard)
                
    def listen(self, name: str = None) :
        """A decorator that registers another function as an external
        event listener. Basically this allows you to listen to multiple
        events from different places e.g. such as `.on_ready`

        The functions being listened to must be coroutine.
        
        Example
        --------

        .. code-block:: python3

            @bot.listen()
            async def on_message(message):
                print('one')

            # in some other file...

            @bot.listen('on_message')
            async def my_message(message):
                print('two')

        Would print one and two in an unspecified order.
        """
        def decorator(func):
            self.add_listener(func, name)
            return func

        return decorator    
        
class Status(Enum):
    OFF = 'OFF'
    CONNECTED = 'CONNECTED'
    LOGGED = 'LOGGED'
    SUSCRIBING = 'SUSCRIBING'
    READY = 'READY'
                    
    
class Event(Enum):
    ON_MESSAGE = 'on_message'
    ON_COMMAND = 'on_command'
    