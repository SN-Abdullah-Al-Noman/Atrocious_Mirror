from pyrogram import filters
from telegraph import upload_file
from asyncio import sleep as asleep
from pyrogram.filters import command
from aiofiles.os import remove as aioremove
from pyrogram.handlers import MessageHandler

from bot import bot
from bot.helper.telegram_helper.filters import CustomFilters


async def telegraph(client, message):
    if not message.reply_to_message:
        return await message.reply(f"Please reply any photo to upload in telegraph")
    elif message.reply_to_message:
        photo_dir = await message.reply_to_message.download()
        await asleep(1)
        photos_link = f'https://graph.org{upload_file(photo_dir)[0]}'
        await aioremove(photo_dir)
        await message.reply(f"Telegraph Link : {photos_link}")


bot.add_handler(MessageHandler(telegraph, filters=command("tm") & CustomFilters.sudo))
