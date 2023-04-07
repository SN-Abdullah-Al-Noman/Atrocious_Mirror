from re import findall
from time import sleep
from html import escape
from threading import Thread
from os import path as ospath
from datetime import datetime
from pickle import load as pload
from base64 import urlsafe_b64decode
from googleapiclient.discovery import build
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot import bot, dispatcher, updater, OWNER_ID

SCOPES = ["https://mail.google.com/"]

if ospath.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        credentials = pload(token)
        if not credentials or not credentials.valid:
            raise Exception("Invalid or missing credentials")
        elif not all(scope in credentials.scopes for scope in SCOPES):
            raise Exception("Missing required Gmail API scopes in credentials")
else:
    credentials = None

if 'https://mail.google.com/' not in credentials.scopes:
    print('Gmail API not enabled in token.pickle. Exiting...')
    exit()

service = build('gmail', 'v1', credentials)

def fetch_unread_messages():
    query = 'is:unread from:(drivesafety-noreply@google.com)'
    messages = service.users().messages().list(userId='me', q=query).execute()
    unread_messages = messages.get('messages', [])
    for message in unread_messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        message_labels = msg['labelIds']
        message_labels.remove('UNREAD')
        updated_message = service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD'], 'addLabelIds': message_labels}).execute()
    return unread_messages


def format_message(message):
    msg = service.users().messages().get(userId='me', id=message['id']).execute()
    sender_name = [header['value'] for header in msg['payload']['headers'] if header['name'] == 'From'][0].split('<')[0].strip()
    sender_email = [header['value'] for header in msg['payload']['headers'] if header['name'] == 'From'][0].split('<')[1].strip('>')
    date = [header['value'] for header in msg['payload']['headers'] if header['name'] == 'Date'][0]
    date_obj = datetime.strptime(date[:-6], '%a, %d %b %Y %H:%M:%S')
    date_str = date_obj.strftime('%a, %d %b %Y')
    time_str = date_obj.strftime('%I:%M:%S %p')
    body = msg['snippet']

    payload = msg['payload']
    if 'parts' in payload:
        parts = payload['parts']
        data = parts[0]['body']['data']
    else:
        data = payload['body']['data']
    message_body = urlsafe_b64decode(data).decode()

    urls = findall(r'(https://notifications\.googleapis\.com/email/redirect\S+)', message_body)
    if urls:
        gdrive_link = urls[0]
        if len(urls) > 1:
            gdrive_link = urls[1]

    msg = f"<b>Alert ⚠️</b>\n"
    msg += f"<b>New File Copyright Email Received 📩</b>\n\n"
    msg += f"<b>Sender Name:</b> {escape(sender_name)}\n"
    msg += f"<b>Address:</b> {escape(sender_email)}\n\n"
    msg += f"<b>Date:</b> {date_str}\n"
    msg += f"<b>Time:</b> {time_str}\n\n"
    msg += f"<b>Mail:</b> {body}\n\n"
    msg += f"<b>File Link:</b> {escape(gdrive_link)}"
    delete_button = InlineKeyboardButton('Delete This Email', callback_data=f"delete_{message['id']}")
    keyboard = [[delete_button]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return msg, reply_markup


def mail(update, context):
    messages = fetch_unread_messages()
    if not messages:
        pass
    else:
        for message in messages:
            formatted_message, reply_markup = format_message(message)
            context.bot.send_message(chat_id=OWNER_ID, text=formatted_message, reply_markup=reply_markup)


def button_callback(update, context):
    query = update.callback_query
    query.answer()
    message_id = query.data.split("_")[1]
    service.users().messages().delete(userId='me', id=message_id).execute()
    query.edit_message_text(text="Email deleted Successfully.")

def run_mail_loop():
    while True:
        mail(None, updater)
        sleep(300)


mail_thread = Thread(target=run_mail_loop)
mail_thread.start()

dispatcher.add_handler(CallbackQueryHandler(button_callback))
