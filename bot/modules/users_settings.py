from pyrogram import Client, filters
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot


async def keyboard(client, message):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Close", callback_data="close")]])
    await message.reply_text("Hello! Press the Close button to close the keyboard.", reply_markup=keyboard)


@bot.on_callback_query()
async def callback_handler(client, query):
    if query.data == "close":
        await query.message.edit_reply_markup(None)

bot.add_handler(MessageHandler(keyboard, filters=command("usertmd")))
