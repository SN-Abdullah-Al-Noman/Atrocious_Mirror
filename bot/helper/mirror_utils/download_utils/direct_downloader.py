#!/usr/bin/env python3
from secrets import token_urlsafe

from bot import LOGGER, aria2_options, aria2c_global, download_dict, download_dict_lock
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.task_manager import is_queued
from bot.helper.listeners.direct_listener import DirectListener
from bot.helper.mirror_utils.status_utils.direct_status import DirectStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.atrocious_utils import stop_duplicate_check


async def add_direct_download(details, path, listener, foldername):
    if not (contents:= details.get('contents')):
        await sendMessage(listener.message, 'There is nothing to download!')
        return
    size = details['total_size']

    if foldername:
        path = f'{path}/{foldername}'

    if not foldername:
        foldername = details['title']
    msg, button = await stop_duplicate_check(foldername, listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        return

    gid = token_urlsafe(10)
    a2c_opt = {**aria2_options}
    [a2c_opt.pop(k) for k in aria2c_global if k in aria2_options]
    if header:= details.get('header'):
        a2c_opt['header'] = header
    a2c_opt['follow-torrent'] = 'false'
    a2c_opt['follow-metalink'] = 'false'
    directListener = DirectListener(foldername, size, path, listener, a2c_opt)
    async with download_dict_lock:
        download_dict[listener.uid] = DirectStatus(directListener, gid, listener)
        LOGGER.info(f"Download from Direct Download: {foldername}")
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)

    await sync_to_async(directListener.download, contents
