import asyncio
from pyrogram import Client, filters
from datetime import datetime

from bot import bot

@bot.on_message(filters.new_chat_members)
async def welcome(client, message):
    for new_member in message.new_chat_members:
        member_name = new_member.first_name if new_member.first_name else "there"
        user_name = f"@{new_member.username}" if new_member.username else ""
        user_id = new_member.id
        now = datetime.now()
        join_date = now.strftime("%Y-%m-%d")
        join_time = now.strftime("%I:%M:%S %p")
        chat_members_count = await client.get_chat_members_count(message.chat.id)
        msg = f"Hlw {member_name} {user_name}\n"
        msg += f"Your ID: <code>{user_id}</code>\n"
        msg += f"Join date: {join_date}\n"
        msg += f"Join time: {join_time}\n"
        msg += f"Member number: {chat_members_count}"
        await message.reply_text(msg)
