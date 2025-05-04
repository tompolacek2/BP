import asyncio
from telegram import Bot

class TelegramConnector:
    def __init__(self, token: str = "7875506886:AAFuzKroDUcKdZhazzPgqyG-IAWqzm7xhHE"):
        self.token = token

    def send_message(self, chat_id: int, text: str):
        # 1) vytvoříme nový loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 2) Bot i session teď vznikají v tomto loopu
        bot = Bot(token=self.token)

        # 3) spustíme poslání a uzavření session
        resp = loop.run_until_complete(bot.send_message(chat_id=chat_id, text=text))
        loop.run_until_complete(bot.close())

        # 4) loop můžeme zavřít, protože ho už dál nepotřebujeme
        loop.close()

        print("OK, vrátilo:", resp)
        return True