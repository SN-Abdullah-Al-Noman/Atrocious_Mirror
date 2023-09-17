#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command

from bot import user_data, DATABASE_URL, bot, OWNER_ID
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata


async def authorize(client, message):
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    else:
        id_ = message.chat.id
    if id_ in user_data and user_data[id_].get('is_auth'):
        msg = 'Already Authorized!'
    else:
        update_user_ldata(id_, 'is_auth', True)
        if DATABASE_URL:
            await DbManger().update_user_data(id_)
        msg = 'Authorized'
    await sendMessage(message, msg)


async def unauthorize(client, message):
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    else:
        id_ = message.chat.id
    if id_ not in user_data or user_data[id_].get('is_auth'):
        update_user_ldata(id_, 'is_auth', False)
        if DATABASE_URL:
            await DbManger().update_user_data(id_)
        msg = 'Unauthorized'
    else:
        msg = 'Already Unauthorized!'
    await sendMessage(message, msg)


async def addSudo(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ in user_data and user_data[id_].get('is_sudo'):
            msg = 'Already Sudo!'
        else:
            update_user_ldata(id_, 'is_sudo', True)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'Promoted as Sudo'
    else:
        msg = "Give ID or Reply To message of whom you want to Promote."
    await sendMessage(message, msg)


async def removeSudo(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_ and id_ not in user_data or user_data[id_].get('is_sudo'):
        update_user_ldata(id_, 'is_sudo', False)
        if DATABASE_URL:
            await DbManger().update_user_data(id_)
        msg = 'Demoted from sudo'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from Sudo"
    await sendMessage(message, msg)


async def add_to_good_friend(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner.'
        elif id_ in user_data and user_data[id_].get('is_good_friend'):
            msg = 'User already in good friend list.'
        else:
            update_user_ldata(id_, 'is_good_friend', True)
            update_user_ldata(id_, 'is_blacklist', False)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'User added in good friend list.\nFrom now token system will skip for him.'
    else:
        msg = "Give ID or Reply To message of whom you want to add in good friend list."
    await sendMessage(message, msg)


async def remove_from_good_friend(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner.'
        elif id_ in user_data or user_data[id_].get('is_good_friend'):
            update_user_ldata(id_, 'is_good_friend', False)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'User removed from good friend list.'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from good friend list."
    await sendMessage(message, msg)


async def add_to_blacklist(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner'
        elif id_ in user_data and user_data[id_].get('is_blacklist'):
            msg = 'User already in blacklist.'
        else:
            update_user_ldata(id_, 'is_blacklist', True)
            update_user_ldata(id_, 'is_good_friend', False)
            update_user_ldata(id_, 'is_paid_user', False)
            update_user_ldata(id_, 'is_sudo', False)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'User added in blacklist.'
    else:
        msg = "Give ID or Reply To message of whom you want to add in blacklist."
    await sendMessage(message, msg)


async def remove_from_blacklist(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner'
        elif id_ not in user_data and user_data[id_].get('is_blacklist'):
            msg = 'User not in blacklist.'
        else:
            update_user_ldata(id_, 'is_blacklist', False)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'User removed from blacklist.'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from blacklist."
    await sendMessage(message, msg)


async def add_to_paid_user(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner.'
        elif id_ in user_data and user_data[id_].get('is_paid_user'):
            msg = 'User already in paid user list.'
        else:
            update_user_ldata(id_, 'is_paid_user', True)
            update_user_ldata(id_, 'is_blacklist', False)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'User added in paid user list.\nFrom now token system and some limit will skip for him.'
    else:
        msg = "Give ID or Reply To message of whom you want to add in paid user list."
    await sendMessage(message, msg)


async def remove_from_paid_user(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner'
        elif id_ not in user_data and user_data[id_].get('is_paid_user'):
            msg = 'User not in paid user list.'
        else:
            update_user_ldata(id_, 'is_paid_user', False)
            if DATABASE_URL:
                await DbManger().update_user_data(id_)
            msg = 'User removed from paid user list.'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from paid user list."
    await sendMessage(message, msg)


bot.add_handler(MessageHandler(authorize, filters=command(BotCommands.AuthorizeCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(unauthorize, filters=command(BotCommands.UnAuthorizeCommand) & CustomFilters.sudo))

bot.add_handler(MessageHandler(add_to_blacklist, filters=(command("addblacklist") & CustomFilters.sudo)))
bot.add_handler(MessageHandler(remove_from_blacklist, filters=(command("rmblacklist") & CustomFilters.sudo)))

bot.add_handler(MessageHandler(add_to_good_friend, filters=(command("addgdf") & CustomFilters.sudo)))
bot.add_handler(MessageHandler(remove_from_good_friend, filters=(command("rmgdf") & CustomFilters.sudo)))

bot.add_handler(MessageHandler(addSudo, filters=command(BotCommands.AddSudoCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(removeSudo, filters=command(BotCommands.RmSudoCommand) & CustomFilters.sudo))

bot.add_handler(MessageHandler(add_to_paid_user, filters=(command("addpaid") & CustomFilters.sudo)))
bot.add_handler(MessageHandler(remove_from_paid_user, filters=(command("rmpaid") & CustomFilters.sudo)))
