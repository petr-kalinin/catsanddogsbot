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
import collections

import db as db_module
from analyze import analyze_new, download, Status, MAX_START, CouldNotLoadError

TOKEN = sys.argv[1]
SOURCE_URL = sys.argv[2]

BOT_NAME="catsanddogsbot"

MIN_TIME_FOR_SUBSTANTIAL = 25
MIN_TIME_FOR_SUBSTANTIAL_END = 10

HELP = """
*Все сообщения от бота — в канале @catsanddogs_nnov*

Этот бот знает, ожидается ли в ближайшее время в Нижнем Новгороде сильный дождь, гроза или град.

Каждые 10 минут бот получает с метеорадаров данные, на которых видно, где сейчас идет дождь. Бот экстраполирует их на ближайший час и исходя из этого определяет, ожидается ли дождь в Нижнем Новгороде в ближайшее время. 

Сообщения о приближающемся дожде бот высылает в канал @catsanddogs_nnov. Подпишитесь на этот канал, чтобы оперативно узнавать об изменениях прогноза.

Кроме того, бот высылает текущий прогноз в ответ на любое сообщение от вас.

Особенности:
1. Метеорадары довольно плохо детектируют слабый дождь, поэтому бот предупреждает только о сильном дожде, грозе и граде. 
2. Метеорадары передают информацию раз в 10 минут, поэтому информация от бота не может быть точнее 10 минут.
3. Бот получает данные от метеорадаров в довольно низком пространственном разрешении, поэтому бот не может надежно предсказывать дождь отдельно по разным частям города.
4. Алгоритм экстраполяции данных не самый идеальный, поэтому на деле точность что по времени, что по пространству, может быть хуже (например, если бот обещает грозу через 40 минут, то на самом деле может оказаться, что гроза будет через 50 минут и на Бору, а не в Нижнем Новгороде).
5. Если бот раньше предупреждал вас о том, что ожидаются осадки, а потом, по новым данным, оказалось, что осадков не будет, то бот пришлет об этом сообщение.
6. Бот указывает длительность осадков, если она не очень большая. Если ожидается довольно длительный дождь, то бот не указывает его длительность.
"""

POINTS = {
    "nnov:center": "Нижний Новгород, центр",
    "nnov:avtozavod": "Нижний Новгород, Автозавод",
    "nnov:sormovo": "Нижний Новгород, Сормово",
    "msk:center": "Москва, центр",
    "msk:north": "Москва, север",
    "msk:south": "Москва, юг",
    "msk:west": "Москва, запад",
    "msk:east": "Москва, восток",
    "spb:center": "Санкт-Петербург, центр",
    "spb:north": "Санкт-Петербург, север",
    "spb:south": "Санкт-Петербург, юг",
    "spb:east": "Санкт-Петербург, восток",
    "sis:": "Берендеевы поляны"
}

TYPE_CLOUD = 2
TYPE_RAIN = 3
TYPE_STORM = 4
TYPE_HAIL = 5


db = db_module.Db()


def now_min():
    return int(datetime.now().timestamp() / 60)


def format_status(status):
    if int(status.type) <= TYPE_CLOUD:
        return "в ближайшее время сильных осадков не ожидается"
    now = now_min()
    text = ''
    if status.start < now + 5:
        text = 'в ближайшее время ожидается '
    else:
        text = 'через %d минут ожидается ' % round(status.start - now, -1)
    
    if int(status.type) == TYPE_RAIN:
        text += 'сильный дождь'
    elif int(status.type) == TYPE_STORM:
        text += 'гроза'
    elif int(status.type) == TYPE_HAIL:
        text += 'гроза с градом'
    else:
        text += '???' + str(status.type)
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
    message = []
    for key in POINTS:
        if not key in status:
            print("{}: not found in new status!".format(key))
            continue
        this_status = format_status(status[key])
        message.append("{}: {}".format(POINTS[key], this_status))
    message.sort()
    return "\n".join(message)


def handle(msg):
    pprint(msg)
    message = msg["text"].strip()
    user = msg['from']['id']
    if message == "/start" or message == "/help":
        message = HELP
    else:
        message = status()
    bot.sendMessage(user, message)
    
    
def substantial_change(a, b):
    if abs(a.type - b.type) < 0.3:
        return False
    if int(b.type) <= TYPE_CLOUD and int(a.type) <= TYPE_CLOUD:
        return False
    if int(b.type) <= TYPE_CLOUD:
        return True
    if int(a.type) <= TYPE_CLOUD:
        return True
    if int(a.type) != int(b.type):
        return True
    return (abs(a.start - b.start) > MIN_TIME_FOR_SUBSTANTIAL
        or abs(a.end - b.end) > 2 * MIN_TIME_FOR_SUBSTANTIAL)


def send_all(messages):
    for chat in messages:
        user = "@catsanddogs_{}".format(chat)
        message_to_send = []
        for message in messages[chat]:
            location, status = message
            status_text = format_status(status)
            message_to_send.append("{}: {}".format(location, status_text))
        if not message_to_send:
            print("{}: no message to send".format(user))
            continue
        message_text = "\n".join(message_to_send)
        try:
            print("{}: Sending message {}".format(user, message_text))
            if bot:
                bot.sendMessage(user, message_text)
            else:
                print("Working in dry-run mode")
        except:
            pass

    
def process_new_status(new_status, old_status):
    status_to_save = new_status
    messages_to_send = collections.defaultdict(list)
    for key in POINTS:
        if not key in old_status:
            print("{}: not found in old status".format(key))
            continue
        if not key in new_status:
            print("{}: not found in new status!".format(key))
            continue
        if not substantial_change(old_status[key], new_status[key]):
            print("{}: Change is not substantiual".format(key))
            status_to_save[key] = old_status[key]
            continue
        chat, _ = key.split(":")
        messages_to_send[chat].append((POINTS[key], new_status[key]))
        
    send_all(messages_to_send)
    return status_to_save
    

def update_forecast():
    last_hash = db.getHash()
    new_file, new_hash = download(SOURCE_URL, last_hash)
    if not new_file:
        print("File not changed, hash=", last_hash)
        return
    print("Detected new file!")
    
    now = now_min() - 2
    new_status = analyze_new(new_file)
    print("New status: ", new_status)
    for key in new_status:
        if new_status[key].start > MAX_START:
            new_status[key] = Status(1e20, 1e20, 0)
        else:
            new_status[key] = Status(new_status[key].start + now, new_status[key].end + now, new_status[key].type)
    
    old_status = db.getStatus()
    print("Old status: ", old_status)
    
    status_to_save = process_new_status(new_status, old_status)

    db.setStatus(status_to_save)
    db.setHash(new_hash)
    
            
if TOKEN != "_":
    bot = telepot.Bot(TOKEN)
    MessageLoop(bot, handle).run_as_thread()
    print ('Listening ...')
else:
    bot = None

while 1:
    print("Trying to download")
    try:
        update_forecast()
    except CouldNotLoadError:
        pass
    time.sleep(120)
