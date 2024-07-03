#!/usr/bin/env python3
import json
from uuid import uuid4
from time import sleep, time
from base64 import b64encode
from pyrogram import filters
from shutil import disk_usage
from urllib.parse import quote
from pymongo import MongoClient
from shlex import split as ssplit
from asyncio.subprocess import PIPE
from aiofiles import open as aiopen
from urllib3 import disable_warnings
from aiofiles.os import path as aiopath
from cloudscraper import create_scraper
from asyncio import create_subprocess_exec
from pyrogram.filters import regex, command
from pyrogram.handlers import MessageHandler
from random import choice, random, randrange
from pyrogram.types import BotCommand, CallbackQuery
from re import findall as refindall, search as re_search
from subprocess import run as srun, check_output as scheck_output
from aiofiles.os import remove as aioremove, path as aiopath, mkdir
from os import remove as osremove, rename as osrename, path as ospath, replace as osreplace, getcwd
from pyrogram.errors import PeerIdInvalid, RPCError, UserNotParticipant, FloodWait
from psutil import disk_usage, cpu_percent, swap_memory, cpu_count, virtual_memory, net_io_counters, boot_time

from bot import bot, botStartTime, config_dict, task_dict_lock, task_dict, DATABASE_URL, DOWNLOAD_DIR, GLOBAL_BLACKLIST_FILE_KEYWORDS, LOGGER, OWNER_ID, shorteneres_list, user_data
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.ext_utils.files_utils import get_base_name
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.message_utils import get_tg_link_message
from bot.helper.ext_utils.links_utils import is_gdrive_id, is_telegram_link
from bot.helper.ext_utils.bot_utils import cmd_exec, sync_to_async, get_telegraph_list, new_task
from bot.helper.ext_utils.status_utils import get_readable_file_size, get_readable_time
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.ext_utils.bot_utils import update_user_ldata
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import editMessage
from bot.helper.mirror_leech_utils.gdrive_utils.search import gdSearch

leech_data = {}
bot_name = bot.me.username


