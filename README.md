# Rocketbotte

A bot for rocketchat messaging, allowing you to react to messages or commands.

It works with rocketchat's realtime api (websocket) to receive messages, and responds with the REST api. To do this, it uses the aiohttp python library.

- [rocketchat api documentation](https://developer.rocket.chat/apidocs/rocketchat-api)
- [rocketchat real time api (websocket)](https://developer.rocket.chat/apidocs/realtimeapi)

## Installation

`pip install rocketbotte`

## Usage

```python
from rocketbotte import Bot, Context, Message

bot = Bot(server_url=SERVER_URL, user_id=USER_ID, auth_token=AUTH_TOKEN)

@bot.command('test')
async def test(ctx:Context, args:str):
    await ctx.send_message(f'response to {args}')

@bot.listen()
async def on_message(message:Message):
    if 'hello' in message.content:
        await bot.send_message(message.room_id, 'world ')

bot.run()
```

### Bot parameters

- server_url: the server url as `https://myrocketchat.org`
- auth_token: the personal authentification token for the bot
- command_prefix: default : '!'
- user_id: the user id who belongs to the authentification token
- max_retry: number of attempt restart after an uncaught exception, default to 5
- max_retry_time: seconds before new attemps of connexion, default to 30
- max_off_time: time in seconds since last ping from server worth a new connection, defaut te 120


## logging

This library use loguru for logging. To see logs explicit ask for by using  `logger.enable("rocketbotte")`