from re import match as rematch
from telegram import Message
from telegram.ext import CommandHandler

from bot import LOGGER, dispatcher, config_dict
from bot.helper.ext_utils.shortenurl import short_url
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage

def wayback(update, context):
    message:Message = update.effective_message
    reply_to = update.message.reply_to_message
    if update.message.from_user.username:
        tag = f"@{update.message.from_user.username}"
    else:
        tag = update.message.from_user.mention_html(update.message.from_user.first_name)

    if reply_to and reply_to.from_user:
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)
            
    longurl = None
    if message.reply_to_message: longurl = message.reply_to_message.text
    else:
        longurl = message.text.split(' ', 1)
        if len(longurl) != 2:
            help_msg = "<b>Send your url after command:</b>"
            help_msg += f"\n<code>/{BotCommands.WayBackCommand}" + " {longurl}" + "</code>"
            help_msg += "\n<b>By replying to message (including url):</b>"
            help_msg += f"\n<code>/{BotCommands.WayBackCommand}" + " {message}" + "</code>"
            return sendMessage(help_msg, context.bot, update.message)
        longurl = longurl[1]
    try: longurl = rematch(r"((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*", longurl)[0]
    except TypeError: return sendMessage('Not a valid url.', context.bot, update)
    shortened_url = short_url(f'{longurl}')
    update.message.reply_text(f'Hey {tag} here is your short url\n\n{shortened_url}')

authfilter = CustomFilters.authorized_chat if config_dict['WAYBACK_ENABLED'] is True else CustomFilters.owner_filter
wayback_handler = CommandHandler(BotCommands.WayBackCommand, wayback, filters=authfilter | CustomFilters.authorized_user)

dispatcher.add_handler(wayback_handler)