async def edit_video_metadata(user_id, file_path):
    if not file_path.lower().endswith(('.mp4', '.mkv')):
        return

    user_dict = user_data.get(user_id, {})
    if user_dict.get("metadatatext", False):
        metadata_text = user_dict["metadatatext"]
    else:
        return

    file_name = ospath.basename(file_path)
    temp_ffile_name = ospath.basename(file_path)
    directory = ospath.dirname(file_path)
    temp_file = f"{file_name}.temp.mkv"
    temp_file_path = ospath.join(directory, temp_file)
    
    cmd = ['ffprobe', '-hide_banner', '-loglevel', 'error', '-print_format', 'json', '-show_streams', file_path]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        print(f"Error getting stream info: {stderr.decode().strip()}")
        return

    try:
        streams = json.loads(stdout)['streams']
    except:
        print(f"No streams found in the ffprobe output: {stdout.decode().strip()}")
        return

    cmd = [
        'ffmpeg', '-y', '-i', file_path, '-c', 'copy',
        '-metadata:s:v:0', f'title={metadata_text}',
        '-metadata', f'title={metadata_text}',
        '-metadata', 'copyright=',
        '-metadata', 'description=',
        '-metadata', 'license=',
        '-metadata', 'LICENSE=',
        '-metadata', 'author=',
        '-metadata', 'summary=',
        '-metadata', 'comment=',
        '-metadata', 'artist=',
        '-metadata', 'album=',
        '-metadata', 'genre=',
        '-metadata', 'date=',
        '-metadata', 'creation_time=',
        '-metadata', 'language=',
        '-metadata', 'publisher=',
        '-metadata', 'encoder=',
        '-metadata', 'SUMMARY=',
        '-metadata', 'AUTHOR=',
        '-metadata', 'WEBSITE=',
        '-metadata', 'COMMENT=',
        '-metadata', 'ENCODER=',
        '-metadata', 'FILENAME=',
        '-metadata', 'MIMETYPE=',
        '-metadata', 'PURL=',
        '-metadata', 'ALBUM='
    ]

    audio_index = 0
    subtitle_index = 0
    first_video = False

    for stream in streams:
        stream_index = stream['index']
        stream_type = stream['codec_type']

        if stream_type == 'video':
            if not first_video:
                cmd.extend(['-map', f'0:{stream_index}'])
                first_video = True
            cmd.extend([f'-metadata:s:v:{stream_index}', f'title={metadata_text}'])
        elif stream_type == 'audio':
            cmd.extend(['-map', f'0:{stream_index}', f'-metadata:s:a:{audio_index}', f'title={metadata_text}'])
            audio_index += 1
        elif stream_type == 'subtitle':
            codec_name = stream.get('codec_name', 'unknown')
            if codec_name in ['webvtt', 'unknown']:
                print(f"Skipping unsupported subtitle metadata modification: {codec_name} for stream {stream_index}")
            else:
                cmd.extend(['-map', f'0:{stream_index}', f'-metadata:s:s:{subtitle_index}', f'title={metadata_text}'])
                subtitle_index += 1
        else:
            cmd.extend(['-map', f'0:{stream_index}'])

    cmd.append(temp_file_path)
    process = await create_subprocess_exec(*cmd, stderr=PIPE, stdout=PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        err = stderr.decode().strip()
        print(err)
        print(f"Error modifying metadata for file: {file_name}")
        return

    osreplace(temp_file_path, file_path)
    print(f"Metadata modified successfully for file: {file_name}")


async def get_tag(message):
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention
    return tag


async def check_filename(message, file_name=None, link=None):
    LOGGER.info(f"Checking {file_name}")
    tag = await get_tag(message)
    owner_msg = f"<b>Blackist File Name:</b> <code>{file_name}</code>\n\n"
    if link is not None:
        owner_msg += f"<b>Link:</b> {link}\n\n"
    owner_msg += f"<b>User ID:</b> <code>{message.from_user.id}</code>\n"
    owner_msg += f"<b>User:</b> {tag}\n\n<b>This user is trying to download blacklist file.</b>"
    if file_name is not None:
        if any(filter_word in file_name.lower() for filter_word in GLOBAL_BLACKLIST_FILE_KEYWORDS):
            await bot.send_message(chat_id=OWNER_ID, text=owner_msg)
            msg = f"A Blacklist keyword found in your file/link.You can not download this file/link."
            return msg


async def getDownloadByGid(gid):
    async with task_dict_lock:
        return next((dl for dl in task_dict.values() if dl.gid() == gid), None)


async def getAllDownload(req_status, user_id=None):
    dls = []
    async with task_dict_lock:
        for dl in list(task_dict.values()):
            if user_id and user_id != dl.message.from_user.id:
                continue
            status = dl.status()
            if req_status in ['all', status]:
                dls.append(dl)
    return dls


async def export_leech_data():
    if DATABASE_URL:
        leech_data.clear()
        client = MongoClient(DATABASE_URL)
        db = client.mltb
        collection = db.leech_links
        for document in collection.find():
            name = document.get('name')
            link = document.get('link')
            from_chat_id = document.get('from_chat_id')
            message_id = document.get('message_id')
            leech_data[name] = {"link": link, "from_chat_id": from_chat_id, "message_id": message_id}


async def update_leech_links(name, from_chat_id, message_id):
    if DATABASE_URL and config_dict['LEECH_DUMP_CHAT']:
        client = MongoClient(DATABASE_URL)
        db = client.mltb
        collection = db.leech_links
        link = f"https://t.me/c/{str(from_chat_id)[4:]}/{message_id}"
        collection.update_one({'name': name}, {'$set': {'link': link, 'from_chat_id': from_chat_id, 'message_id': message_id}}, upsert=True)
        LOGGER.info(f"Link for {name} added in database")
        await export_leech_data()


async def copy_message(chat_id, from_chat_id, message_id):
    try:
        await bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
    except:
        pass


async def get_bot_pm_button():
    buttons = ButtonMaker()
    buttons.ubutton("View in inbox", f"https://t.me/{bot_name}")
    button = buttons.build_menu(1)
    return button


async def send_to_chat(chat_id=None, message=None, text=None, buttons=None, reply=False, photo=False):
    if chat_id and not reply:
        try:
            if photo and config_dict['IMAGES']:
                IMAGES = choice(config_dict['IMAGES'])
                await bot.send_photo(chat_id, IMAGES, text, reply_markup=buttons)
            else:
                await bot.send_message(chat_id, text, reply_markup=buttons)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            pass
    else:
        try:
            if photo and config_dict['IMAGES']: 
                return await bot.send_photo(chat_id=message.chat.id, photo=choice(config_dict['IMAGES']), caption=text, reply_to_message_id=message.id, reply_markup=buttons)
            else:
                return await message.reply(text=text, quote=True, disable_web_page_preview=True, disable_notification=True, reply_markup=buttons)
        except FloodWait as f:
            LOGGER.warning(str(f))
            if block:
                await sleep(f.value * 1.2)
                return await message.reply(text=text, quote=True, disable_web_page_preview=True, disable_notification=True, reply_markup=buttons)
            return str(f)
        except Exception as e:
            LOGGER.error(str(e))
            return str(e)


async def stop_duplicate_leech(name, size, listener):
    LOGGER.info(f"Checking Duplicate Leech for: {name}")
    if not listener.isLeech:
        return

    if listener.compress:
        name = f"{name}.zip"
    message = listener.message
    user_id = message.from_user.id
    tag = await get_tag(message)
    leech_dict = leech_data.get(name, {})
    if leech_dict.get('link') and leech_dict.get('from_chat_id') and leech_dict.get('message_id'):
        link = leech_dict['link']
        from_chat_id = leech_dict['from_chat_id']
        message_id = leech_dict['message_id']
    
        if link and is_telegram_link(link):
            try:
                reply_to, session = await get_tg_link_message(link)
            except Exception as e:
                print({e})
                return
            if reply_to:
                file_ = reply_to.document or reply_to.photo or reply_to.video or reply_to.audio or reply_to.voice or reply_to.video_note or reply_to.sticker or reply_to.animation or None
                if file_:
                    file_name = file_.file_name
                    file_size = file_.file_size
                    if size == file_size:
                        if config_dict['BOT_PM'] and message.chat.type != message.chat.type.PRIVATE:
                            msg = f"File already available in Leech Dump Chat.\nI have sent available file in pm."
                            await bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
                        else:
                            msg = f"File already available in Leech Dump Chat.\nI have forwarded the file here."
                            await bot.copy_message(chat_id=message.chat.id, from_chat_id=from_chat_id, message_id=message_id)
                        return msg
    return


async def user_info(user_id):
    try:
        return await bot.get_users(user_id)
    except Exception:
        return ''


async def get_user_tasks(user_id, maxtask):
    if tasks := await getAllDownload('all', user_id):
        return len(tasks) >= maxtask


async def delete_links(message):
    if message.from_user.id == OWNER_ID and message.chat.type == message.chat.type.PRIVATE:
        return

    if config_dict['DELETE_LINKS']:
        try:
            if reply_to := message.reply_to_message:
                await reply_to.delete()
                await message.delete()
            else:
                await message.delete()
        except Exception as e:
            LOGGER.error(str(e))


async def check_duplicate_file(self, up_name):
    LOGGER.info(f"Searching {up_name} in drive")
    message = self.message
    user_id = message.from_user.id 
    telegraph_content, contents_no = await sync_to_async(gdSearch(stopDup=True).drive_list, up_name, self.upDest, self.user_id)
    if telegraph_content:
        if config_dict['BOT_PM'] and message.chat.type != message.chat.type.PRIVATE:
            msg = f"\nFile/Folder is already available in Drive.\nI have sent available file link in pm."
            pmmsg = f"Hey {self.tag}.\n\nFile/Folder is already available in Drive.\nHere are {contents_no} list results:"
            pmbutton = await get_telegraph_list(telegraph_content)
            button = await get_bot_pm_button()
            await send_to_chat(chat_id=user_id, text=pmmsg, button=pmbutton)
        else:
            msg = f"\nFile/Folder is already available in Drive.\nHere are {contents_no} list results:"
            button = await get_telegraph_list(telegraph_content)
        return msg, button
    return False, None


def short_url(longurl, attempt=0):
    if not shorteneres_list:
        return longurl
    if attempt >= 4:
        return longurl
    i = 0 if len(shorteneres_list) == 1 else randrange(len(shorteneres_list))
    _shorten_dict = shorteneres_list[i]
    _shortener = _shorten_dict['domain']
    _shortener_api =  _shorten_dict['api_key']
    cget = create_scraper().request
    disable_warnings()
    try:
        if "shorte.st" in _shortener:
            headers = {'public-api-token': _shortener_api}
            data = {'urlToShorten': quote(longurl)}
            return cget('PUT', 'https://api.shorte.st/v1/data/url', headers=headers, data=data).json()['shortenedUrl']
        elif "linkvertise" in _shortener:
            url = quote(b64encode(longurl.encode("utf-8")))
            linkvertise = [
                f"https://link-to.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://up-to-down.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://direct-link.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://file-link.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}"]
            return choice(linkvertise)
        elif "bitly.com" in _shortener:
            headers = {"Authorization": f"Bearer {_shortener_api}"}
            return cget('POST', "https://api-ssl.bit.ly/v4/shorten", json={"long_url": longurl}, headers=headers).json()["link"]
        elif "ouo.io" in _shortener:
            return cget('GET', f'http://ouo.io/api/{_shortener_api}?s={longurl}', verify=False).text
        elif "cutt.ly" in _shortener:
            return cget('GET', f'http://cutt.ly/api/api.php?key={_shortener_api}&short={longurl}').json()['url']['shortLink']
        else:
            res = cget('GET', f'https://{_shortener}/api?api={_shortener_api}&url={quote(longurl)}').json()
            shorted = res['shortenedUrl']
            if not shorted:
                shrtco_res = cget('GET', f'https://api.shrtco.de/v2/shorten?url={quote(longurl)}').json()
                shrtco_link = shrtco_res['result']['full_short_link']
                res = cget('GET', f'https://{_shortener}/api?api={_shortener_api}&url={shrtco_link}').json()
                shorted = res['shortenedUrl']
            if not shorted:
                shorted = longurl
            return shorted
    except Exception as e:
        LOGGER.error(e)
        sleep(1)
        attempt +=1
        return short_url(longurl, attempt)


def checking_blacklist(message, button=None):
    LOGGER.info(f"Checking blacklis status")
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('is_blacklist'):
        b_msg = f"<b>You are blacklisted ⚠️.</b>\n\n<b>User Id:</b> <code>{user_id}</code>.\n\n"
        b_msg += f"<b>Possible Reasons:</b>\n<b>1:</b> Mirror or Leech P*r*n Video.\n<b>2:</b> Mirror or Leech illegal files.\n\n"
        b_msg += f"Contact with bot owner to remove yourself from blacklist."
        return b_msg, button
    return None, button
    

def checking_token_status(message, button=None):
    user_id = message.from_user.id
    if not config_dict['TOKEN_TIMEOUT'] or bool(user_id == OWNER_ID or user_id in user_data and user_data[user_id].get('is_sudo') or user_id in user_data and user_data[user_id].get('is_good_friend') or user_id in user_data and user_data[user_id].get('is_paid_user')):
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
            f'https://t.me/{bot_name}?{BotCommands.StartCommand}={token}'))
        return f"Your Ads token is expired, generate your token and try again.\n\n<b>Token Timeout:</b> {get_readable_time(int(config_dict['TOKEN_TIMEOUT']))}.\n\n<b>What is token?</b>\nThis is an ads token. If you pass 1 ad, you can use the bot for {get_readable_time(int(config_dict['TOKEN_TIMEOUT']))} after passing the ad.\n\n<b>Token Generate Video Tutorial:</b> ⬇️\nhttps://t.me/AtrociousMirrorBackup/116", button
    return None, button


