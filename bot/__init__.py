from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aria2p import API as ariaAPI, Client as ariaClient
from asyncio import Lock
from dotenv import load_dotenv, dotenv_values
from logging import (
    getLogger,
    FileHandler,
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
    warning as log_warning,
    ERROR,
)
from os import remove, path as ospath, environ
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pyrogram import Client as tgClient, enums
from qbittorrentapi import Client as qbClient
from socket import setdefaulttimeout
from subprocess import Popen, run
from time import time
from tzlocal import get_localzone
from uvloop import install

# from faulthandler import enable as faulthandler_enable
# faulthandler_enable()

install()
setdefaulttimeout(600)

getLogger("qbittorrentapi").setLevel(INFO)
getLogger("requests").setLevel(INFO)
getLogger("urllib3").setLevel(INFO)
getLogger("pyrogram").setLevel(ERROR)
getLogger("httpx").setLevel(ERROR)
getLogger("pymongo").setLevel(ERROR)

botStartTime = time()

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

LOGGER = getLogger(__name__)

load_dotenv("config.env", override=True)

Intervals = {"status": {}, "qb": "", "jd": "", "stopAll": False}
QbTorrents = {}
jd_downloads = {}
DRIVES_NAMES = []
DRIVES_IDS = []
INDEX_URLS = []
GLOBAL_EXTENSION_FILTER = ["aria2", "!qB"]
user_data = {}
aria2_options = {}
qbit_options = {}
queued_dl = {}
queued_up = {}
non_queued_dl = set()
non_queued_up = set()
multi_tags = set()
shorteneres_list = []
GLOBAL_BLACKLIST_FILE_KEYWORDS = []

try:
    if bool(environ.get("_____REMOVE_THIS_LINE_____")):
        log_error("The README.md file there to be read! Exiting now!")
        exit(1)
except:
    pass

task_dict_lock = Lock()
queue_dict_lock = Lock()
qb_listener_lock = Lock()
jd_lock = Lock()
cpu_eater_lock = Lock()
subprocess_lock = Lock()
status_dict = {}
task_dict = {}
rss_dict = {}

BOT_TOKEN = environ.get("BOT_TOKEN", "")
if len(BOT_TOKEN) == 0:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

bot_id = BOT_TOKEN.split(":", 1)[0]

DATABASE_URL = environ.get("DATABASE_URL", "")
if len(DATABASE_URL) == 0:
    DATABASE_URL = ""

if DATABASE_URL:
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn.mltb
        current_config = dict(dotenv_values("config.env"))
        old_config = db.settings.deployConfig.find_one({"_id": bot_id})
        if old_config is None:
            db.settings.deployConfig.replace_one(
                {"_id": bot_id}, current_config, upsert=True
            )
        else:
            del old_config["_id"]
        if old_config and old_config != current_config:
            db.settings.deployConfig.replace_one(
                {"_id": bot_id}, current_config, upsert=True
            )
        elif config_dict := db.settings.config.find_one({"_id": bot_id}):
            del config_dict["_id"]
            for key, value in config_dict.items():
                environ[key] = str(value)
        if pf_dict := db.settings.files.find_one({"_id": bot_id}):
            del pf_dict["_id"]
            for key, value in pf_dict.items():
                if value:
                    file_ = key.replace("__", ".")
                    with open(file_, "wb+") as f:
                        f.write(value)
                    if file_ == "cfg.zip":
                        run(["rm", "-rf", "/JDownloader/cfg"])
                        run(["7z", "x", "cfg.zip", "-o/JDownloader"])
                        remove("cfg.zip")
        if a2c_options := db.settings.aria2c.find_one({"_id": bot_id}):
            del a2c_options["_id"]
            aria2_options = a2c_options
        if qbit_opt := db.settings.qbittorrent.find_one({"_id": bot_id}):
            del qbit_opt["_id"]
            qbit_options = qbit_opt
        conn.close()
        BOT_TOKEN = environ.get("BOT_TOKEN", "")
        bot_id = BOT_TOKEN.split(":", 1)[0]
        DATABASE_URL = environ.get("DATABASE_URL", "")
    except Exception as e:
        LOGGER.error(f"Database ERROR: {e}")
