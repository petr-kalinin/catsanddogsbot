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
from analyze import analyze_new, download, Status, MAX_START, CouldNotLoadError

TOKEN = sys.argv[1]
SOURCE_URL = sys.argv[2]

BOT_NAME="catsanddogsbot"

MIN_TIME_FOR_SUBSTANTIAL = 20
MIN_TIME_FOR_SUBSTANTIAL_END = 10

HELP = """
Этот бот предупредит вас, если в ближайшее время в Нижнем Новгороде будет ожидаться сильный дождь, гроза или град.

Каждые 10 минут бот получает с метеорадаров данные, на которых видно, где сейчас идет дождь. Бот экстраполирует их на ближайшие 1-2 часа и исходя из этого определяет, ожидается ли дождь в Нижнем Новгороде в ближайшее время. Сообщения о приближающемся дожде бот присылает всем его подписчикам.

Инструкция по эксплуатации:
Команда /start подписывает вас на уведомления от бота (если вы видите этот текст, то вы только что подписались).
Команда /stop отписывает вас от уведомлений.
Любое другое сообщение боту — получить текущую информацию об ожидаемых осадках (независимо от того, подписаны вы или нет).

Особенности:
1. Метеорадары довольно плохо детектируют слабый дождь, поэтому бот предупреждает только о сильном дожде, грозе и граде. 
2. Метеорадары передают информацию раз в 10 минут, поэтому информация от бота не может быть точнее 10 минут.
3. Бот получает данные от метеорадаров в довольно низком пространственном разрешении, поэтому бот не может надежно предсказывать дождь отдельно по разным частям города.
4. Алгоритм экстраполяции данных не самый идеальный, поэтому на деле точность что по времени, что по пространству, может быть хуже (например, если бот обещает грозу через 40 минут, то на самом деле может оказаться, что гроза будет через 50 минут и на Бору, а не в Нижнем Новгороде).
5. Если бот раньше предупреждал вас о том, что ожидаются осадки, а потом, по новым данным, оказалось, что осадков не будет, то бот пришлет об этом сообщение.
6. Бот указывает длительность осадков, если она не очень большая. Если ожидается довольно длительный дождь, то бот не указывает его длительность.
"""

db = db_module.Db()


def now_min():
    return int(datetime.now().timestamp() / 60)


def format_status(status):
    if not status:
        return "В ближайшее время сильных осадков не ожидается"
    now = now_min()
    text = ''
    if status.start < now + 5:
        text = 'В ближайшее время ожидается '
    else:
        text = 'Через %d минут ожидается ' % round(status.start - now, -1)
    if status.type == 1:
        text += 'сильный дождь'
    elif status.type == 2:
        text += 'гроза'
    elif status.type == 3:
        text += 'гроза с градом'
    else:
        text += '???'
    end_time = status.end - now
    if end_time < MAX_START:
        length = status.end - status.start
        if length < 10:
            length = 10
        text += ' длительностью %d минут' % round(length, -1)
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
        if message == "/start":
            message = HELP
            db.addUser(user)
        else:
            message = status()
    bot.sendMessage(user, message)
    
    
def substantial_change(a, b):
    now = now_min()
    if not b and not a:
        return False
    if not b:
        return True #a.end > now + MIN_TIME_FOR_SUBSTANTIAL_END
    if not a:
        return True
    if a.type != b.type:
        return True
    return (abs(a.start - b.start) > MIN_TIME_FOR_SUBSTANTIAL
        or abs(a.end - b.end) > 2 * MIN_TIME_FOR_SUBSTANTIAL)


def send_all(status):
    users = db.getUsers()
    status_text = format_status(status)
    for user in users:
        try:
            bot.sendMessage(user, status_text)
        except:
            pass

    
def update_forecast():
    last_hash = db.getHash()
    new_file, new_hash = download(SOURCE_URL, last_hash)
    if not new_file:
        print("File not changed, hash=", last_hash)
        return
    print("Detected new file!")
    
    new_status = analyze_new(new_file)
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
    
            
bot = telepot.Bot(TOKEN)

MessageLoop(bot, handle).run_as_thread()
print ('Listening ...')

while 1:
    print("Trying to download")
    try:
        update_forecast()
    except CouldNotLoadError:
        pass
    time.sleep(120)
