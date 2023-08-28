from bot import bot
from pyrogram import filters
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler

from asyncio import sleep as asleep
from telegraph import upload_file
from aiofiles.os import remove as aioremove


async def telegraph(client, message):
    if not message.reply_to_message:
        return await message.reply(f"Please reply any photo to upload in telegraph")
    elif message.reply_to_message:
        photo_dir = await message.reply_to_message.download()
        await asleep(1)
        photos_link = f'https://graph.org{upload_file(photo_dir)[0]}'
        await aioremove(photo_dir)
        await message.reply(f"Telegraph Link : {photos_link}")

bot.add_handler(MessageHandler(telegraph, filters=command("tm")))
