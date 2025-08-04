import asyncio
import re
import time
import traceback
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Coroutine

import aiohttp
from aiohttp import ClientWebSocketResponse, WSMessage
from loguru import logger
from yarl import URL

from rocketbotte.exceptions import NoPingException
from rocketbotte.models import Message, Subscription


class Status(Enum):
    OFF = "OFF"
    CONNECTED = "CONNECTED"
    LOGGED = "LOGGED"
    SUSCRIBING = "SUSCRIBING"
    READY = "READY"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class Context:
    def __init__(self, message: Message, send: Coroutine):
        self.message = message
        self.__send = send

    async def send_message(self, content: str):
        await self.__send(self.message.room_id, content)


class Bot:
    API: str = "api/v1"

    def __init__(
        self,
        server_url: str,
        user_id: str,
        auth_token: str,
        command_prefix="!",
        max_retry: int = 5,
        REST_API: str = "api/v1",
        max_retry_time: int = 30,
        max_off_time: int = 120,
    ):
        super().__init__()
        self.rest_url = URL(server_url.strip())
        self.ws_url = URL(re.sub("^http([s]?)://", lambda m: f"ws{m.group(1)}://", str(self.rest_url))) / "websocket"
        self.user_id = user_id
        self.auth_token = auth_token
        self.api = REST_API

        self.command_prefix = command_prefix

        self.status: Status = Status.OFF
        self.subscriptions: dict[str, Subscription] = {}

        self.retry = 0
        self.max_retry = max_retry
        self.max_retry_time = max_retry_time
        self.max_off_time = max_off_time
        self.last_ping: datetime
        self.background_task = set()
        self.watcher_task = None
        self.pending_requests = set()
        self.r_command = re.compile(rf"^\s?{command_prefix}(\w+)\s?(.*)")

        self.events = {}
        self.commands = {}
        self.already_process = deque(maxlen=100)
        self.add_listener(self.on_command, "on_command")
        self.add_listener(self.on_close, "on_close")

    def run(self):
        try:
            asyncio.run(self.__run())
            self.watcher_task.result()
        except Exception as e:
            self.retry += 1
            logger.error(e)
            logger.error(traceback.format_exc())
            if self.retry < self.max_retry:
                self.status: Status = Status.OFF
                logger.error("Uncaught exception")
                logger.info(f"Retry ({self.retry}/{self.max_retry}) in {self.max_retry_time} seconds...")
                time.sleep(self.max_retry_time)
                self.run()
            else:
                logger.info("max retry reached, exit program")
                exit()

    async def __run(self):
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.ws_url) as ws:
                await self._connect(ws)

                self.watcher_task = asyncio.create_task(self.watch_connection(ws))

                async for msg in ws:
                    await self.pong(msg, ws)
                    if self.status != Status.READY:
                        await self._login(msg, ws)
                        await self._subscribe(msg, ws)
                        await self._assert_rooms_suscribed(msg)
                    else:
                        await self.__process_messages(msg.json())

    async def watch_connection(self, ws: ClientWebSocketResponse):
        while True:
            if self.status in [Status.READY, Status.LOGGED, Status.SUSCRIBING]:
                if self.status == Status.CLOSING:
                    await self.close(ws)
                    break

                if self.status == Status.READY:
                    elapsed_time_ping = datetime.now() - self.last_ping
                    logger.trace(f"elapsed time since last ping : {elapsed_time_ping}")
                    if elapsed_time_ping.seconds > self.max_off_time:
                        await self.close(ws)
                        raise NoPingException(f"No ping since {elapsed_time_ping}")
                await asyncio.sleep(1)
            await asyncio.sleep(2)

    def background_event_callback(self, task):
        self.background_task.discard(task)
        if task.exception():
            logger.warning(f"Exception occured during event : {task.exception()!r}")
            print(f"Exception {task.exception()!r} handled!")

    async def on_close(self):
        logger.info("closing websocket")
        self.status = Status.CLOSING

    async def close(self, ws: ClientWebSocketResponse):
        await ws.close()
        self.status = Status.CLOSED
        logger.info("websocket closed")

    def fire_event(self, name, *args):
        logger.trace(f"fire event {name} with args {args}")
        for event in self.events.get(name, []):
            task = asyncio.create_task(event(*args))
            self.background_task.add(task)
            task.add_done_callback(self.background_event_callback)

    async def on_command(self, ctx: Context, command_name, args):
        """a predefined on_message listenner, will look for command  command_name to run it"""
        try:
            coro: Coroutine = self.commands.get(command_name)
            if coro is not None:
                await coro(ctx, args)
            else:
                logger.debug(f"command !{command_name} doesn’t exist")
        except Exception as e:
            logger.warning(f"Exception in command {command_name}")
            logger.warning(e)
            logger.warning(traceback.format_exc())

    async def send_message(self, room_id: str, content: str):
        """send content to the room with rid room_id"""
        try:
            headers = {"X-User-Id": self.user_id, "X-Auth-Token": self.auth_token}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(url=self.rest_url / self.api / "chat.sendMessage", json={"message": {"rid": room_id, "msg": content}}) as response:
                    status, rjson = response.status, await response.json()
                    if status != 200 or rjson.get("success") is not True:
                        logger.warning(
                            f"chat.sendMessage return status {rjson['status']} {response.status} :  maybe check auth_token or user_id : {rjson['message']}"
                        )
                    return status, rjson
        except Exception as e:
            logger.error(f"Exception while calling {self.server_url / self.api / 'chat.sendMessage'}")
            raise e

    async def __process_messages(self, message: dict):
        if message.get("collection") is not None and message.get("collection") == "stream-room-messages":
            if len(message.get("fields", {}).get("args")) == 1:
                msg = Message(message.get("fields", {}).get("args")[0])
                if msg.id not in self.already_process:
                    self.already_process.append(msg.id)
                    if msg.edited_at is None and msg.author.id != self.user_id:
                        self.fire_event("on_message", msg)
                        m = self.r_command.match(msg.content)
                        if m is not None:
                            ctx = Context(msg, self.send_message)
                            self.fire_event("on_command", ctx, m.group(1), m.group(2))

    async def _connect(self, ws: ClientWebSocketResponse):
        if self.status == Status.OFF:
            await ws.send_json({"msg": "connect", "version": "1", "support": ["1"]})
            reponse: dict = await ws.receive_json()
            if reponse.get("msg") == "connected":
                logger.info(f"Connection to websocket {self.rest_url}")
                self.status = Status.CONNECTED
                self.retry = 0
                self.last_ping = datetime.now()
        else:
            raise Exception("erreur lors de la connexion")

    async def _login(self, msg: WSMessage, ws: ClientWebSocketResponse):
        if self.status == Status.CONNECTED:
            if "login" not in self.pending_requests:
                self.pending_requests.add("login")
                await ws.send_json({"msg": "method", "id": "login", "method": "login", "params": [{"resume": self.auth_token}]})
            else:
                if msg.json().get("id") == "login":
                    logger.info(f"Logged as {msg.json().get('result', {}).get('id')}")
                    self.status = Status.LOGGED
                    self.pending_requests.remove("login")

    async def pong(self, msg: WSMessage, ws: ClientWebSocketResponse):
        if msg.json()["msg"] == "ping":
            logger.trace("pong")
            self.last_ping = datetime.now()
            await ws.send_json({"msg": "pong"})

    async def _subscribe(self, msg: WSMessage, ws: ClientWebSocketResponse):
        if self.status == Status.LOGGED:
            if "get_subscriptions" not in self.pending_requests:
                self.pending_requests.add("get_subscriptions")
                await ws.send_json({"msg": "method", "method": "subscriptions/get", "id": "get_subscriptions", "params": []})
            else:
                if msg.json().get("id") == "get_subscriptions":
                    subs = msg.json().get("result", [])
                    logger.info(f"Suscribing to {len(subs)} rooms")
                    self.pending_requests.remove("get_subscriptions")
                    for sub in subs:
                        subscription = Subscription(sub)
                        self.subscriptions[subscription.room_id] = subscription
                        request_id = f"retrieve_{subscription.room_id}"
                        self.pending_requests.add(request_id)
                        await ws.send_json({"msg": "sub", "id": request_id, "name": "stream-room-messages", "params": [subscription.room_id, False]})
                    self.status = Status.SUSCRIBING

    async def _assert_rooms_suscribed(self, msg: WSMessage):
        if self.status == Status.SUSCRIBING:
            response_id = msg.json().get("subs", [None])[0]
            if response_id is not None and response_id in self.pending_requests:
                logger.debug(f"watching {self.subscriptions[response_id.split('_')[1]]}")
                self.pending_requests.remove(response_id)

                if not any([f"retrieve_{rid}" in self.pending_requests for rid in self.subscriptions.keys()]):
                    logger.info("Bot ready and listenning")
                    self.status = Status.READY
                    self.fire_event("on_ready")

    def add_listener(self, func: Coroutine, name: str = None, aliases: list[str] = []) -> None:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Listeners must be coroutines")

        name = func.__name__ if name is None else name

        if name in self.events:
            self.events[name].append(func)
        else:
            self.events[name] = [func]

    def remove_listener(self, func: Coroutine, name: str = None) -> None:
        name = func.__name__ if name is None else name

        if name in self.events:
            try:
                self.events[name].remove(func)
            except ValueError:
                pass

    def add_command(self, name, coro: Coroutine, aliases: list[str] = []):
        self.commands[name] = coro
        for alias in aliases:
            self.commands[alias] = coro

    def command(self, name: str = None, aliases: list[str] = []):
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
            self.add_command(n, func, aliases=aliases)
            return func

        return decorator

    def listen(self, name: str = None):
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
