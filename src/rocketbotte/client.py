import json, sys
from loguru import logger 
import asyncio, aiohttp, time
from aiohttp import BasicAuth
from datetime import datetime, timezone

class Bot():
    def __init__(self, user_id:str, auth_token:str, server_url:str, delay=1):
        super().__init__()
        self.user_id = user_id
        self.auth_token = auth_token
        self.server_url = server_url
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
            # logger.info(f'Connected as {self.me.name} on {self.server_url}')
            self.status = 'CONNECTED'
            
            # while self.status == 'CONNECTED':
            #     last_update = datetime.now()
            #     messages = await self.__get_messages(session, last_update)
            #     await self.__process_messages(messages)
            #     time.sleep(self.delay)
                
    async def __login(self, session:aiohttp.ClientSession):
        async with session.get(url=self.server_url+ '/api/v1/me') as response:
            print(response.headers)
            print("Status:", response.status)
            print("Content-type:", response.headers['content-type'])
            self.me = await response.json()
            print(self.me )
            
    async def __get_messages(self, session:aiohttp.ClientSession, last_update:datetime):
        async with session.get(self.server_url, ) as response:

            print("Status:", response.status)
            print("Content-type:", response.headers['content-type'])

            html = await response.text()
            print("Body:", html[:15], "...")
 
 
# /api/v1/me           
    # X-User-Id
    # stringRequired

    # The user ID of the user.
    # X-Auth-Token
    # stringRequired

    # The authorization token of the user.
    #
# /api/v1/logout