else:
    config_dict = {}

if not ospath.exists(".netrc"):
    with open(".netrc", "w"):
        pass
run(
    "chmod 600 .netrc && cp .netrc /root/.netrc && chmod +x aria-nox.sh && ./aria-nox.sh",
    shell=True,
)

OWNER_ID = environ.get("OWNER_ID", "")
if len(OWNER_ID) == 0:
    log_error("OWNER_ID variable is missing! Exiting now")
    exit(1)
else:
    OWNER_ID = int(OWNER_ID)

TELEGRAM_API = environ.get("TELEGRAM_API", "")
if len(TELEGRAM_API) == 0:
    log_error("TELEGRAM_API variable is missing! Exiting now")
    exit(1)
else:
    TELEGRAM_API = int(TELEGRAM_API)

TELEGRAM_HASH = environ.get("TELEGRAM_HASH", "")
if len(TELEGRAM_HASH) == 0:
    log_error("TELEGRAM_HASH variable is missing! Exiting now")
    exit(1)

GDRIVE_ID = environ.get("GDRIVE_ID", "")
if len(GDRIVE_ID) == 0:
    GDRIVE_ID = ""

RCLONE_PATH = environ.get("RCLONE_PATH", "")
if len(RCLONE_PATH) == 0:
    RCLONE_PATH = ""

RCLONE_FLAGS = environ.get("RCLONE_FLAGS", "")
if len(RCLONE_FLAGS) == 0:
    RCLONE_FLAGS = ""

DEFAULT_UPLOAD = environ.get("DEFAULT_UPLOAD", "")
if DEFAULT_UPLOAD != "rc":
    DEFAULT_UPLOAD = "gd"

DOWNLOAD_DIR = environ.get("DOWNLOAD_DIR", "")
if len(DOWNLOAD_DIR) == 0:
    DOWNLOAD_DIR = "/usr/src/app/downloads/"
elif not DOWNLOAD_DIR.endswith("/"):
    DOWNLOAD_DIR = f"{DOWNLOAD_DIR}/"

AUTHORIZED_CHATS = environ.get("AUTHORIZED_CHATS", "")
if len(AUTHORIZED_CHATS) != 0:
    aid = AUTHORIZED_CHATS.split()
    for id_ in aid:
        user_data[int(id_.strip())] = {"is_auth": True}

SUDO_USERS = environ.get("SUDO_USERS", "")
if len(SUDO_USERS) != 0:
    aid = SUDO_USERS.split()
    for id_ in aid:
        user_data[int(id_.strip())] = {"is_sudo": True}

EXTENSION_FILTER = environ.get("EXTENSION_FILTER", "")
if len(EXTENSION_FILTER) > 0:
    fx = EXTENSION_FILTER.split()
    for x in fx:
        x = x.lstrip(".")
        GLOBAL_EXTENSION_FILTER.append(x.strip().lower())

USER_SESSION_STRING = environ.get("USER_SESSION_STRING", "")
if len(USER_SESSION_STRING) != 0:
    log_info("Creating client from USER_SESSION_STRING")
    try:
        user = tgClient('user', TELEGRAM_API, TELEGRAM_HASH, session_string = USER_SESSION_STRING, workers = 1000, parse_mode = enums.ParseMode.HTML, no_updates = True).start()
        IS_PREMIUM_USER = user.me.is_premium
    except:
        log_error("Failed to create client from USER_SESSION_STRING")
        IS_PREMIUM_USER = False
        user = ""
else:
    IS_PREMIUM_USER = False
    user = ""

