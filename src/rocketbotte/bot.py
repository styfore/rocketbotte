import time
from loguru import logger 
import asyncio, traceback, re
from enum import Enum
from typing import Coroutine
from rocketbotte.models import Message, Subscription
from collections import deque
import aiohttp
from aiohttp import ClientWebSocketResponse, WSMessage
from yarl import URL
        
class Status(Enum):
    OFF = 'OFF'
    CONNECTED = 'CONNECTED'
    LOGGED = 'LOGGED'
    SUSCRIBING = 'SUSCRIBING'
    READY = 'READY'
                    
    
class Command:
    def __init__(self, name, args):
        self.name = name
        self.args = args
    
class Context:
    def __init__(self, message:Message, send:Coroutine):
        self.message = message
        self.send = send
        
    async def send_message(self, content:str):
        await self.send(self.message.room_id, content)
        
class Bot():
    API:str = 'api/v1'
    
    def __init__(self,server_url:str, user_id:str, auth_token:str, command_prefix='!', max_retry:int=5, REST_API:str = 'api/v1'):
        super().__init__()
        self.rest_url = URL(server_url.strip())
        self.ws_url = URL(re.sub('^http([s]?)://', lambda m : f'ws{m.group(1)}://', str(self.rest_url)))/'websocket'
        self.user_id = user_id
        self.auth_token = auth_token
        self.api = REST_API
        
        self.command_prefix = command_prefix
        
        self.status:Status= Status.OFF
        self.subscriptions:dict[str, Subscription] = {}
        
        self.retry = 0
        self.max_retry = max_retry
        self.background_task = set()
        self.pending_requests = set()
        self.r_command = re.compile(rf'^\s?{command_prefix}(\w+)\s?(.*)')
        
        self.events = {}
        self.commands = {}
        self.already_process = deque(maxlen=100)
        self.add_listener(self.on_command, 'on_command')

    
    def run(self):
        try:
            asyncio.run(self.__run())
        except Exception as e:
            self.retry += 1
            logger.error(e)
            logger.error(traceback.format_exc())
            if self.retry < self.max_retry:
                self.status:Status= Status.OFF
                logger.error('Uncaught exception')
                logger.info(f'Retry ({self.retry}/{self.max_retry}) in 5 seconds...')
                time.sleep(5)
                self.run()
            else:
                logger.info('max retry reached, exit program')
                exit()
    
    async def __run(self):
        async with aiohttp.ClientSession() as session:
            async with  session.ws_connect(self.ws_url) as ws:
                await self._connect(ws)
                
                async for msg in ws:
                    await self.pong(msg, ws)
                    if self.status != Status.READY:
                        await self._login(msg, ws)
                        await self._subscribe(msg, ws)
                        await self._assert_rooms_suscribed(msg)
                    else:
                        await self.__process_messages(msg.json())

   
    def fire_event(self, name, *args):
        logger.trace(f'fire event {name} with args {args}')
        for event in self.events.get(name, []):
            task = asyncio.create_task(event(*args))
            self.background_task.add(task)
            task.add_done_callback(self.background_task.discard)
            
     
    async def on_command(self, ctx:Context, command_name, args):
        '''a predefined on_message listenner, will look for command  command_name to run it'''
        try:
            coro:Coroutine = self.commands[command_name]
            await coro(ctx, args)
        except Exception as e:
            logger.warning(f'Exception in command {command_name}')
            logger.warning(e)
            logger.warning(traceback.format_exc())


    async def send_message(self, room_id:str , content:str):
        '''send content to the room with rid room_id'''
        try:
            headers = {'X-User-Id': self.user_id, 'X-Auth-Token': self.auth_token}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(url=self.rest_url/self.api/'chat.sendMessage', json={'message': {'rid':room_id, 'msg':content}}) as response:
                    status, rjson =  response.status, await response.json()
                    if status != 200 or rjson.get('success') is not True: 
                        logger.warning(f'chat.sendMessage return status {rjson['status']} {response.status} :  maybe check auth_token or user_id : {rjson['message']}')               
                    return status, rjson
        except Exception as e:
            logger.error(f'Exception while calling {self.server_url/self.api/'chat.sendMessage'}')
            raise e
             
    async def __process_messages(self, message:dict):
        if message.get('collection') is not None and message.get('collection') == 'stream-room-messages':
            if len(message.get('fields', {}).get('args')) == 1:
                j = message.get('fields', {}).get('args')[0]
                msg = Message(message.get('fields', {}).get('args')[0])
                if msg.id not in self.already_process:
                    self.already_process.append(msg.id)
                    if msg.edited_at is None:
                        ctx = Context(msg,  self.send_message)
                        self.fire_event('on_message', msg)
                        m = self.r_command.match(msg.content)
                        if m is not None:
                            self.fire_event('on_command', ctx, m.group(1), m.group(2))
                                   
    async def _connect(self, ws:ClientWebSocketResponse):
        if self.status == Status.OFF:
            await ws.send_json({"msg": "connect","version": "1","support": ["1"]})
            reponse:dict = await ws.receive_json()
            if reponse.get('msg')  == 'connected':
                logger.info(f'Connection to websocket {self.rest_url}')
                self.status = Status.CONNECTED
        else:
            raise Exception('erreur lors de la connexion')

    async def _login(self, msg:WSMessage, ws:ClientWebSocketResponse):
        if self.status == Status.CONNECTED:
            if 'login' not in self.pending_requests:
                self.pending_requests.add('login')
                await ws.send_json({"msg": "method", 'id': 'login', "method": "login", "params":[{ "resume": self.auth_token}]})
            else:
                if msg.json().get('id') == 'login' :
                    logger.info(f'Logged as {msg.json().get('result', {}).get('id')}')
                    self.status = Status.LOGGED
                    self.pending_requests.remove('login')
                    
        
    async def pong(self, msg:WSMessage,  ws:ClientWebSocketResponse):
        if msg.json()['msg'] == 'ping':
            logger.trace(f'pong')
            await ws.send_json({"msg": "pong"})
                
    async def _subscribe(self, msg:WSMessage, ws:ClientWebSocketResponse):
        if self.status == Status.LOGGED:
            if 'get_subscriptions' not in self.pending_requests:
                self.pending_requests.add('get_subscriptions')
                await ws.send_json({"msg": "method",  "method": "subscriptions/get",  "id": "get_subscriptions", "params": []})
            else:
                if msg.json().get('id') == 'get_subscriptions':
                    subs = msg.json().get('result', [])
                    logger.info(f'Suscribing to {len(subs)} rooms')
                    self.pending_requests.remove('get_subscriptions')
                    for sub in subs:
                        subscription = Subscription(sub)
                        self.subscriptions[subscription.room_id] = subscription
                        request_id = f"retrieve_{subscription.room_id}"
                        self.pending_requests.add(request_id)
                        await ws.send_json({"msg": "sub", "id": request_id, "name": "stream-room-messages", "params":[subscription.room_id, False ]})
                    self.status = Status.SUSCRIBING
                    
    async def _assert_rooms_suscribed(self, msg:WSMessage):
        if self.status == Status.SUSCRIBING:
            response_id = msg.json().get('subs', [None])[0]
            if response_id is not None and response_id in self.pending_requests:
                logger.debug(f'watching {self.subscriptions[response_id.split('_')[1]]}')
                self.pending_requests.remove(response_id)
                
                if not any([f'retrieve_{rid}' in self.pending_requests for rid in self.subscriptions.keys()]):
                    logger.info('Bot ready and listenning')
                    self.status = Status.READY
                    self.fire_event('on_ready')
                    

    def  add_listener(self, func:Coroutine, name: str = None, aliases:list[str]=[]) -> None:
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
            
    
                
    def command(self, name: str = None, aliases:list[str]=[]) :
        """A decorator that registers a coro that will be eventually executed in a on_command event

        The functions being listened to must be coroutine.
        
        Example
        --------

        .. code-block:: python3

            @bot.command()
            async def command_name(message):
                print('one')

            # in some other file...

            @bot.command('command_name')
            async def my_command(message):
                print('two')

        Would print one and two in an unspecified order.
        """
        def decorator(func):
            n = func.__name__ if name is None else name
            self.commands[n] = func
            return func

        return decorator

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

        