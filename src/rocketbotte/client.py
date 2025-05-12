import json, sys
from loguru import logger 
import asyncio, aiohttp, time
from aiohttp import BasicAuth
from datetime import datetime, timezone
from types import SimpleNamespace
from yarl import URL

class Bot():
    API:str = 'api/v1'
    
    def __init__(self, user_id:str, auth_token:str, server_url:str, delay=1):
        super().__init__()
        self.user_id = user_id
        self.auth_token = auth_token
        self.server_url = URL(server_url)
        self.status = 'OFF'
        self.delay = delay
        self.headers = {'X-User-Id': self.user_id, 'X-Auth-Token': self.auth_token}
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    
    def run(self):
        asyncio.run(self.__run())
    
    async def __run(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            await self.__login(session)

            # while self.status == 'CONNECTED':
            last_update = datetime.now()
            messages = await self.__get_messages(session, last_update)
            time.sleep(self.delay)
            
                
            

            
                
    async def __call_api(self, session:aiohttp.ClientSession, endpoint:str,  api:str=API, **params ):
        async with session.get(url=self.server_url/api/endpoint, params=params) as response:
            return response.status, await response.json()
            
    async def __login(self, session:aiohttp.ClientSession):
        status, response = await self.__call_api(session, 'me')
        if status == 200:
            self.me = response
            self.status = 'CONNECTED'
            logger.info(f'Logged as {self.me['username']}')
        else:
            resp = await response.json()
            raise Exception(f'{resp['status']} {response.status} : unable to connect, check auth_token or user_id : {resp['message']}')
        

    async def __get_messages(self, session:aiohttp.ClientSession, last_update:datetime):
        status, channels = await self.__call_api(session, 'subscriptions.get')
        if status == 200:
            for channel in channels['update']:
                print(channel)


# /api/v1/me           
    # X-User-Id
    # stringRequired

    # The user ID of the user.
    # X-Auth-Token
    # stringRequired

    # The authorization token of the user.
    #
# /api/v1/logout
