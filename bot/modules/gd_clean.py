#!/usr/bin/env python3
from random import randrange
from pickle import load as pload
from logging import getLogger, ERROR
from os import path as ospath, listdir
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pyrogram.filters import command, regex
from pyrogram.handlers import MessageHandler

from bot import bot, config_dict
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.ext_utils.bot_utils import sync_to_async, new_task, is_gdrive_link, get_readable_file_size

LOGGER = getLogger(__name__)
getLogger('googleapiclient.discovery').setLevel(ERROR)


def authorize_with_service_accounts():
    json_files = listdir("accounts")
    sa_number = len(json_files)
    sa_index = randrange(sa_number)
    LOGGER.info(f"Authorizing with {json_files[sa_index]} service account")
    credentials = service_account.Credentials.from_service_account_file(f'accounts/{json_files[sa_index]}', scopes=['https://www.googleapis.com/auth/drive'])
    return credentials


def authorize_with_token_pickle():
    LOGGER.info(f"Authorizing with token.pickle")
    with open('token.pickle', 'rb') as f:
        credentials = pload(f)
        return credentials


@new_task
async def clean(credentials, message):
    try:
        service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
    except HttpError as error:
        await message.reply(f'An error occurred: {error}')
        return
    LOGGER.info(f"Trying to clean drive")
    query = "'%s' in parents and trashed = false" % config_dict['GDRIVE_ID']
    page_token = None
    while True:
        try:
            response = service.files().list(q=query, spaces='drive', fields='nextPageToken, files(id, name)', pageToken=page_token, includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
            files = response.get('files', [])
            for file in files:
                service.files().delete(fileId=file['id'], supportsAllDrives=True).execute()
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                await message.reply('Drive cleanup completed! 🚮')
                break
        except HttpError as err:
            await message.reply(f"An error occurred: {err}")
            break


async def drive_clean(client, message):
    credentials = None
    if config_dict.get('USE_SERVICE_ACCOUNTS') and ospath.exists('accounts'):
        try:
            credentials = authorize_with_service_accounts()
            await clean(credentials, message)
        except Exception as e:
            print(f"An error occurred: {e}")
            pass
    elif not config_dict.get('USE_SERVICE_ACCOUNTS') and ospath.exists("token.pickle"):
        try:
            credentials = authorize_with_token_pickle()
            await clean(credentials, message)
        except Exception as e:
            print(f"An error occurred: {e}")
            pass
    else:
        await message.reply(f"service accounts or token.pickle not found for authorization")


bot.add_handler(MessageHandler(drive_clean, filters=command("gdclean") & CustomFilters.owner))