def check_storage_threshold(size, threshold, arch=False, alloc=False):
    free = disk_usage(DOWNLOAD_DIR).free
    if not alloc:
        if (
            not arch
            and free - size < threshold
            or arch
            and free - (size * 2) < threshold
        ):
            return False
    elif not arch:
        if free < threshold:
            return False
    elif free - size < threshold:
        return False
    return True


async def command_listener(message, isClone=False, isGdrive=False, isJd=False, isLeech=False, isMega=False, isMirror=False, isQbit=False, isYtdl=False):
    msg = ""
    tag = await get_tag(message)

    if message.from_user.id != OWNER_ID:
        if isClone and not config_dict['CLONE_ENABLED']:
            msg = f"Hey {tag}.\n\nCloning file in Gdrive is disabled."
        elif isGdrive and not config_dict['GDRIVE_ENABLED']:
            msg = f"Hey {tag}.\n\nGdrive link is disabled."
        elif isJd and not config_dict['JD_ENABLED']:
            msg = f"Hey {tag}.\n\nJDownload is disabled."
        elif isLeech and not config_dict['LEECH_ENABLED']:
            msg = f"Hey {tag}.\n\nLeeching file in telegram is disabled."
        elif isMega and not config_dict['MEGA_ENABLED']:
            msg = f"Hey {tag}.\n\nMega link is disabled."
        elif isMirror and not config_dict['MIRROR_ENABLED']:
            msg = f"Hey {tag}.\n\nMirroring file in Gdrive is disabled."
        elif isQbit and not config_dict['TORRENT_ENABLED']:
            msg = f"Hey {tag}.\n\nTorrent download is disabled."
        elif isQbit and isLeech and not config_dict['TORRENT_ENABLED'] and not config_dict['LEECH_ENABLED']:
            msg = f"Hey {tag}.\n\nTorrent download and Leech both are disabled."
        elif isYtdl and not config_dict['YTDLP_ENABLED']:
            msg = f"Hey {tag}.\n\nYouTube download is disabled.</b>"
        elif isYtdl and isLeech and not config_dict['YTDLP_ENABLED'] and not config_dict['LEECH_ENABLED']:
            msg = f"Hey {tag}.\n\nYoutube download and Leeching file in telegram both are disabled."
        
    if msg:
        await delete_links(message)
        return await message.reply(msg)


