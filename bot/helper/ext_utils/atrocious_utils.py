#!/usr/bin/env python3
from uuid import uuid4
from time import sleep, time
from base64 import b64encode
from shutil import disk_usage
from urllib.parse import quote
from pymongo import MongoClient
from urllib3 import disable_warnings
from cloudscraper import create_scraper
from random import choice, random, randrange
from pyrogram.errors import PeerIdInvalid, RPCError, UserNotParticipant
from pyrogram.types import BotCommand, CallbackQuery
from pyrogram.filters import regex

from bot import bot, bot_name, config_dict, DATABASE_URL, download_dict, DOWNLOAD_DIR, GLOBAL_BLACKLIST_FILE_KEYWORDS, LOGGER, OWNER_ID, shorteneres_list, user_data
from bot.helper.ext_utils.bot_utils import sync_to_async, get_readable_file_size, get_readable_time, getAllDownload, get_telegraph_list, is_gdrive_id, is_telegram_link
from bot.helper.ext_utils.fs_utils import get_base_name
from bot.helper.telegram_helper.message_utils import get_tg_link_content
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.mirror_utils.gdrive_utlis.search import gdSearch


leech_data = {}

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


async def send_to_chat(chat_id, text, button=None, photo=False):
    try:
        if photo and config_dict['IMAGES']:
            IMAGES = choice(config_dict['IMAGES'])
            await bot.send_photo(chat_id, IMAGES, text, reply_markup=button)
        else:
            await bot.send_message(chat_id, text, reply_markup=button)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        pass


async def stop_duplicate_check(name, listener):
    if (not is_gdrive_id(listener.upDest) or listener.isLeech or listener.select or listener.upDest.startswith('mtp:') and not listener.user_dict.get('stop_duplicate', False) or config_dict['STOP_DUPLICATE'] and listener.upDest.startswith('mtp:')):
        return False, None

    if listener.compress:
        name = f"{name}.zip"
    elif listener.extract:
        try:
            name = get_base_name(name)
        except:
            name = None

    message = listener.message
    user_id = message.from_user.id
    
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if name is not None:
        telegraph_content, contents_no = await sync_to_async(gdSearch(stopDup=True).drive_list, name, listener.upDest, listener.user_id)
        if telegraph_content:
            if config_dict['BOT_PM'] and message.chat.type != message.chat.type.PRIVATE:
                msg = f"File/Folder is already available in Drive.\nI have sent available file link in pm."
                pmmsg = f"Hey {tag}.\n\nFile/Folder is already available in Drive.\n\nHere are {contents_no} list results:"
                pmbutton = await get_telegraph_list(telegraph_content)
                button = await get_bot_pm_button()
                await send_to_chat(chat_id=user_id, text=pmmsg, button=pmbutton)
            else:
                msg = f"File/Folder is already available in Drive.\nHere are {contents_no} list results:"
                button = await get_telegraph_list(telegraph_content)
            return msg, button
    return False, None


async def stop_duplicate_leech(name, size, listener):
    LOGGER.info(f"Leech Name: {name}")
    if not listener.isLeech:
        return
    if listener.compress:
        name = f"{name}.zip"
    message = listener.message
    user_id = message.from_user.id
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    leech_dict = leech_data.get(name, {})
    if leech_dict.get('link') and leech_dict.get('from_chat_id') and leech_dict.get('message_id'):
        link = leech_dict['link']
        from_chat_id = leech_dict['from_chat_id']
        message_id = leech_dict['message_id']
    
        if link and is_telegram_link(link):
            try:
                reply_to, session = await get_tg_link_content(link)
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
            f'https://t.me/{bot_name}?start={token}'))
        return f"Your Ads token is expired, generate your token and try again.\n\n<b>Token Timeout:</b> {get_readable_time(int(config_dict['TOKEN_TIMEOUT']))}.\n\n<b>What is token?</b>\nThis is an ads token. If you pass 1 ad, you can use the bot for {get_readable_time(int(config_dict['TOKEN_TIMEOUT']))} after passing the ad.\n\n<b>Token Generate Video Tutorial:</b> ⬇️\nhttps://t.me/AtrociousMirrorBackup/116", button
    return None, button


async def check_filename(name=None):
    if name is not None and any(filter_word in name.lower() for filter_word in GLOBAL_BLACKLIST_FILE_KEYWORDS):
        return f"A Blacklist keyword found in your file/link.You can not mirror or leech this file/link."


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


