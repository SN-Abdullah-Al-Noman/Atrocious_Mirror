#!/usr/bin/env python3
from secrets import token_urlsafe

from bot import download_dict, download_dict_lock, LOGGER
from bot.helper.mirror_utils.gdrive_utlis.download import gdDownload
from bot.helper.mirror_utils.gdrive_utlis.count import gdCount
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.atrocious_utils import check_filename, limit_checker, stop_duplicate_check, stop_duplicate_leech


async def add_gd_download(link, path, listener, newname):
    drive = gdCount()
    name, mime_type, size, _, _ = await sync_to_async(drive.count, link, listener.user_id)
    if mime_type is None:
        await sendMessage(listener.message, name)
        return

    name = newname or name
    gid = token_urlsafe(12)

    if msg := await check_filename(name):
        warn = f"Hey {listener.tag}.\n\n{msg}"
        await sendMessage(listener.message, warn)
        return

    msg = await stop_duplicate_leech(name, size, listener)
    if msg:
        warn = f"Hey {listener.tag}.\n\n{msg}"
        await sendMessage(listener.message, warn)
        return

    msg, button = await stop_duplicate_check(name, listener)
    if msg:
        warn = f"Hey {listener.tag}.\n\n{msg}"
        await sendMessage(listener.message, warn, button)
        return

    limit_exceeded, button = await limit_checker(size, listener, isDriveLink=True)
    if limit_exceeded:
        msg = f"Hey {listener.tag}.\n\n{limit_exceeded}"
        await sendMessage(listener.message, msg, button)
        return

    drive = gdDownload(name, path, listener)
    async with download_dict_lock:
        download_dict[listener.uid] = GdriveStatus(drive, size, listener.message, gid, 'dl')
        LOGGER.info(f"Download from GDrive: {name}")
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)

    await sync_to_async(drive.download, link)