JD_EMAIL = environ.get("JD_EMAIL", "")
JD_PASS = environ.get("JD_PASS", "")
if len(JD_EMAIL) == 0 or len(JD_PASS) == 0:
    JD_EMAIL = ""
    JD_PASS = ""

FILELION_API = environ.get("FILELION_API", "")
if len(FILELION_API) == 0:
    FILELION_API = ""

STREAMWISH_API = environ.get("STREAMWISH_API", "")
if len(STREAMWISH_API) == 0:
    STREAMWISH_API = ""

INDEX_URL = environ.get("INDEX_URL", "").rstrip("/")
if len(INDEX_URL) == 0:
    INDEX_URL = ""

SEARCH_API_LINK = environ.get("SEARCH_API_LINK", "").rstrip("/")
if len(SEARCH_API_LINK) == 0:
    SEARCH_API_LINK = ""

LEECH_FILENAME_PREFIX = environ.get("LEECH_FILENAME_PREFIX", "")
if len(LEECH_FILENAME_PREFIX) == 0:
    LEECH_FILENAME_PREFIX = ""

SEARCH_PLUGINS = environ.get("SEARCH_PLUGINS", "")
if len(SEARCH_PLUGINS) == 0:
    SEARCH_PLUGINS = ""

MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

LEECH_SPLIT_SIZE = environ.get("LEECH_SPLIT_SIZE", "")
if (
    len(LEECH_SPLIT_SIZE) == 0
    or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE
    or LEECH_SPLIT_SIZE == "2097152000"
):
    LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
else:
    LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

STATUS_UPDATE_INTERVAL = environ.get("STATUS_UPDATE_INTERVAL", "")
if len(STATUS_UPDATE_INTERVAL) == 0:
    STATUS_UPDATE_INTERVAL = 15
else:
    STATUS_UPDATE_INTERVAL = int(STATUS_UPDATE_INTERVAL)

YT_DLP_OPTIONS = environ.get("YT_DLP_OPTIONS", "")
if len(YT_DLP_OPTIONS) == 0:
    YT_DLP_OPTIONS = ""

SEARCH_LIMIT = environ.get("SEARCH_LIMIT", "")
SEARCH_LIMIT = 0 if len(SEARCH_LIMIT) == 0 else int(SEARCH_LIMIT)

LEECH_DUMP_CHAT = environ.get("LEECH_DUMP_CHAT", "")
LEECH_DUMP_CHAT = "" if len(LEECH_DUMP_CHAT) == 0 else LEECH_DUMP_CHAT
if LEECH_DUMP_CHAT.isdigit() or LEECH_DUMP_CHAT.startswith("-"):
    LEECH_DUMP_CHAT = int(LEECH_DUMP_CHAT)

STATUS_LIMIT = environ.get("STATUS_LIMIT", "")
STATUS_LIMIT = 10 if len(STATUS_LIMIT) == 0 else int(STATUS_LIMIT)

CMD_SUFFIX = environ.get("CMD_SUFFIX", "")

RSS_CHAT = environ.get("RSS_CHAT", "")
RSS_CHAT = "" if len(RSS_CHAT) == 0 else RSS_CHAT
if RSS_CHAT.isdigit() or RSS_CHAT.startswith("-"):
    RSS_CHAT = int(RSS_CHAT)

RSS_DELAY = environ.get("RSS_DELAY", "")
RSS_DELAY = 600 if len(RSS_DELAY) == 0 else int(RSS_DELAY)

TORRENT_TIMEOUT = environ.get("TORRENT_TIMEOUT", "")
TORRENT_TIMEOUT = "" if len(TORRENT_TIMEOUT) == 0 else int(TORRENT_TIMEOUT)

QUEUE_ALL = environ.get("QUEUE_ALL", "")
QUEUE_ALL = "" if len(QUEUE_ALL) == 0 else int(QUEUE_ALL)

QUEUE_DOWNLOAD = environ.get("QUEUE_DOWNLOAD", "")
QUEUE_DOWNLOAD = "" if len(QUEUE_DOWNLOAD) == 0 else int(QUEUE_DOWNLOAD)