@bot.on_callback_query(regex("limits_callback"))
async def callback_handler(client, CallbackQuery):
    msg = f"Clone Limit: {config_dict['CLONE_LIMIT']} GB\n"
    msg += f"Gdrive Limit: {config_dict['GDRIVE_LIMIT']} GB\n"
    msg += f"Leech Limit: {config_dict['LEECH_LIMIT']} GB\n"
    msg += f"Mega Limit: {config_dict['MEGA_LIMIT']} GB\n"
    msg += f"Mirror Limit: {config_dict['MIRROR_LIMIT']} GB\n"
    msg += f"Storage Threshold: {config_dict['STORAGE_THRESHOLD']} GB\n"
    msg += f"Torrent Limit: {config_dict['TORRENT_LIMIT']} GB\n"
    msg += f"Ytdlp Limit: {config_dict['YTDLP_LIMIT']} GB\n"
    await CallbackQuery.answer(text=msg, show_alert=True)


async def limit_checker(size, listener=None, message=None, isClone=False, isDriveLink=False, isMega=False, isTorrent=False, isYtdlp=False):
    LOGGER.info(f"✅️ Checking file size limit")
    buttons = ButtonMaker()
    buttons.ibutton("See All Limits", "limits_callback")
    button = buttons.build_menu(1)
    if isClone:
        message = message
    else:
         message = listener.message
    user_id = message.from_user.id
    tag = await get_tag(message)
    
    if user_id == OWNER_ID or user_id in user_data and user_data[user_id].get('is_sudo') or user_id in user_data and user_data[user_id].get('is_paid_user'):
        return None, None

    limit_exceeded = ""
    if isClone:
        if CLONE_LIMIT := config_dict['CLONE_LIMIT']:
            limit = CLONE_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Dear {tag}. Clone limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
    elif isDriveLink:
        if GDRIVE_LIMIT := config_dict['GDRIVE_LIMIT']:
            limit = GDRIVE_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'G-drive limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
    elif listener.isLeech:
        if LEECH_LIMIT := config_dict['LEECH_LIMIT']:
            limit = LEECH_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Leech limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
    elif isMega:
        if MEGA_LIMIT := config_dict['MEGA_LIMIT']:
            limit = MEGA_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Mega limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
    elif listener.upDest and not isTorrent:
        if MIRROR_LIMIT := config_dict['MIRROR_LIMIT']:
            limit = MIRROR_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Mirror limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
    elif isTorrent:
        if TORRENT_LIMIT := config_dict['TORRENT_LIMIT']:
            limit = TORRENT_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Torrent limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
    elif isYtdlp:
        if YTDLP_LIMIT := config_dict['YTDLP_LIMIT']:
            limit = YTDLP_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Ytdlp limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'

    if not limit_exceeded:
        if not isClone:
            if STORAGE_THRESHOLD := config_dict['STORAGE_THRESHOLD']:
                arch = any([listener.compress, listener.extract])
                limit = STORAGE_THRESHOLD * 1024**3
                acpt = await sync_to_async(check_storage_threshold, size, limit, arch)
                if not acpt:
                    limit_exceeded = f'You must leave {get_readable_file_size(limit)} free storage.\nYour File/Folder size is {get_readable_file_size(size)}.'
    
    if limit_exceeded:
        return limit_exceeded, button
    else:
        return None, None


