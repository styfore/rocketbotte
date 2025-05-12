import asyncio, time
from loguru import logger
from datetime import datetime




mess = []
def listen_message():
    global mess
    while True:
        m = input()
        d = datetime.now()
        logger.debug(d)
        if m is not None and len(m.strip()) > 0:
            mess.append({'msg':m, 'date':d})



async def get_messages(last_update):
    global mess
    l =  list(filter(lambda m: m['date'] > last_update, mess))
    await asyncio.sleep(0.2)
    return l


async def main(delay=1):
    last_update = datetime.now()
    task = asyncio.create_task(asyncio.to_thread(listen_message))
    while True:
        messages = await get_messages(last_update)
        if len(messages) > 0:
            last_update = max([m['date'] for m in messages])
        for msg in messages:
            if '!test' in msg['msg']:
                logger.info(f'commande Test sur {msg}')
            else :
                logger.warning(f'message {msg} non traité')
        time.sleep(delay)     






asyncio.run(main())