QUEUE_UPLOAD = environ.get("QUEUE_UPLOAD", "")
QUEUE_UPLOAD = "" if len(QUEUE_UPLOAD) == 0 else int(QUEUE_UPLOAD)

INCOMPLETE_TASK_NOTIFIER = environ.get("INCOMPLETE_TASK_NOTIFIER", "")
INCOMPLETE_TASK_NOTIFIER = INCOMPLETE_TASK_NOTIFIER.lower() == "true"

STOP_DUPLICATE = environ.get("STOP_DUPLICATE", "")
STOP_DUPLICATE = STOP_DUPLICATE.lower() == "true"

IS_TEAM_DRIVE = environ.get("IS_TEAM_DRIVE", "")
IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == "true"

USE_SERVICE_ACCOUNTS = environ.get("USE_SERVICE_ACCOUNTS", "")
USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == "true"

WEB_PINCODE = environ.get("WEB_PINCODE", "")
WEB_PINCODE = WEB_PINCODE.lower() == "true"

AS_DOCUMENT = environ.get("AS_DOCUMENT", "")
AS_DOCUMENT = AS_DOCUMENT.lower() == "true"

EQUAL_SPLITS = environ.get("EQUAL_SPLITS", "")
EQUAL_SPLITS = EQUAL_SPLITS.lower() == "true"

MEDIA_GROUP = environ.get("MEDIA_GROUP", "")
MEDIA_GROUP = MEDIA_GROUP.lower() == "true"

USER_TRANSMISSION = environ.get("USER_TRANSMISSION", "")
USER_TRANSMISSION = USER_TRANSMISSION.lower() == "true" and IS_PREMIUM_USER

BASE_URL_PORT = environ.get("BASE_URL_PORT", "")
BASE_URL_PORT = 80 if len(BASE_URL_PORT) == 0 else int(BASE_URL_PORT)

BASE_URL = environ.get("BASE_URL", "").rstrip("/")
if len(BASE_URL) == 0:
    log_warning("BASE_URL not provided!")
    BASE_URL = ""

UPSTREAM_REPO = environ.get("UPSTREAM_REPO", "")
if len(UPSTREAM_REPO) == 0:
    UPSTREAM_REPO = ""

UPSTREAM_BRANCH = environ.get("UPSTREAM_BRANCH", "")
if len(UPSTREAM_BRANCH) == 0:
    UPSTREAM_BRANCH = "master"

RCLONE_SERVE_URL = environ.get("RCLONE_SERVE_URL", "").rstrip("/")
if len(RCLONE_SERVE_URL) == 0:
    RCLONE_SERVE_URL = ""

RCLONE_SERVE_PORT = environ.get("RCLONE_SERVE_PORT", "")
RCLONE_SERVE_PORT = 8080 if len(RCLONE_SERVE_PORT) == 0 else int(RCLONE_SERVE_PORT)

RCLONE_SERVE_USER = environ.get("RCLONE_SERVE_USER", "")
if len(RCLONE_SERVE_USER) == 0:
    RCLONE_SERVE_USER = ""

RCLONE_SERVE_PASS = environ.get("RCLONE_SERVE_PASS", "")
if len(RCLONE_SERVE_PASS) == 0:
    RCLONE_SERVE_PASS = ""

NAME_SUBSTITUTE = environ.get("NAME_SUBSTITUTE", "")
NAME_SUBSTITUTE = "" if len(NAME_SUBSTITUTE) == 0 else NAME_SUBSTITUTE

MIXED_LEECH = environ.get("MIXED_LEECH", "")
MIXED_LEECH = MIXED_LEECH.lower() == "true" and IS_PREMIUM_USER

####### SERVICES ####### 
CLONE_ENABLED = environ.get('CLONE_ENABLED', '')
CLONE_ENABLED = CLONE_ENABLED.lower() == 'true'