async def chat_info(channel_id):
    if channel_id.startswith('-100'):
        channel_id = int(channel_id)
    elif channel_id.startswith('@'):
        channel_id = channel_id.replace('@', '')
    else:
        return None
    try:
        chat = await bot.get_chat(channel_id)
        return chat
    except PeerIdInvalid as e:
        LOGGER.error(f"{e.NAME}: {e.MESSAGE} for {channel_id}")
        return None


async def forcesub(message, ids, button=None):
    join_button = {}
    _msg = ""
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id].get('is_good_friend') or user_id in user_data and user_data[user_id].get('is_paid_user'):
        return None, button
    for channel_id in ids.split():
        chat = await chat_info(channel_id)
        try:
            await chat.get_member(message.from_user.id)
        except UserNotParticipant:
            if username := chat.username:
                invite_link = f"https://t.me/{username}"
            else:
                invite_link = chat.invite_link
            join_button[chat.title] = invite_link
        except RPCError as e:
            LOGGER.error(f"{e.NAME}: {e.MESSAGE} for {channel_id}")
        except Exception as e:
            LOGGER.error(f'{e} for {channel_id}')
    if join_button:
        if button is None:
            button = ButtonMaker()
        _msg = "You haven't joined our channel yet!"
        for key, value in join_button.items():
            button.ubutton(f'Join {key}', value, 'footer')
    return _msg, button


