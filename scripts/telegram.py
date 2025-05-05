import asyncio
from telegram import Bot

class TelegramConnector:
    def __init__(self, token: str = ""):
        self.token = token

    def send_message(self, chat_id: int, text: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        bot = Bot(token=self.token)

        resp = loop.run_until_complete(bot.send_message(chat_id=chat_id, text=text))
        loop.run_until_complete(bot.close())

        loop.close()

        print("OK, vrátilo:", resp)
        return True