DISABLE_DRIVE_LINK = environ.get('DISABLE_DRIVE_LINK', '')
DISABLE_DRIVE_LINK = DISABLE_DRIVE_LINK.lower() == 'true'

GDRIVE_ENABLED = environ.get('GDRIVE_ENABLED', '')
GDRIVE_ENABLED = GDRIVE_ENABLED.lower() == 'true'

JD_ENABLED = environ.get('JD_ENABLED', '')
JD_ENABLED = JD_ENABLED.lower() == 'true'

LEECH_ENABLED = environ.get('LEECH_ENABLED', '')
LEECH_ENABLED = LEECH_ENABLED.lower() == 'true'

MEGA_ENABLED = environ.get('MEGA_ENABLED', '')
MEGA_ENABLED = MEGA_ENABLED.lower() == 'true'

MIRROR_ENABLED = environ.get('MIRROR_ENABLED', '')
MIRROR_ENABLED = MIRROR_ENABLED.lower() == 'true'

PAID_SERVICE = environ.get('PAID_SERVICE', '')
if len(PAID_SERVICE) == 0:
    PAID_SERVICE = ''

SA_MAIL = environ.get('SA_MAIL', '')
if len(SA_MAIL) == 0:
    SA_MAIL = ''

STOP_DUPLICATE_LEECH = environ.get('STOP_DUPLICATE_LEECH', '')
STOP_DUPLICATE_LEECH = STOP_DUPLICATE_LEECH.lower() == 'true'

TORRENT_ENABLED = environ.get('TORRENT_ENABLED', '')
TORRENT_ENABLED = TORRENT_ENABLED.lower() == 'true'

USER_TD_ENABLED = environ.get('USER_TD_ENABLED', '')
USER_TD_ENABLED = USER_TD_ENABLED.lower() == 'true'

YTDLP_ENABLED = environ.get('YTDLP_ENABLED', '')
YTDLP_ENABLED = YTDLP_ENABLED.lower() == 'true'

####### LIMITS  ####### 
CLONE_LIMIT = environ.get('CLONE_LIMIT', '')
CLONE_LIMIT = '' if len(CLONE_LIMIT) == 0 else float(CLONE_LIMIT)

GDRIVE_LIMIT = environ.get('GDRIVE_LIMIT', '')
GDRIVE_LIMIT = '' if len(GDRIVE_LIMIT) == 0 else float(GDRIVE_LIMIT)

LEECH_LIMIT = environ.get('LEECH_LIMIT', '')
LEECH_LIMIT = '' if len(LEECH_LIMIT) == 0 else float(LEECH_LIMIT)

MEGA_LIMIT = environ.get('MEGA_LIMIT', '')
MEGA_LIMIT = '' if len(MEGA_LIMIT) == 0 else float(MEGA_LIMIT)

MIRROR_LIMIT = environ.get('MIRROR_LIMIT', '')
MIRROR_LIMIT = '' if len(MIRROR_LIMIT) == 0 else float(MIRROR_LIMIT)

STORAGE_THRESHOLD = environ.get('STORAGE_THRESHOLD', '')
STORAGE_THRESHOLD = '' if len(STORAGE_THRESHOLD) == 0 else float(STORAGE_THRESHOLD)

TORRENT_LIMIT = environ.get('TORRENT_LIMIT', '')
TORRENT_LIMIT = '' if len(TORRENT_LIMIT) == 0 else float(TORRENT_LIMIT)

YTDLP_LIMIT = environ.get('YTDLP_LIMIT', '')
YTDLP_LIMIT = '' if len(YTDLP_LIMIT) == 0 else float(YTDLP_LIMIT)

####### BOT TOOLS ####### 
BLACKLIST_FILE_KEYWORDS = environ.get('BLACKLIST_FILE_KEYWORDS', '')
if len(BLACKLIST_FILE_KEYWORDS) > 0:
    fx = BLACKLIST_FILE_KEYWORDS.split()
    for x in fx:
        x = x.lstrip('.')
        GLOBAL_BLACKLIST_FILE_KEYWORDS.append(x.strip().lower())