async def BotPm_check(message, button=None):
    try:
        temp_msg = await message._client.send_message(chat_id=message.from_user.id, text='<b>Checking Access...</b>')
        await temp_msg.delete()
        return None, button
    except Exception as e:
        if button is None:
            button = ButtonMaker()
        _msg = "You didn't START the bot in PM (Private)."
        button.ubutton("Start Bot Now", f"https://t.me/{bot_name}?start=start", 'header')
        return _msg, button


async def task_utils(message):
    LOGGER.info("Running Task Checking")
    msg = []
    button = None
    user_id = message.from_user.id
    user = await message._client.get_users(user_id)
    if user_id == OWNER_ID:
        return msg, button
    b_msg, button = checking_blacklist(message, button)
    if b_msg is not None:
        msg.append(b_msg)
    if config_dict['BOT_PM']:
        if user.status == user.status.LONG_AGO:
            _msg, button = await BotPm_check(message, button)
            if _msg:
                msg.append(_msg)
    if ids := config_dict['FSUB_IDS']:
        _msg, button = await forcesub(message, ids, button)
        if _msg:
            msg.append(_msg)
    if config_dict["BOT_MAX_TASKS"] and len(task_dict) >= config_dict['BOT_MAX_TASKS']:
        msg.append(f"Bot Max Tasks limit exceeded.\nBot max tasks limit is {config_dict['BOT_MAX_TASKS']}.\nPlease wait for the completion of other tasks.")
    if (maxtask := config_dict['USER_MAX_TASKS']) and await get_user_tasks(message.from_user.id, maxtask):
        if config_dict["PAID_SERVICE"] and user_id in user_data and user_data[user_id].get('is_paid_user'):
            pass
        else:
            msg.append(f"User tasks limit is {maxtask}.\nPlease wait for the completion of your old tasks.")
    token_msg, button = checking_token_status(message, button)
    if token_msg is not None:
        msg.append(token_msg)
    return msg, button


@bot.on_callback_query(regex("no_drive_link"))
async def callback_handler(client, CallbackQuery):
    msg = f"Drive link is hidden for all user.\n"
    msg += f"Download from index link if available.\n"
    msg += f"You will get same speed from index link like google drive."
    await CallbackQuery.answer(text=msg, show_alert=True)


async def get_drive_link_button(message, link):
    buttons = ButtonMaker()
    if config_dict['DISABLE_DRIVE_LINK']:
        if message.from_user.id == OWNER_ID:
            if config_dict["BOT_PM"] or message.chat.type == message.chat.type.PRIVATE: 
                buttons.ubutton("☁️ Drive Link", link)
        else:
            buttons.ibutton("🚫 Drive Link", "no_drive_link")
    else:
        buttons.ubutton("☁️ Drive Link", link)
    return buttons


