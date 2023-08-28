#!/usr/bin/env python3
from re import match as re_match
from time import time
from html import escape
from uuid import uuid4
from base64 import b64encode
from psutil import virtual_memory, cpu_percent, disk_usage
from asyncio import create_subprocess_exec, create_subprocess_shell, run_coroutine_threadsafe, sleep
from asyncio.subprocess import PIPE
from functools import partial, wraps
from concurrent.futures import ThreadPoolExecutor
from aiohttp import ClientSession
from pyrogram.types import BotCommand

from bot import download_dict, download_dict_lock, botStartTime, user_data, config_dict, bot_loop, OWNER_ID, bot_name
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.ext_utils.shortener import short_url

THREADPOOL = ThreadPoolExecutor(max_workers=1000)

MAGNET_REGEX = r'magnet:\?xt=urn:(btih|btmh):[a-zA-Z0-9]*\s*'

URL_REGEX = r'^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$'

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

STATUS_START = 0
PAGES = 1
PAGE_NO = 1


class MirrorStatus:
    STATUS_UPLOADING = "Upload"
    STATUS_DOWNLOADING = "Download"
    STATUS_CLONING = "Clone"
    STATUS_QUEUEDL = "QueueDl"
    STATUS_QUEUEUP = "QueueUp"
    STATUS_PAUSED = "Pause"
    STATUS_ARCHIVING = "Archive"
    STATUS_EXTRACTING = "Extract"
    STATUS_SPLITTING = "Split"
    STATUS_CHECKING = "CheckUp"
    STATUS_SEEDING = "Seed"


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.task = bot_loop.create_task(self.__set_interval())

    async def __set_interval(self):
        while True:
            await sleep(self.interval)
            await self.action()

    def cancel(self):
        self.task.cancel()


def get_readable_file_size(size_in_bytes):
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    return f'{size_in_bytes:.2f}{SIZE_UNITS[index]}' if index > 0 else f'{size_in_bytes}B'


async def getDownloadByGid(gid):
    async with download_dict_lock:
        return next((dl for dl in download_dict.values() if dl.gid() == gid), None)


async def getAllDownload(req_status, user_id=None):
    dls = []
    async with download_dict_lock:
        for dl in list(download_dict.values()):
            if user_id and user_id != dl.message.from_user.id:
                continue
            status = dl.status()
            if req_status in ['all', status]:
                dls.append(dl)
    return dls


def bt_selection_buttons(id_):
    gid = id_[:12] if len(id_) > 20 else id_
    pincode = ''.join([n for n in id_ if n.isdigit()][:4])
    buttons = ButtonMaker()
    BASE_URL = config_dict['BASE_URL']
    if config_dict['WEB_PINCODE']:
        buttons.ubutton("Select Files", f"{BASE_URL}/app/files/{id_}")
        buttons.ibutton("Pincode", f"btsel pin {gid} {pincode}")
    else:
        buttons.ubutton(
            "Select Files", f"{BASE_URL}/app/files/{id_}?pin_code={pincode}")
    buttons.ibutton("Done Selecting", f"btsel done {gid} {id_}")
    return buttons.build_menu(2)


async def get_telegraph_list(telegraph_content):
    path = [(await telegraph.create_page(title='Mirror-Leech-Bot Drive Search', content=content))["path"] for content in telegraph_content]
    if len(path) > 1:
        await telegraph.edit_telegraph(path, telegraph_content)
    buttons = ButtonMaker()
    buttons.ubutton("🔎 VIEW", f"https://telegra.ph/{path[0]}")
    return buttons.build_menu(1)


