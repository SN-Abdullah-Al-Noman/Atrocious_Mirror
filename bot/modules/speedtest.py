from pyrogram import filters
from subprocess import run as srun
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler

from bot import bot, CMD_SUFFIX

async def speed_test(client, message):
    try:
        from speedtest import Speedtest
    except ImportError:
        await message.reply(f"Speedtest pypi is not installed. Now installing it.")
        srun(['pip3', 'install', 'speedtest-cli'])
        from speedtest import Speedtest
    st = Speedtest()
    download_speed = st.download() / 1_000_000 / 8
    upload_speed = st.upload() / 1_000_000 / 8
    msg = f"<b>Speedtest Result.</b>"
    msg += f"\n\n<b>• Download Speed:</b> {download_speed:.2f} Mbps"
    msg += f"\n<b>• Upload Speed:</b> {upload_speed:.2f} Mbps"
    await message.reply(msg)

bot.add_handler(MessageHandler(speed_test, filters=command(f"speedtest{CMD_SUFFIX}")))