async def set_commands(bot):
    if config_dict['SET_COMMANDS']:
        await bot.set_bot_commands(commands=[
            BotCommand(BotCommands.StartCommand, "Start the bot"),
            BotCommand(BotCommands.StatsCommand, "Get bot stats"),
            BotCommand(BotCommands.StatusCommand, "Get bot status"),
            BotCommand(BotCommands.RestartCommand, "Restart the bot"),
            BotCommand(BotCommands.CloneCommand, "Start cloning"),
            BotCommand(BotCommands.MirrorCommand[0], "Start mirroring"),
            BotCommand(BotCommands.LeechCommand[0], "Start leeching"),
            BotCommand(BotCommands.QbMirrorCommand[0], "Start qb mirroring"),
            BotCommand(BotCommands.QbLeechCommand[0], "Start qb leeching"),
            BotCommand(BotCommands.YtdlCommand[0], "Mirror youtube file"),
            BotCommand(BotCommands.YtdlLeechCommand[0], "Leech youtube file"),
            BotCommand(BotCommands.CancelTaskCommand[0], "Cancel any task"),
            BotCommand(BotCommands.CancelAllCommand, "Cancel all task"),
            BotCommand(BotCommands.ListCommand, "Search file in google drive"),
            BotCommand(BotCommands.DeleteCommand, "Delete google drive file"),
            BotCommand(BotCommands.ForceStartCommand[0], "Force start a task"),
            BotCommand(BotCommands.ListCommand, "List files in Google Drive"),
            BotCommand(BotCommands.SearchCommand, "Search files in Google Drive"),
            BotCommand(BotCommands.UsersCommand, "Check users"),
            BotCommand(BotCommands.AuthorizeCommand, "Authorize a user"),
            BotCommand(BotCommands.UnAuthorizeCommand, "Unauthorize a user"),
            BotCommand(BotCommands.AddSudoCommand, "Add a sudo user"),
            BotCommand(BotCommands.RmSudoCommand, "Remove a sudo user"),
            BotCommand(BotCommands.PingCommand, "Ping the bot"),
            BotCommand(BotCommands.HelpCommand, "Get help"),
            BotCommand(BotCommands.LogCommand, "Get bot log"),
            BotCommand(BotCommands.BotSetCommand[0], "Bot settings"),
            BotCommand(BotCommands.UserSetCommand[0], "User settings"),
            BotCommand(BotCommands.BtSelectCommand, "Select a BT download"),
            BotCommand(BotCommands.RssCommand, "Manage RSS feeds"),
        ])


async def start(client, message):
    if len(message.command) > 1:
        userid = message.from_user.id
        input_token = message.command[1]
        if userid not in user_data:
            return await send_to_chat(message=message, text=f"Who are you?", buttons=None, photo=False)
        data = user_data[userid]
        if 'token' not in data or data['token'] != input_token:
            return await send_to_chat(message=message, text=f"This token already expired", buttons=None, photo=False)
        data['token'] = str(uuid4())
        data['time'] = time()
        user_data[userid].update(data)
        return await send_to_chat(message=message, text=f"Token refreshed successfully", buttons=None, reply=True, photo=True)
    else:
        buttons = ButtonMaker()
        buttons.ubutton("Repo", "https://github.com/SN-Abdullah-Al-Noman/Atrocious_Mirror")
        buttons.ubutton("Owner", "https://t.me/AtrociousMirrorBackup")
        reply_markup = buttons.build_menu(2)
        start_string = f'''This bot can mirror all your links|files|torrents to Google Drive or any rclone cloud or to telegram.\nType /{BotCommands.HelpCommand} to get a list of available commands'''
        await send_to_chat(message=message, text=start_string, buttons=reply_markup, reply=True, photo=True)
    await DbManager().update_pm_users(message.from_user.id)


async def stats(client, message):
    if await aiopath.exists('.git'):
        last_commit = await cmd_exec("git log -1 --date=short --pretty=format:'%cd <b>\nFrom:</b> %cr'", True)
        last_commit = last_commit[0]
    else:
        last_commit = 'No UPSTREAM_REPO'
    total, used, free, disk = disk_usage('/')
    swap = swap_memory()
    memory = virtual_memory()
    stats = f'<b>Commit Date:</b> {last_commit}\n\n'\
            f'<b>Bot Uptime:</b> {get_readable_time(time() - botStartTime)}\n'\
            f'<b>OS Uptime:</b> {get_readable_time(time() - boot_time())}\n\n'\
            f'<b>Total Disk Space:</b> {get_readable_file_size(total)}\n'\
            f'<b>Used:</b> {get_readable_file_size(used)} | <b>Free:</b> {get_readable_file_size(free)}\n\n'\
            f'<b>Up:</b> {get_readable_file_size(net_io_counters().bytes_sent)} <b>|</b> '\
            f'<b>Down:</b> {get_readable_file_size(net_io_counters().bytes_recv)}\n'\
            f'<b>CPU:</b> {cpu_percent(interval=0.5)}% <b>|</b> '\
            f'<b>RAM:</b> {memory.percent}% <b>| </b>'\
            f'<b>DISK:</b> {disk}%\n'\
            f'<b>Physical Cores:</b> {cpu_count(logical=False)} <b>|</b> '\
            f'<b>Total Cores:</b> {cpu_count(logical=True)}\n\n'\
            f'<b>SWAP:</b> {get_readable_file_size(swap.total)} | <b>Used:</b> {swap.percent}%\n'\
            f'<b>Memory Total:</b> {get_readable_file_size(memory.total)}\n'\
            f'<b>Memory Free:</b> {get_readable_file_size(memory.available)}\n'\
            f'<b>Memory Used:</b> {get_readable_file_size(memory.used)}\n'
    await send_to_chat(message=message, text=stats, reply=True, buttons=None, photo=True)


