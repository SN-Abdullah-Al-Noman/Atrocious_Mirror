#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex, create
from time import time
from functools import partial
from asyncio import sleep

from bot import bot, user_data, config_dict, DATABASE_URL, OWNER_ID
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata, sync_to_async, new_thread, is_blacklist

handler_dict = {}


async def get_user_settings(from_user):
    if config_dict['SA_MAIL']:
        SA_MAIL = config_dict['SA_MAIL']
    else:
        SA_MAIL = ''
    user_id = from_user.id
    name = from_user.mention
    buttons = ButtonMaker()
    user_dict = user_data.get(user_id, {})

    buttons.ibutton("Users Gdrive ID", f"user_td_set {user_id} users_gdrive_id")
    if user_dict.get('users_gdrive_id'):
        users_gdrive_id = user_dict['users_gdrive_id']
    else:
        users_gdrive_id = ''

    buttons.ibutton("Users Index URl", f"user_td_set {user_id} users_index_url")
    if user_dict.get('users_index_url'):
        users_index_url = user_dict['users_index_url']
    else:
        users_index_url = ''
        
    buttons.ibutton("Close", f"user_td_set {user_id} close")

    text = f"""<u><b>Custom Drive Settings for</b> {name}</u>
\n<b>Your Custom Gdrive ID:</b> <code>{users_gdrive_id}</code></b>
\n<b>Your Custom Index URL:</b> <code>{users_index_url}</code></b>
\n<b>Please add the S.A mail in your share drive as content manager</b>
\n<b>S.A Mail: </b><code>{SA_MAIL}</code>"""

    return text, buttons.build_menu(2)


async def update_user_settings(query):
    msg, button = await get_user_settings(query.from_user)
    await editMessage(query.message, msg, button)


async def user_td_settings(_, message):
    user_id = message.from_user.id
    if await is_blacklist(message):
        return
    if not config_dict['USER_TD_ENABLED']:
        if user_id != OWNER_ID:
            return await message.reply("<b>⚠️ User Team Drive Support Disabled By Owner.</b>")
    from_user = message.from_user
    handler_dict[from_user.id] = False
    msg, button = await get_user_settings(from_user)
    await sendMessage(message, msg, button)


async def set_users_gdrive_idination(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    if value.isdigit() or value.startswith('-'):
        value = int(value)
    update_user_ldata(user_id, 'users_gdrive_id', value)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)


async def set_users_index_idination(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    if value.isdigit() or value.startswith('-'):
        value = int(value)
    update_user_ldata(user_id, 'users_index_url', value)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)


async def event_handler(client, query, pfunc, photo=False, document=False):
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        mtype = event.text
        user = event.from_user or event.sender_chat
        return bool(user.id == user_id and event.chat.id == query.message.chat.id and mtype)

    handler = client.add_handler(MessageHandler(
        pfunc, filters=create(event_filter)), group=-1)

    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await update_user_settings(query)
    client.remove_handler(*handler)


@new_thread
async def edit_user_settings(client, query):
    from_user = query.from_user
    user_id = from_user.id
    message = query.message
    data = query.data.split()
    user_dict = user_data.get(user_id, {})
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == 'users_gdrive_id':
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get('users_gdrive_id', False) or 'users_gdrive_id' not in user_dict:
            buttons.ibutton("Remove Your Gdrive ID",
                            f"user_td_set {user_id} remove_users_gdrive_id")
        buttons.ibutton("Back", f"user_td_set {user_id} back")
        buttons.ibutton("Close", f"user_td_set {user_id} close")
        await editMessage(message, 'Send Your Gdrive ID. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(set_users_gdrive_idination, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == 'remove_users_gdrive_id':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'users_gdrive_id', '')
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'users_index_url':
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get('users_index_url', False) or 'users_index_url' not in user_dict:
            buttons.ibutton("Remove Your Index URL",
                            f"user_td_set {user_id} remove_users_index_url")
        buttons.ibutton("Back", f"user_td_set {user_id} back")
        buttons.ibutton("Close", f"user_td_set {user_id} close")
        await editMessage(message, 'Send Your Index URL. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(set_users_index_idination, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == 'remove_users_index_url':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'users_index_url', '')
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'back':
        handler_dict[user_id] = False
        await query.answer()
        await update_user_settings(query)
    else:
        handler_dict[user_id] = False
        await query.answer()
        await message.reply_to_message.delete()
        await message.delete()


bot.add_handler(MessageHandler(user_td_settings, filters=command(BotCommands.UserTdCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(edit_user_settings, filters=regex("^user_td_set")))
