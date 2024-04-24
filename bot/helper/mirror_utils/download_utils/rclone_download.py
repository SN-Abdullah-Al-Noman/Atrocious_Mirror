#!/usr/bin/env python3
from asyncio import gather
from json import loads
from secrets import token_urlsafe

from bot import download_dict, download_dict_lock, LOGGER
from bot.helper.ext_utils.bot_utils import cmd_exec
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.task_manager import is_queued
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.ext_utils.atrocious_utils import check_filename, stop_duplicate_check


async def add_rclone_download(rc_path, config_path, path, name, listener):
    remote, rc_path = rc_path.split(':', 1)
    rc_path = rc_path.strip('/')

    cmd1 = ['rclone', 'lsjson', '--fast-list', '--stat', '--no-mimetype',
            '--no-modtime', '--config', config_path, f'{remote}:{rc_path}']
    cmd2 = ['rclone', 'size', '--fast-list', '--json',
            '--config', config_path, f'{remote}:{rc_path}']
    res1, res2 = await gather(cmd_exec(cmd1), cmd_exec(cmd2))
    if res1[2] != res2[2] != 0:
        if res1[2] != -9:
            err = res1[1] or res2[1]
            msg = f'Error: While getting rclone stat/size. Path: {remote}:{rc_path}. Stderr: {err[:4000]}'
            await sendMessage(listener.message, msg)
        return
    try:
        rstat = loads(res1[0])
        rsize = loads(res2[0])
    except Exception as err:
        await sendMessage(listener.message, f'RcloneDownload JsonLoad: {err}')
        return
    if rstat['IsDir']:
        if not name:
            name = rc_path.rsplit('/', 1)[-1] if rc_path else remote
        path += name
    else:
        name = rc_path.rsplit('/', 1)[-1]
    size = rsize['bytes']
    gid = token_urlsafe(12)

    if msg := await check_filename(name):
        warn = f"Hey {listener.tag}.\n\n{msg}"
        await sendMessage(listener.message, msg)
        return
        
    msg, button = await stop_duplicate_check(name, listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        return

    RCTransfer = RcloneTransferHelper(listener, name)
    async with download_dict_lock:
        download_dict[listener.uid] = RcloneStatus(RCTransfer, listener.message, gid, 'dl')
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
        LOGGER.info(f"Download with rclone: {rc_path}")

    await RCTransfer.download(remote, rc_path, config_path, path)