def get_progress_bar_string(pct):
    pct = float(pct.strip('%'))
    p = min(max(pct, 0), 100)
    cFull = int(p // 10)
    p_str = '■' * cFull
    p_str += '□' * (10 - cFull)
    return f"[{p_str}]"


def get_readable_message():
    msg = ""
    button = None
    STATUS_LIMIT = config_dict['STATUS_LIMIT']
    tasks = len(download_dict)
    globals()['PAGES'] = (tasks + STATUS_LIMIT - 1) // STATUS_LIMIT
    if PAGE_NO > PAGES and PAGES != 0:
        globals()['STATUS_START'] = STATUS_LIMIT * (PAGES - 1)
        globals()['PAGE_NO'] = PAGES
    for download in list(download_dict.values())[STATUS_START:STATUS_LIMIT+STATUS_START]:
        if config_dict['SAFE_MODE']:
            msg += f"<b>{download.status()}: </b>Safe Mode Enabled"
        else:
            msg += f"<b><a href='{download.message.link}'>{download.status()}</a>: </b>"
            msg += f"<code>{escape(f'{download.name()}')}</code>"
        if download.status() not in [MirrorStatus.STATUS_SPLITTING, MirrorStatus.STATUS_SEEDING]:
            msg += f"\n{get_progress_bar_string(download.progress())} {download.progress()}"
            msg += f"\n<b>Speed: </b>{download.speed()}"
            msg += f"\n<b>Done: </b>{download.processed_bytes()} of {download.size()}"
            msg += f"\n<b>ETA: </b>{download.eta()} <b>| Elapsed: </b>{get_readable_time(time() - download.message.date.timestamp())}"
            msg += f"\n<b>Engine: </b>{download.engine}"
            msg += f"\n<b>User: </b>{download.message.from_user.mention(style='html')} | <b>ID: </b><code>{download.message.from_user.id}</code>"
            if hasattr(download, 'seeders_num'):
                try:
                    msg += f"\n<b>Seeders:</b> {download.seeders_num()} | <b>Leechers:</b> {download.leechers_num()}"
                except:
                    pass
        elif download.status() == MirrorStatus.STATUS_SEEDING:
            msg += f"\n<b>Size: </b>{download.size()}"
            msg += f"\n<b>Speed: </b>{download.upload_speed()}"
            msg += f" | <b>Uploaded: </b>{download.uploaded_bytes()}"
            msg += f"\n<b>Ratio: </b>{download.ratio()}"
            msg += f" | <b>Time: </b>{download.seeding_time()}"
        else:
            msg += f"\n<b>Size: </b>{download.size()}"
        msg += f"\n<b>Stop: </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n\n"
    if len(msg) == 0:
        return None, None
    dl_speed = 0
    up_speed = 0
    for download in download_dict.values():
        tstatus = download.status()
        if tstatus == MirrorStatus.STATUS_DOWNLOADING:
            spd = download.speed()
            if 'K' in spd:
                dl_speed += float(spd.split('K')[0]) * 1024
            elif 'M' in spd:
                dl_speed += float(spd.split('M')[0]) * 1048576
        elif tstatus == MirrorStatus.STATUS_UPLOADING:
            spd = download.speed()
            if 'K' in spd:
                up_speed += float(spd.split('K')[0]) * 1024
            elif 'M' in spd:
                up_speed += float(spd.split('M')[0]) * 1048576
        elif tstatus == MirrorStatus.STATUS_SEEDING:
            spd = download.upload_speed()
            if 'K' in spd:
                up_speed += float(spd.split('K')[0]) * 1024
            elif 'M' in spd:
                up_speed += float(spd.split('M')[0]) * 1048576
    msg += f"_______________________________"
    buttons = ButtonMaker()
    buttons.ubutton(f"Repo", f"https://github.com/SN-Abdullah-Al-Noman/Atrocious_Mirror")
    buttons.ibutton("Refresh", "status ref")
    buttons.ubutton(f"Group", f"https://t.me/+yw0A-x4cYBphZmJl")
    button = buttons.build_menu(3)
    if tasks > STATUS_LIMIT:
        buttons = ButtonMaker()
        buttons.ibutton("Previous", "status pre")
        buttons.ibutton("Refresh", "status ref")
        buttons.ibutton("Next", "status nex")
        button = buttons.build_menu(3)
    if config_dict['BOT_MAX_TASKS']:
        TASKS_COUNT = f"\n<b>Task Limit: </b>{config_dict['BOT_MAX_TASKS']} | <b>Run:</b> {len(download_dict)} | <b>Free:</b> {config_dict['BOT_MAX_TASKS'] - len(download_dict)}\n"
    else:
        TASKS_COUNT = f"<b>Tasks Running:</b> {len(download_dict)}\n"
    msg += f"{TASKS_COUNT}"
    msg += f"<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {get_readable_file_size(disk_usage(config_dict['DOWNLOAD_DIR']).free)}"
    msg += f"\n<b>RAM:</b> {virtual_memory().percent}% | <b>UP:</b> {get_readable_time(time() - botStartTime)}"
    msg += f"\n<b>DL:</b> {get_readable_file_size(dl_speed)}/s | <b>UL:</b> {get_readable_file_size(up_speed)}/s"
    return msg, button


async def turn_page(data):
    STATUS_LIMIT = config_dict['STATUS_LIMIT']
    global STATUS_START, PAGE_NO
    async with download_dict_lock:
        if data[1] == "nex":
            if PAGE_NO == PAGES:
                STATUS_START = 0
                PAGE_NO = 1
            else:
                STATUS_START += STATUS_LIMIT
                PAGE_NO += 1
        elif data[1] == "pre":
            if PAGE_NO == 1:
                STATUS_START = STATUS_LIMIT * (PAGES - 1)
                PAGE_NO = PAGES
            else:
                STATUS_START -= STATUS_LIMIT
                PAGE_NO -= 1


def get_readable_time(seconds):
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result


def is_magnet(url):
    return bool(re_match(MAGNET_REGEX, url))


def is_url(url):
    return bool(re_match(URL_REGEX, url))


def is_gdrive_link(url):
    return "drive.google.com" in url


def is_telegram_link(url):
    return url.startswith(('https://t.me/', 'tg://openmessage?user_id='))


def is_share_link(url):
    return bool(re_match(r'https?:\/\/.+\.gdtot\.\S+|https?:\/\/(filepress|filebee|appdrive|gdflix)\.\S+', url))


def is_mega_link(url):
    return "mega.nz" in url or "mega.co.nz" in url


def is_rclone_path(path):
    return bool(re_match(r'^(mrcc:)?(?!magnet:)(?![- ])[a-zA-Z0-9_\. -]+(?<! ):(?!.*\/\/).*$|^rcl$', path))


def get_mega_link_type(url):
    return "folder" if "folder" in url or "/#F!" in url else "file"


def arg_parser(items, arg_base):
    if not items:
        return arg_base
    bool_arg_set = {'-b', '-e', '-z', '-s', '-j', '-d'}
    t = len(items)
    i = 0
    arg_start = -1

    while i + 1 <= t:
        part = items[i].strip()
        if part in arg_base:
            if arg_start == -1:
                arg_start = i
            if i + 1 == t and part in bool_arg_set or part in ['-s', '-j']:
                arg_base[part] = True
            else:
                sub_list = []
                for j in range(i + 1, t):
                    item = items[j].strip()
                    if item in arg_base:
                        if part in bool_arg_set and not sub_list:
                            arg_base[part] = True
                        break
                    sub_list.append(item.strip())
                    i += 1
                if sub_list:
                    arg_base[part] = " ".join(sub_list)
        i += 1

    link = []
    if items[0].strip() not in arg_base:
        if arg_start == -1:
            link.extend(item.strip() for item in items)
        else:
            link.extend(items[r].strip() for r in range(arg_start))
        if link:
            arg_base['link'] = " ".join(link)
    return arg_base


async def get_content_type(url):
    try:
        async with ClientSession(trust_env=True) as session:
            async with session.get(url, verify_ssl=False) as response:
                return response.headers.get('Content-Type')
    except:
        return None


def update_user_ldata(id_, key, value):
    user_data.setdefault(id_, {})
    user_data[id_][key] = value


async def cmd_exec(cmd, shell=False):
    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()
    return stdout, stderr, proc.returncode


def new_task(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return bot_loop.create_task(func(*args, **kwargs))
    return wrapper


async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREADPOOL, pfunc)
    return await future if wait else future


def async_to_sync(func, *args, wait=True, **kwargs):
    future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
    return future.result() if wait else future


def new_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future
    return wrapper


async def get_user_tasks(user_id, maxtask):
    if tasks := await getAllDownload('all', user_id):
        return len(tasks) >= maxtask


def checking_access(message, button=None):
    user_id = message.from_user.id
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if user_id in user_data and user_data[user_id].get('is_blacklist'):
        if button is None:
            button = ButtonMaker()
        button.ubutton('Contact with bot owner', 'https://t.me/ItsBitDefender')
        return f"<b>Hey {tag}.</b>\n<b>User Id: </b><code>{user_id}</code>.\n\n<b>You are blacklisted ⚠️.</b>\n\n<b>Possible Reasons:</b>\n<b>1:</b> Mirror or Leech P*r*n Video.\n<b>2:</b> Mirror or Leech illegal files.\n\nClick the button for chat with bot owner to remove yourself from blacklist.", button
    elif config_dict['ONLY_PAID_SERVICE'] and not (user_id == OWNER_ID or (user_id in user_data and (user_data[user_id].get('is_sudo') or user_data[user_id].get('is_good_friend') or user_data[user_id].get('is_paid_user')))):
        if button is None:
            button = ButtonMaker()
        button.ubutton('Contact with bot owner', 'https://t.me/ItsBitDefender')
        return f"<b>Sorry, {tag} you are not paid user.</b>\n\nThis bot is only for paid users.\nYou need to pay monthly 20 Taka or 20 Rupee for use this bot.\n\nClick the button for chat with bot owner for paid membership.", button
    elif not config_dict['TOKEN_TIMEOUT'] or bool(user_id == OWNER_ID or user_id in user_data and user_data[user_id].get('is_sudo') or user_id in user_data and user_data[user_id].get('is_good_friend') or user_id in user_data and user_data[user_id].get('is_paid_user')):
        return None, button
    user_data.setdefault(user_id, {})
    data = user_data[user_id]
    expire = data.get('time')
    isExpired = (expire is None or expire is not None and (
        time() - expire) > config_dict['TOKEN_TIMEOUT'])
    if isExpired:
        token = data['token'] if expire is None and 'token' in data else str(
            uuid4())
        if expire is not None:
            del data['time']
        data['token'] = token
        user_data[user_id].update(data)
        if button is None:
            button = ButtonMaker()
        button.ubutton('Generate Token', short_url(
            f'https://t.me/{bot_name}?start={token}'))
        return f"Dear {tag} your Ads token is expired, generate your token and try again.\n\n<b>Token Timeout:</b> {get_readable_time(int(config_dict['TOKEN_TIMEOUT']))}.\n\n<b>What is token?</b>\nThis is an ads token. If you pass 1 ad, you can use the bot for {get_readable_time(int(config_dict['TOKEN_TIMEOUT']))} after passing the ad.\n\n<b>Token Generate Video Tutorial:</b> ⬇️\nhttps://t.me/AtrociousMirrorBackup/116", button
    return None, button
    

def get_gdrive_id(user_id):
    user_dict = user_data.get(user_id, {})
    if config_dict['USER_TD_ENABLED'] and user_dict.get('users_gdrive_id'):
        GDRIVE_ID = user_dict['users_gdrive_id']
    else:
        GDRIVE_ID = config_dict['GDRIVE_ID']  
    return GDRIVE_ID


def get_index_url(user_id):
    user_dict = user_data.get(user_id, {})
    if config_dict['USER_TD_ENABLED'] and user_dict.get('users_gdrive_id') and user_dict.get('users_index_url'):
        INDEX_URL = user_dict['users_index_url']
    else:
        INDEX_URL = config_dict['INDEX_URL']  
    return INDEX_URL


async def set_commands(client):
    if config_dict['SET_COMMANDS']:
        await client.set_bot_commands([
        BotCommand(f'{BotCommands.MirrorCommand[0]}', f'or /{BotCommands.MirrorCommand[1]} Mirror'),
        BotCommand(f'{BotCommands.LeechCommand[0]}', f'or /{BotCommands.LeechCommand[1]} Leech'),
        BotCommand(f'{BotCommands.QbMirrorCommand[0]}', f'or /{BotCommands.QbMirrorCommand[1]} Mirror torrent using qBittorrent'),
        BotCommand(f'{BotCommands.QbLeechCommand[0]}', f'or /{BotCommands.QbLeechCommand[1]} Leech torrent using qBittorrent'),
        BotCommand(f'{BotCommands.YtdlCommand[0]}', f'or /{BotCommands.YtdlCommand[1]} Mirror yt-dlp supported link'),
        BotCommand(f'{BotCommands.YtdlLeechCommand[0]}', f'or /{BotCommands.YtdlLeechCommand[1]} Leech through yt-dlp supported link'),
        BotCommand(f'{BotCommands.CloneCommand[0]}', 'Copy file/folder to Drive'),
        BotCommand(f'{BotCommands.CountCommand}', '[drive_url]: Count file/folder of Google Drive.'),
        BotCommand(f'{BotCommands.StatusCommand[0]}', f'or /{BotCommands.StatusCommand[1]} Get mirror status message'),
        BotCommand(f'{BotCommands.StatsCommand}', f'Check Bot & System stats'),
        BotCommand(f'{BotCommands.BtSelectCommand}', 'Select files to download only torrents'),
        BotCommand(f'{BotCommands.CancelMirror}', f'Cancel a Task'),
        BotCommand(f'{BotCommands.CancelAllCommand[0]}', f'Cancel all tasks which added by you to in bots.'),
        BotCommand(f'{BotCommands.ListCommand}', 'Search in Drive'),
        BotCommand(f'{BotCommands.SearchCommand}', 'Search in Torrent'),
        BotCommand(f'{BotCommands.UserSetCommand[0]}', 'Users settings'),
        BotCommand(f'{BotCommands.HelpCommand}', 'Get detailed help'),
        BotCommand(f'{BotCommands.BotSetCommand[0]}', 'Change Bot settings'),
        BotCommand(f'{BotCommands.RestartCommand}', 'Restart the bot'),
        BotCommand(f'{BotCommands.UserTdCommand}', 'Edit your own td and index settings'),
            ])
