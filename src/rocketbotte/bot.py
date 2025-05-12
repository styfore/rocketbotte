import json, sys
from loguru import logger 
import asyncio, aiohttp, time
from aiohttp import BasicAuth
from datetime import datetime, timezone
from types import SimpleNamespace
from yarl import URL
from enum import Enum
from typing import Any, Coro, Coroutine
class Bot():
    API:str = 'api/v1'
    subscription_type = {'d' : 'dm', 'c' : 'channels', 'p': 'groups'}
    def __init__(self, server_url:str, delay=1):
        super().__init__()
        self.server_url = URL(server_url)
        self.status:Status= Status.OFF
        self.delay = delay
        self.last_update = str(datetime.now(timezone.utc).isoformat("T", "milliseconds")).split('+')[0]
        self.commands = {}
        self.events = {}
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    
    def run(self, user_id:str, auth_token:str):
        asyncio.run(self.__run(user_id=user_id, auth_token=auth_token))
    
    async def __run(self, user_id:str, auth_token:str):
        headers = {'X-User-Id': user_id, 'X-Auth-Token': auth_token}
        async with aiohttp.ClientSession(headers=headers) as session:
            await self.__login(session)
            
            while self.status == Status.READY:
                await self.__process_subscriptions(session)
                time.sleep(self.delay)

                
    async def __call_api(self, session:aiohttp.ClientSession, endpoint:str,  api:str=API, **params ):
        try:
            async with session.get(url=self.server_url/api/endpoint, params=params) as response:
                status, rjson =  response.status, await response.json()
                if status != 200:
                    logger.warning(f'{endpoint} return status {rjson['status']} {response.status} :  maybe check auth_token or user_id : {rjson['message']}')               
                return status, rjson
        except Exception as e:
            logger.error(f'Exception while calling {self.server_url}/{endpoint}')
            raise e
        
            
    async def __login(self, session:aiohttp.ClientSession):
        status, response = await self.__call_api(session, 'me')
        if status == 200:
            self.me = response
            self.status = Status.READY
            logger.info(f'Logged as {self.me['username']}')
        else:
            resp = await response.json()
            error_message = f'unable to connect, check auth_token or user_id : {resp['message']}'
            logger.error(error_message)
            raise Exception(error_message)
        

    async def __process_subscriptions(self, session:aiohttp.ClientSession):
        # get subscription channels to look for history
        status, subscriptions = await self.__call_api(session, 'subscriptions.get')
        if status == 200:
            tasks:list[asyncio.Task] = []
            async with asyncio.TaskGroup() as tg:
                for subscription in subscriptions.get('update', []):
                    tasks.append(tg.create_task(self.__process_messages(session, subscription)))
            max_dates = [task.result() for task in tasks if task.result() is not None]
            if len(max_dates) > 0:
                self.last_update = max([task.result() for task in tasks if task.result() is not None])
            

    async def __process_messages(self, session:aiohttp.ClientSession, subscription):
        # retrieve history
        room_id = subscription['rid']
        endpoint = self.subscription_type.get(subscription['t'])
        max_date = self.last_update
        if endpoint is not None:    
            status, history = await self.__call_api(session, f'{endpoint}.history', roomId=room_id, oldest=self.last_update)
            if status == 200:
                for message in history.get('messages', []):
                    print(f'{message['u']['username']} : {message['msg']}')
                    max_date = max(max_date, message['ts']) if message['ts'] is not None else max_date
            else:
                raise Exception(f'{history['status']} {history.status} : unable to connect, check auth_token or user_id : {history['message']}')
        return max_date
    

    def  add_listener(self, func:Coroutine, name) -> None:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError('Listeners must be coroutines')
        
        if name in self.events:
            self.events[name].append(func)
        else:
            self.events[name] = [func]
        
        
class Status(Enum):
    OFF = False
    READY = True
    