BOT_MAX_TASKS = environ.get('BOT_MAX_TASKS', '')
BOT_MAX_TASKS = int(BOT_MAX_TASKS) if BOT_MAX_TASKS.isdigit() else ''

BOT_PM = environ.get('BOT_PM', '')
BOT_PM = BOT_PM.lower() == 'true'

DELETE_LINKS = environ.get('DELETE_LINKS', '')
DELETE_LINKS = DELETE_LINKS.lower() == 'true'

FSUB_IDS = environ.get('FSUB_IDS', '')
if len(FSUB_IDS) == 0:
    FSUB_IDS = ''

SAFE_MODE = environ.get('SAFE_MODE', '')
if len(SAFE_MODE) == 0:
    log_warning('SAFE_MODE Is Not Enabled')
    SAFE_MODE = ''

SET_COMMANDS = environ.get('SET_COMMANDS', '')
SET_COMMANDS = SET_COMMANDS.lower() == 'true'

TOKEN_TIMEOUT = environ.get('TOKEN_TIMEOUT', '')
TOKEN_TIMEOUT = '' if len(TOKEN_TIMEOUT) == 0 else float(TOKEN_TIMEOUT)

USER_MAX_TASKS = environ.get('USER_MAX_TASKS', '')
USER_MAX_TASKS = int(USER_MAX_TASKS) if USER_MAX_TASKS.isdigit() else ''

####### UI THEME ####### 
IMAGES = environ.get('IMAGES', '')
IMAGES = (IMAGES.replace("'", '').replace('"', '').replace('[', '').replace(']', '').replace(",", "")).split()

STATUS_HEADER = environ.get('STATUS_HEADER', '')
if len(STATUS_HEADER) == 0:
    STATUS_HEADER = ''

THEME_ENABLED = environ.get('THEME_ENABLED', '')
if len(THEME_ENABLED) == 0:
    THEME_ENABLED = ""

REMOVE_CAPTION = environ.get("REMOVE_CAPTION", "")
if len(REMOVE_CAPTION) == 0:
    REMOVE_CAPTION = ""

MIRROR_LOG_CHAT = environ.get("MIRROR_LOG_CHAT", "")
MIRROR_LOG_CHAT = "" if len(MIRROR_LOG_CHAT) == 0 else MIRROR_LOG_CHAT
if MIRROR_LOG_CHAT.isdigit() or MIRROR_LOG_CHAT.startswith("-"):
    MIRROR_LOG_CHAT = int(MIRROR_LOG_CHAT)

