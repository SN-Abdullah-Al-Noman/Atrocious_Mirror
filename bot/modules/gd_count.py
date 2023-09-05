#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command

from bot import bot
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import deleteMessage, sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import is_gdrive_link, sync_to_async, new_task, get_readable_file_size 


@new_task
async def countNode(_, message):
    args = message.text.split()
    if username := message.from_user.username:
            tag = f"@{username}"
    else:
        tag = message.from_user.mention

    link = args[1] if len(args) > 1 else ''
    if len(link) == 0 and (reply_to := message.reply_to_message):
        link = reply_to.text.split(maxsplit=1)[0].strip()

    if is_gdrive_link(link):
        msg = await sendMessage(message, f"Counting: <code>{link}</code>")
        gd = GoogleDriveHelper()
        name, mime_type, size, files, folders = await sync_to_async(gd.count, link)
        if mime_type is None:
            await sendMessage(message, name)
            return
        await deleteMessage(msg)
        msg = f'<b>Name: </b><code>{name}</code>'
        msg += f'\n\n<b>• Size: </b>{get_readable_file_size(size)}'
        msg += f'\n<b>• Type: </b>{mime_type}'
        if mime_type == 'Folder':
            msg += f'\n\n<b>• SubFolders: </b>{folders}'
            msg += f'\n<b>• Files: </b>{files}'
        msg += f'\n\n<b>• User: </b>{tag}'
    else:
        msg = 'Send Gdrive link along with command or by replying to the link by command'

    await sendMessage(message, msg)


bot.add_handler(MessageHandler(countNode, filters=command(
    BotCommands.CountCommand) & CustomFilters.authorized))



from bot import bot, config_dict
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

@bot.on_callback_query()
async def callback_handler(client, CallbackQuery):
    limit_msg = f"Clone Limit: {config_dict['CLONE_LIMIT']} GB\n"
    limit_msg += f"Gdrive Limit: {config_dict['GDRIVE_LIMIT']} GB\n"
    limit_msg += f"Leech Limit: {config_dict['LEECH_LIMIT']} GB\n"
    limit_msg += f"Mega Limit: {config_dict['MEGA_LIMIT']} GB\n"
    limit_msg += f"Mirror Limit: {config_dict['MIRROR_LIMIT']} GB\n"
    limit_msg += f"Storage Threshold: {config_dict['STORAGE_THRESHOLD']} GB\n"
    limit_msg += f"Torrent Limit: {config_dict['TORRENT_LIMIT']} GB\n"
    limit_msg += f"Ytdlp Limit: {config_dict['YTDLP_LIMIT']} GB\n"
    await CallbackQuery.answer(text=limit_msg, show_alert=True)


async def show_limits(client, message):
    limit_button = InlineKeyboardMarkup([[InlineKeyboardButton("See Limits", callback_data="msg")]])
    await message.reply("Click the button to see limits.", reply_markup=limit_button)


bot.add_handler(MessageHandler(show_limits, filters=command("limits")))
