from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

from bot import bot, config_dict, DATABASE_URL, OWNER_ID, user_data


async def get_user_info(client, message):
    user_id = message.from_user.id
    user = await client.get_users(user_id)
    info = f"User ID: {user.id}\n"
    info += f"Username: @{user.username}\n"
    info += f"First Name: {user.first_name}\n"
    info += f"Last Name: {user.last_name}\n"
    info += f"Is Bot: {user.is_bot}"
    
    await message.reply_text(info)

bot.add_handler(MessageHandler(get_user_info, filters=command(info))