config_dict = {
    "AS_DOCUMENT": AS_DOCUMENT,
    "AUTHORIZED_CHATS": AUTHORIZED_CHATS,
    "BASE_URL": BASE_URL,
    "BASE_URL_PORT": BASE_URL_PORT,
    "BOT_TOKEN": BOT_TOKEN,
    "CMD_SUFFIX": CMD_SUFFIX,
    "DATABASE_URL": DATABASE_URL,
    "DEFAULT_UPLOAD": DEFAULT_UPLOAD,
    "DOWNLOAD_DIR": DOWNLOAD_DIR,
    "EQUAL_SPLITS": EQUAL_SPLITS,
    "EXTENSION_FILTER": EXTENSION_FILTER,
    "FILELION_API": FILELION_API,
    "GDRIVE_ID": GDRIVE_ID,
    "INCOMPLETE_TASK_NOTIFIER": INCOMPLETE_TASK_NOTIFIER,
    "INDEX_URL": INDEX_URL,
    "IS_TEAM_DRIVE": IS_TEAM_DRIVE,
    "JD_EMAIL": JD_EMAIL,
    "JD_PASS": JD_PASS,
    "LEECH_DUMP_CHAT": LEECH_DUMP_CHAT,
    "LEECH_FILENAME_PREFIX": LEECH_FILENAME_PREFIX,
    "LEECH_SPLIT_SIZE": LEECH_SPLIT_SIZE,
    "MEDIA_GROUP": MEDIA_GROUP,
    "MIXED_LEECH": MIXED_LEECH,
    "NAME_SUBSTITUTE": NAME_SUBSTITUTE,
    "OWNER_ID": OWNER_ID,
    "QUEUE_ALL": QUEUE_ALL,
    "QUEUE_DOWNLOAD": QUEUE_DOWNLOAD,
    "QUEUE_UPLOAD": QUEUE_UPLOAD,
    "RCLONE_FLAGS": RCLONE_FLAGS,
    "RCLONE_PATH": RCLONE_PATH,
    "RCLONE_SERVE_URL": RCLONE_SERVE_URL,
    "RCLONE_SERVE_USER": RCLONE_SERVE_USER,
    "RCLONE_SERVE_PASS": RCLONE_SERVE_PASS,
    "RCLONE_SERVE_PORT": RCLONE_SERVE_PORT,
    "REMOVE_CAPTION": REMOVE_CAPTION,
    "RSS_CHAT": RSS_CHAT,
    "RSS_DELAY": RSS_DELAY,
    "SEARCH_API_LINK": SEARCH_API_LINK,
    "SEARCH_LIMIT": SEARCH_LIMIT,
    "SEARCH_PLUGINS": SEARCH_PLUGINS,
    "STATUS_LIMIT": STATUS_LIMIT,
    "STATUS_UPDATE_INTERVAL": STATUS_UPDATE_INTERVAL,
    "STOP_DUPLICATE": STOP_DUPLICATE,
    "STREAMWISH_API": STREAMWISH_API,
    "SUDO_USERS": SUDO_USERS,
    "TELEGRAM_API": TELEGRAM_API,
    "TELEGRAM_HASH": TELEGRAM_HASH,
    "TORRENT_TIMEOUT": TORRENT_TIMEOUT,
    "USER_TRANSMISSION": USER_TRANSMISSION,
    "UPSTREAM_REPO": UPSTREAM_REPO,
    "UPSTREAM_BRANCH": UPSTREAM_BRANCH,
    "USER_SESSION_STRING": USER_SESSION_STRING,
    "USE_SERVICE_ACCOUNTS": USE_SERVICE_ACCOUNTS,
    "WEB_PINCODE": WEB_PINCODE,
    "YT_DLP_OPTIONS": YT_DLP_OPTIONS,
    "CLONE_ENABLED": CLONE_ENABLED,
    "DISABLE_DRIVE_LINK": DISABLE_DRIVE_LINK,
    "GDRIVE_ENABLED": GDRIVE_ENABLED,
    "JD_ENABLED": JD_ENABLED,
    "LEECH_ENABLED": LEECH_ENABLED,
    "MEGA_ENABLED": MEGA_ENABLED,
    "MIRROR_ENABLED": MIRROR_ENABLED,
    "PAID_SERVICE": PAID_SERVICE,
    "SA_MAIL": SA_MAIL,
    "STOP_DUPLICATE_LEECH": STOP_DUPLICATE_LEECH,
    "TORRENT_ENABLED": TORRENT_ENABLED,
    "USER_TD_ENABLED": USER_TD_ENABLED,
    "YTDLP_ENABLED": YTDLP_ENABLED,
    "CLONE_LIMIT": CLONE_LIMIT,
    "GDRIVE_LIMIT": GDRIVE_LIMIT,
    "LEECH_LIMIT": LEECH_LIMIT,
    "MEGA_LIMIT": MEGA_LIMIT,
    "MIRROR_LIMIT": MIRROR_LIMIT,
    "STORAGE_THRESHOLD": STORAGE_THRESHOLD,
    "TORRENT_LIMIT": TORRENT_LIMIT,
    "YTDLP_LIMIT": YTDLP_LIMIT,
    "BLACKLIST_FILE_KEYWORDS": BLACKLIST_FILE_KEYWORDS,
    "BOT_MAX_TASKS": BOT_MAX_TASKS,
    "BOT_PM": BOT_PM,
    "DELETE_LINKS": DELETE_LINKS,
    "FSUB_IDS": FSUB_IDS,
    "SAFE_MODE": SAFE_MODE,
    "SET_COMMANDS": SET_COMMANDS,
    "TOKEN_TIMEOUT": TOKEN_TIMEOUT,
    "USER_MAX_TASKS": USER_MAX_TASKS,
    "IMAGES": IMAGES,
    "STATUS_HEADER": STATUS_HEADER,
    "THEME_ENABLED": THEME_ENABLED,
}

