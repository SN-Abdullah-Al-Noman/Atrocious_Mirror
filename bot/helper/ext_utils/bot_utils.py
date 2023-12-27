#!/usr/bin/env python3
from re import match as re_match
from time import time
from html import escape
from psutil import virtual_memory, cpu_percent, disk_usage, net_io_counters
from asyncio import create_subprocess_exec, create_subprocess_shell, run_coroutine_threadsafe, sleep
from asyncio.subprocess import PIPE
from functools import partial, wraps
from concurrent.futures import ThreadPoolExecutor
from aiohttp import ClientSession
from pyrogram.filters import regex
from pyrogram.types import CallbackQuery

from bot import download_dict, download_dict_lock, botStartTime, user_data, config_dict, bot_loop, bot
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.theme import theme

THREADPOOL = ThreadPoolExecutor(max_workers=1000)

COMMAND_USAGE = {}

MAGNET_REGEX = r'magnet:\?xt=urn:(btih|btmh):[a-zA-Z0-9]*\s*'

URL_REGEX = r'^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$'

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

STATUS_START = 0
PAGES = 1
PAGE_NO = 1

class MirrorStatus:
    STATUS_UPLOADING = theme['Upload']
    STATUS_DOWNLOADING = theme['Download']
    STATUS_CLONING = theme['Clone']
    STATUS_QUEUEDL = theme['QueueDl']
    STATUS_QUEUEUP = theme['QueueUp']
    STATUS_PAUSED = theme['Pause']
    STATUS_ARCHIVING = theme['Archive']
    STATUS_EXTRACTING = theme['Extract']
    STATUS_SPLITTING = theme['Split']
    STATUS_CHECKING = theme['CheckUp']
    STATUS_SEEDING = theme['Seed']


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


def speed_string_to_bytes(size_text: str):
    size = 0
    size_text = size_text.lower()
    if "k" in size_text:
        size += float(size_text.split("k")[0]) * 1024
    elif "m" in size_text:
        size += float(size_text.split("m")[0]) * 1048576
    elif "g" in size_text:
        size += float(size_text.split("g")[0]) * 1073741824
    elif "t" in size_text:
        size += float(size_text.split("t")[0]) * 1099511627776
    elif "b" in size_text:
        size += float(size_text.split("b")[0])
    return size


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
    if config_dict['STATUS_HEADER']:
        msg += f"<b>{config_dict['STATUS_HEADER']}</b>\n\n"
    for download in list(download_dict.values())[STATUS_START:STATUS_LIMIT+STATUS_START]:
        if config_dict['SAFE_MODE']:
            msg += f"<b>{download.status()}: </b>Safe Mode Activated"
        else:
            msg += f"<b><a href='{download.message.link}'>{download.status()}</a>: </b>"
            msg += f"<code>{escape(f'{download.name()}')}</code>"
        if download.status() not in [MirrorStatus.STATUS_SPLITTING, MirrorStatus.STATUS_SEEDING]:
            msg += f"\n<b>{theme['Done']}:</b> {get_progress_bar_string(download.progress())} {download.progress()}"
            msg += f"\n<b>{theme['Speed']}: </b>{download.speed()}"
            msg += f"\n<b>{theme['Process']}: </b>{download.processed_bytes()} of {download.size()}"
            msg += f"\n<b>{theme['ETA']}: </b>{download.eta()} <b>| Elapsed: </b>{get_readable_time(time() - download.message.date.timestamp())}"
            msg += f"\n<b>{theme['Engine']}: </b>{download.engine}"
            msg += f"\n<b>{theme['User']}: </b>{download.message.from_user.mention(style='html')} | <b>ID: </b><code>{download.message.from_user.id}</code>"
            if hasattr(download, 'seeders_num'):
                try:
                    msg += f"\n<b>{theme['Seeders']}:</b> {download.seeders_num()} | <b>Leechers:</b> {download.leechers_num()}"
                except:
                    pass
        elif download.status() == MirrorStatus.STATUS_SEEDING:
            msg += f"\n<b>{theme['Size']}: </b>{download.size()}"
            msg += f"\n<b>{theme['Speed']}: </b>{download.upload_speed()}"
            msg += f" | <b>{theme['Uploaded']}: </b>{download.uploaded_bytes()}"
            msg += f"\n<b>{theme['Ratio']}: </b>{download.ratio()}"
            msg += f" | <b>{theme['Time']}: </b>{download.seeding_time()}"
        else:
            msg += f"\n<b>{theme['Size']}: </b>{download.size()}"
        msg += f"\n<b>{theme['Stop']} </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n\n"
    if len(msg) == 0:
        return None, None
    dl_speed = 0
    up_speed = 0
    for download in download_dict.values():
        tstatus = download.status()
        if tstatus == MirrorStatus.STATUS_DOWNLOADING:
            dl_speed += text_size_to_bytes(download.speed())
        elif tstatus == MirrorStatus.STATUS_UPLOADING:
            up_speed += text_size_to_bytes(download.speed())
        elif tstatus == MirrorStatus.STATUS_SEEDING:
            up_speed +=text_size_to_bytes(download.upload_speed())
    buttons = ButtonMaker()
    if tasks > STATUS_LIMIT:
        buttons.ibutton("Previous", "status pre")
        buttons.ibutton("Next", "status nex")
        buttons.ibutton(f"Page: {PAGE_NO}/{PAGES}", "status ref")
        buttons.ibutton("Close", "status close")
        button = buttons.build_menu(2)
    else:
        buttons.ibutton("Refresh", "status ref")
        buttons.ibutton("Statistics", str(THREE))
        buttons.ubutton(f"Repo", f"https://github.com/SN-Abdullah-Al-Noman/Atrocious_Mirror")
        buttons.ibutton("Close", "status close")
        button = buttons.build_menu(2)
    if config_dict['BOT_MAX_TASKS']:
        TASKS_COUNT = f"<b>Task Limit: </b>{config_dict['BOT_MAX_TASKS']} | <b>Run:</b> {tasks} | <b>Free:</b> {config_dict['BOT_MAX_TASKS'] - tasks}"
    else:
        TASKS_COUNT = f"<b>Tasks Running:</b> {tasks}"
    msg += f"■■■■■■■■■■■■■■■■■■■■"
    msg += f"\n{TASKS_COUNT}"
    msg += f"\n<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {get_readable_file_size(disk_usage(config_dict['DOWNLOAD_DIR']).free)}"
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
    return bool(re_match(r'^(mrcc:)?(?!magnet:)(?!mtp:)(?![- ])[a-zA-Z0-9_\. -]+(?<! ):(?!.*\/\/).*$|^rcl$', path))