async def log(client, message):
    logFileRead = open('log.txt', 'r')
    logFileLines = logFileRead.read().splitlines()
    ind = 1
    Loglines = ''
    try:
        while len(Loglines) <= 2500:
            Loglines = logFileLines[-ind]+'\n'+Loglines
            if ind == len(logFileLines):
                break
            ind += 1
        log_text = Loglines
        await client.send_message(chat_id=message.chat.id, text=log_text, disable_web_page_preview=True)
    except Exception as err:
        LOGGER.error(f"Log Display: {err}")


async def add_to_paid_user(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner.'
        elif id_ in user_data and user_data[id_].get('is_paid_user'):
            msg = 'User already in paid user list.'
        else:
            update_user_ldata(id_, 'is_paid_user', True)
            update_user_ldata(id_, 'is_blacklist', False)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = 'User added in paid user list.\nFrom now token system and some limit will skip for him.'
    else:
        msg = "Give ID or Reply To message of whom you want to add in paid user list."
    await send_to_chat(message=message, text=msg, reply=True)


async def remove_from_paid_user(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner'
        elif id_ not in user_data and user_data[id_].get('is_paid_user'):
            msg = 'User not in paid user list.'
        else:
            update_user_ldata(id_, 'is_paid_user', False)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = 'User removed from paid user list.'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from paid user list."
    await send_to_chat(message=message, text=msg, reply=True)


async def add_to_good_friend(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner.'
        elif id_ in user_data and user_data[id_].get('is_good_friend'):
            msg = 'User already in good friend list.'
        else:
            update_user_ldata(id_, 'is_good_friend', True)
            update_user_ldata(id_, 'is_blacklist', False)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = 'User added in good friend list.\nFrom now token system will skip for him.'
    else:
        msg = "Give ID or Reply To message of whom you want to add in good friend list."
    await send_to_chat(message=message, text=msg, reply=True)


async def remove_from_good_friend(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner.'
        elif id_ in user_data or user_data[id_].get('is_good_friend'):
            update_user_ldata(id_, 'is_good_friend', False)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = 'User removed from good friend list.'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from good friend list."
    await send_to_chat(message=message, text=msg, reply=True)


async def add_to_blacklist(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner'
        elif id_ in user_data and user_data[id_].get('is_blacklist'):
            msg = 'User already in blacklist.'
        else:
            update_user_ldata(id_, 'is_blacklist', True)
            update_user_ldata(id_, 'is_good_friend', False)
            update_user_ldata(id_, 'is_paid_user', False)
            update_user_ldata(id_, 'is_sudo', False)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = 'User added in blacklist.'
    else:
        msg = "Give ID or Reply To message of whom you want to add in blacklist."
    await send_to_chat(message=message, text=msg, reply=True)


async def remove_from_blacklist(client, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id
    if id_:
        if id_ == OWNER_ID:
            msg = 'You are playing with owner'
        elif id_ not in user_data and user_data[id_].get('is_blacklist'):
            msg = 'User not in blacklist.'
        else:
            update_user_ldata(id_, 'is_blacklist', False)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = 'User removed from blacklist.'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from blacklist."
    await send_to_chat(message=message, text=msg, reply=True)


bot.add_handler(MessageHandler(start, filters=command(BotCommands.StartCommand)))
bot.add_handler(MessageHandler(stats, filters=command(BotCommands.StatsCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(log, filters=command(BotCommands.LogCommand) & CustomFilters.sudo))

bot.add_handler(MessageHandler(add_to_paid_user, filters=(command("addpaid") & CustomFilters.sudo)))
bot.add_handler(MessageHandler(remove_from_paid_user, filters=(command("rmpaid") & CustomFilters.sudo)))

bot.add_handler(MessageHandler(add_to_good_friend, filters=(command("addgdf") & CustomFilters.sudo)))
bot.add_handler(MessageHandler(remove_from_good_friend, filters=(command("rmgdf") & CustomFilters.sudo)))

bot.add_handler(MessageHandler(add_to_blacklist, filters=(command("addblacklist") & CustomFilters.sudo)))
bot.add_handler(MessageHandler(remove_from_blacklist, filters=(command("rmblacklist") & CustomFilters.sudo)))
