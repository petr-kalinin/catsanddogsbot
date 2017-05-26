#!/usr/bin/python3
import logging
import sys
import re
import time
import threading
import random
import telepot
from telepot.loop import MessageLoop
from pprint import pprint
from datetime import datetime
import traceback
import pymongo
import pdb

from analyze import analyze, download, MAX_START

BOT_NAME="catsanddogsbot"

client = pymongo.MongoClient()
db = client.rain

USERS_KEY = {'_id': 'users'}
STATUS_KEY = {'_id': 'status'}
HASH_KEY = {'_id': 'hash'}

MIN_TIME_FOR_SUBSTANTIAL = 20

HELP = "help"


def now_min():
    return int(datetime.now().timestamp() / 60)


def format_status(status):
    if len(status) == 0:
        return "В ближайшее время дождя не ожидается"
    now = now_min()
    text = ''
    if status['start'] < now:
        text = 'В ближайшее время ожидается '
    else:
        text = 'Через %d минут ожидается ' % (status['start'] - now)
    if status['type'] == 1:
        text += 'сильный дождь'
    elif status['type'] == 2:
        text += 'гроза'
    elif status['type'] == 3:
        text += 'град'
    else:
        text += '???'
    end_time = status['end'] - now
    if end_time < MAX_START:
        text += ', длительностью %d минут' % (status['end'] - status['start'])
    text += "."
    return text


def status():
    status = db.rain.find_one(STATUS_KEY)
    if not status:
        return "Прогноза нет"
    else:
        return format_status(status['status'])


def handle(msg):
    pprint(msg)
    #bot.sendMessage(999999999, 'Hey!')
    if not db.rain.find_one(USERS_KEY):
        db.rain.insert(USERS_KEY, {'users': []})
    message = msg["text"].strip()
    user = msg['from']['id']
    if message == "/stop":
        cmd = '$pull'
    else:
        cmd = '$addToSet'
    db.rain.find_one_and_update(USERS_KEY, {cmd: {'users': user}})
    if message == "/start":
        message = HELP
    elif message == "/stop":
        message = "Удалил вас из списка подписчиков"
    else:
        message = status()
    bot.sendMessage(user, message)
    
    
def substantial_change(a, b):
    now = now_min()
    if not b and not a:
        return False
    if not b:
        return a['start'] > now + MIN_TIME_FOR_SUBSTANTIAL
    if not a:
        return True
    if a['type'] != b['type']:
        return True
    return abs(a['start'] - b['start']) > MIN_TIME_FOR_SUBSTANTIAL


def send_all(status):
    users = db.rain.find_one(USERS_KEY)
    if not users:
        return
    status_text = format_status(status)
    for user in users['users']:
        bot.sendMessage(user, status_text)
            

    
def update_forecast():
    last_hash = db.rain.find_one(HASH_KEY)
    if last_hash:
        last_hash = last_hash['hash']
    new_file, new_hash = download(last_hash)
    if not new_file:
        print("File not changed")
        return
    print("Detected new file!")
    
    status = analyze(new_file)
    print("New status: ", status)
    
    now = now_min()
    if status:
        new_status = {'start': status.start + now, 'end': status.end + now, 'type': status.type}
    else:
        new_status = {}
    
    old_status = db.rain.find_one(STATUS_KEY)
    if old_status:
        old_status = old_status['status']
    else:
        # set new status in case we have no old status at all
        db.rain.find_one_and_replace(STATUS_KEY, {'status': new_status}, upsert=True)
    if not substantial_change(old_status, new_status):
        print("Change is not substantiual")
        return
    db.rain.find_one_and_replace(STATUS_KEY, {'status': new_status}, upsert=True)
    send_all(new_status)

    db.rain.find_one_and_replace(HASH_KEY, {'hash': new_hash}, upsert=True)
    
            
TOKEN = sys.argv[1]  # get token from command-line
bot = telepot.Bot(TOKEN)

MessageLoop(bot, handle).run_as_thread()
print ('Listening ...')

while 1:
    print("Trying to download")
    update_forecast()
    time.sleep(120)