async def command_listener(message, isClone=False, isGdrive=False, isLeech=False, isMega=False, isMirror=False, isQbit=False, isYtdl=False):
    msg = ""
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if message.from_user.id != OWNER_ID:
        if isClone and not config_dict['CLONE_ENABLED']:
            msg = f"Hey {tag}.\n\nCloning file in Gdrive is disabled."
        elif isGdrive and not config_dict['GDRIVE_ENABLED']:
            msg = f"Hey {tag}.\n\nGdrive link is disabled."
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


async def limit_checker(size, listener, isClone=False, isDriveLink=False, isMega=False, isTorrent=False, isYtdlp=False):
    buttons = ButtonMaker()
    buttons.ibutton("See All Limits", "limits_callback")
    button = buttons.build_menu(1)
    user_id = listener.message.from_user.id
    if user_id == OWNER_ID or user_id in user_data and user_data[user_id].get('is_sudo') or user_id in user_data and user_data[user_id].get('is_paid_user'):
        return None, None

    LOGGER.info('Checking Size Limit of link/file/folder/tasks...')
    limit_exceeded = ''
    if isClone:
        if CLONE_LIMIT := config_dict['CLONE_LIMIT']:
            limit = CLONE_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Clone limit is {get_readable_file_size(limit)}.\nYour File/Folder size is {get_readable_file_size(size)}.'
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


async def set_commands(client):
    if config_dict['SET_COMMANDS']:
        await client.set_bot_commands([
        BotCommand(f'{BotCommands.MirrorCommand[0]}', f'or /{BotCommands.MirrorCommand[1]} Mirror'),
        BotCommand(f'{BotCommands.LeechCommand[0]}', f'or /{BotCommands.LeechCommand[1]} Leech'),
        BotCommand(f'{BotCommands.QbMirrorCommand[0]}', f'or /{BotCommands.QbMirrorCommand[1]} Mirror torrent using qBittorrent'),
        BotCommand(f'{BotCommands.QbLeechCommand[0]}', f'or /{BotCommands.QbLeechCommand[1]} Leech torrent using qBittorrent'),
        BotCommand(f'{BotCommands.YtdlCommand[0]}', f'or /{BotCommands.YtdlCommand[1]} Mirror yt-dlp supported link'),
        BotCommand(f'{BotCommands.YtdlLeechCommand[0]}', f'or /{BotCommands.YtdlLeechCommand[1]} Leech through yt-dlp supported link'),
        BotCommand(f'{BotCommands.CloneCommand}', f'Copy file/folder to Drive'),
        BotCommand(f'{BotCommands.CountCommand}', f'Count file/folder of Google Drive.'),
        BotCommand(f'{BotCommands.StatusCommand}', f'Get mirror status message'),
        BotCommand(f'{BotCommands.StatsCommand}', f'Check Bot & System stats'),
        BotCommand(f'{BotCommands.BtSelectCommand}', 'Select files to download only torrents'),
        BotCommand(f'{BotCommands.CancelMirror}', f'Cancel a Task'),
        BotCommand(f'{BotCommands.CancelAllCommand}', f'Cancel all tasks which added by you to in bots.'),
        BotCommand(f'{BotCommands.ListCommand}', 'Search in Drive'),
        BotCommand(f'{BotCommands.SearchCommand}', 'Search in Torrent'),
        BotCommand(f'{BotCommands.UserSetCommand}', f'Users settings'),
        BotCommand(f'{BotCommands.HelpCommand}', 'Get detailed help'),
        BotCommand(f'{BotCommands.BotSetCommand[0]}', 'Change Bot settings'),
        BotCommand(f'{BotCommands.RestartCommand}', 'Restart the bot'),
        BotCommand(f'{BotCommands.LogCommand}', 'Get bots log'),
            ])


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
    _msg = ''
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
    if config_dict['BOT_MAX_TASKS'] and len(download_dict) >= config_dict['BOT_MAX_TASKS']:
        msg.append(f"Bot Max Tasks limit exceeded.\nBot max tasks limit is {config_dict['BOT_MAX_TASKS']}.\nPlease wait for the completion of other tasks.")
    if (maxtask := config_dict['USER_MAX_TASKS']) and await get_user_tasks(message.from_user.id, maxtask):
        if config_dict['PAID_SERVICE'] and user_id in user_data and user_data[user_id].get('is_paid_user'):
            pass
        else:
            msg.append(f"User tasks limit is {maxtask}.\nPlease wait for the completion of your old tasks.")
    token_msg, button = checking_token_status(message, button)
    if token_msg is not None:
        msg.append(token_msg)
    return msg, button