def is_gdrive_id(id_):
    return bool(re_match(r'^(mtp:)?(?:[a-zA-Z0-9-_]{33}|[a-zA-Z0-9_-]{19})$|^gdl$|^root$', id_))


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


def text_size_to_bytes(size_text):
    size = 0
    size_text = size_text.lower()
    if 'k' in size_text:
        size += float(size_text.split('k')[0]) * 1024
    elif 'm' in size_text:
        size += float(size_text.split('m')[0]) * 1048576
    elif 'g' in size_text:
        size += float(size_text.split('g')[0]) *1073741824
    elif 't' in size_text:
        size += float(size_text.split('t')[0]) *1099511627776
    return size


def speed_string_to_bytes(size_text: str):
    size = 0
    size_text = size_text.lower()
    if "k" in size_text:
        size += float(size_text.split("k")[0]) * 1024
    elif "m" in size_text:
        size += float(size_text.split("m")[0]) * 1048576
    elif "g" in size_text:
        size += float(size_text.split("g")[0]) * 1073741824
    elif "t" in size_text:
        size += float(size_text.split("t")[0]) * 1099511627776
    elif "b" in size_text:
        size += float(size_text.split("b")[0])
    return size


def new_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future
    return wrapper


ONE, TWO, THREE = range(3)
@bot.on_callback_query(regex(pattern=f"^{str(THREE)}$"))
async def pop_up_stats(client, CallbackQuery):
    sent = get_readable_file_size(net_io_counters().bytes_recv)
    recv = get_readable_file_size(net_io_counters().bytes_sent)
    num_active = 0
    num_upload = 0
    num_seeding = 0
    num_zip = 0
    num_unzip = 0
    num_split = 0
    num_queuedl = 0
    num_queueup = 0
    
    for stats in list(download_dict.values()):
        if stats.status() == MirrorStatus.STATUS_DOWNLOADING:
            num_active += 1
        if stats.status() == MirrorStatus.STATUS_UPLOADING:
            num_upload += 1
        if stats.status() == MirrorStatus.STATUS_SEEDING:
            num_seeding += 1
        if stats.status() == MirrorStatus.STATUS_ARCHIVING:
            num_zip += 1
        if stats.status() == MirrorStatus.STATUS_EXTRACTING:
            num_unzip += 1
        if stats.status() == MirrorStatus.STATUS_SPLITTING:
            num_split += 1
        if stats.status() == MirrorStatus.STATUS_QUEUEDL:
            num_queuedl += 1
        if stats.status() == MirrorStatus.STATUS_QUEUEUP:
            num_queueup += 1
        
            
    msg = f"Toxic Telegram\n\n"
    msg += f"Sent: {sent} | Received: {recv}\n\n"
    msg += f"Download: {num_active} | Upload: {num_upload}\n\n"
    msg += f"Seed: {num_seeding} | Split: {num_split}\n\n"
    msg += f"Zip: {num_zip} | Unzip: {num_unzip}\n\n"
    msg += f"QueueDl: {num_queuedl} | QueueUp: {num_queueup}\n\n"
    msg += f"Uninstall telegram and save your life."

    await CallbackQuery.answer(text=msg, show_alert=True)