if GDRIVE_ID:
    DRIVES_NAMES.append("Main")
    DRIVES_IDS.append(GDRIVE_ID)
    INDEX_URLS.append(INDEX_URL)

if ospath.exists("list_drives.txt"):
    with open("list_drives.txt", "r+") as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            DRIVES_IDS.append(temp[1])
            DRIVES_NAMES.append(temp[0].replace("_", " "))
            if len(temp) > 2:
                INDEX_URLS.append(temp[2])
            else:
                INDEX_URLS.append("")
                
if ospath.exists('shorteners.txt'):
    with open('shorteners.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            if len(temp) == 2:
                shorteneres_list.append({'domain': temp[0],'api_key': temp[1]})

if BASE_URL:
    Popen(
        f"gunicorn web.wserver:app --bind 0.0.0.0:{BASE_URL_PORT} --worker-class gevent",
        shell=True,
    )

if ospath.exists('accounts.zip'):
    if ospath.exists('accounts'):
        run(["rm", "-rf", "accounts"])
    run(["7z", "x", "accounts.zip", "-oaccounts", "-aoa", "*.json"])
    run(["chmod", "-R", "777", "accounts"])
    remove('accounts.zip')
if not ospath.exists("accounts"):
    config_dict["USE_SERVICE_ACCOUNTS"] = False


def get_qb_client():
    return qbClient(
        host="localhost",
        port=8090,
        VERIFY_WEBUI_CERTIFICATE=False,
        REQUESTS_ARGS={"timeout": (30, 60)},
    )


aria2c_global = [
    "bt-max-open-files",
    "download-result",
    "keep-unfinished-download-result",
    "log",
    "log-level",
    "max-concurrent-downloads",
    "max-download-result",
    "max-overall-download-limit",
    "save-session",
    "max-overall-upload-limit",
    "optimize-concurrent-downloads",
    "save-cookies",
    "server-stat-of",
]

log_info("Creating client from BOT_TOKEN")
bot = tgClient(
    "bot",
    TELEGRAM_API,
    TELEGRAM_HASH,
    bot_token=BOT_TOKEN,
    workers=1000,
    parse_mode=enums.ParseMode.HTML,
).start()
bot_loop = bot.loop
bot_name = bot.me.username

scheduler = AsyncIOScheduler(timezone=str(get_localzone()), event_loop=bot_loop)

if not qbit_options:
    qbit_options = dict(get_qb_client().app_preferences())
    del qbit_options["listen_port"]
    for k in list(qbit_options.keys()):
        if k.startswith("rss"):
            del qbit_options[k]
else:
    qb_opt = {**qbit_options}
    for k, v in list(qb_opt.items()):
        if v in ["", "*"]:
            del qb_opt[k]
    get_qb_client().app_set_preferences(qb_opt)

aria2 = ariaAPI(ariaClient(host="http://localhost", port=6800, secret=""))
if not aria2_options:
    aria2_options = aria2.client.get_global_option()
else:
    a2c_glo = {op: aria2_options[op] for op in aria2c_global if op in aria2_options}
    aria2.set_global_options(a2c_glo)
