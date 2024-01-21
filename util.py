import asyncio
import telegram

telegram_api_token = '<TELEGRAM_API_TOKEN>'


async def print_self(bot: telegram.Bot):
    print(await bot.get_me())

async def print_messages(bot: telegram.Bot):
    updates = await bot.get_updates()
    for update in updates:
        print(update.message)

async def send_message(bot: telegram.Bot, chat_id, text):
    async with bot:
        await bot.send_message(chat_id=chat_id, text=text)
    print(f'sent message to {chat_id}')

async def main():
    bot = telegram.Bot(telegram_api_token)

    # await print_self(bot)
    # await print_messages(bot)
    # await send_message(bot, 123456789, 'Willkommen auf der ICMS-Watcher Subscriber Liste :) (keine Haftung für Herzinfakte, Falschmeldungen etc.)')
    print(await bot.getChat(123456789))


if __name__ == '__main__':
    asyncio.run(main())
