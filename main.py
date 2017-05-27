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
import pdb

import db as db_module
from analyze import analyze, download, Status, MAX_START

BOT_NAME="catsanddogsbot"

MIN_TIME_FOR_SUBSTANTIAL = 20
MIN_TIME_FOR_SUBSTANTIAL_END = 10

HELP = "help"

db = db_module.Db()


def now_min():
    return int(datetime.now().timestamp() / 60)


def format_status(status):
    if not status:
        return "В ближайшее время дождя не ожидается"
    now = now_min()
    text = ''
    if status.start < now:
        text = 'В ближайшее время ожидается '
    else:
        text = 'Через %d минут ожидается ' % (status.start - now)
    if status.type == 1:
        text += 'сильный дождь'
    elif status.type == 2:
        text += 'гроза'
    elif status.type == 3:
        text += 'град'
    else:
        text += '???'
    end_time = status.end - now
    if end_time < MAX_START:
        text += ', длительностью %d минут' % (status.end - status.start)
    text += "."
    return text


def status():
    status = db.getStatus()
    return format_status(status)


def handle(msg):
    pprint(msg)
    message = msg["text"].strip()
    user = msg['from']['id']
    if message == "/stop":
        db.removeUser(user)
        message = "Удалил вас из списка подписчиков"
    else:
        db.addUser(user)
        if message == "/start":
            message = HELP
        else:
            message = status()
    bot.sendMessage(user, message)
    
    
def substantial_change(a, b):
    now = now_min()
    if not b and not a:
        return False
    if not b:
        return a.end > now + MIN_TIME_FOR_SUBSTANTIAL_END
    if not a:
        return True
    if a.type != b.type:
        return True
    return abs(a.start - b.start) > MIN_TIME_FOR_SUBSTANTIAL


def send_all(status):
    users = db.getUsers()
    status_text = format_status(status)
    for user in users:
        bot.sendMessage(user, status_text)
            

    
def update_forecast():
    last_hash = db.getHash()
    new_file, new_hash = download(last_hash)
    if not new_file:
        print("File not changed, hash=", last_hash)
        return
    print("Detected new file!")
    
    new_status = analyze(new_file)
    print("New status: ", new_status)

    now = now_min()
    if new_status:
        new_status = Status(new_status.start + now, new_status.end + now, new_status.type)
    
    old_status = db.getStatus()
    if not old_status:
        # set new status in case we have no old status at all
        db.setStatus(old_status)
    if not substantial_change(old_status, new_status):
        print("Change is not substantiual")
        db.setHash(new_hash)
        return
    db.setStatus(new_status)
    db.setHash(new_hash)
    send_all(new_status)
    
            
TOKEN = sys.argv[1]  # get token from command-line
bot = telepot.Bot(TOKEN)

MessageLoop(bot, handle).run_as_thread()
print ('Listening ...')

while 1:
    print("Trying to download")
    update_forecast()
    time.sleep(120)
