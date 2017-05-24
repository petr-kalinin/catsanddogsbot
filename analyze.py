#!/usr/bin/python3
from urllib import request
from datetime import datetime
import os
from PIL import Image
import time
from collections import namedtuple
import numpy

URL = "***REMOVED***"
DIR = "images"
NNOV = (612,448)
TEST = (414, 317)

TYPE_STORM = 2
TYPE_RAIN = 1
TYPE_NONE = 0

Range = namedtuple('Range', 'start end')
Status = namedtuple('Status', 'start end type')


def download():
    os.makedirs(DIR, exist_ok=True)
    response = request.urlopen(URL)
    data = response.read()
    fname = DIR + "/" + datetime.now().isoformat() + ".gif"
    with open(fname, "wb") as f:
        f.write(data)
    return fname


def merge(range1, range2):
    if not range1:
        return range2
    if not range2:
        return range1
    return Range(min(range1.start, range1.end), max(range2.start, range2.end))


def is_rain_color(color):
    r, g, b = color
    return b > 2*g and b > 2*r


def is_storm_color(color):
    r, g, b = color
    return ((r > 1.3*g and r > 2*b) # reds
        or (g > 2*r and g > 2*b) # greens
        or (r > 3*g and b > 3*g and r > 0.5*b and b > 0.5*r)) # violets
        
        
def is_none_color(color):
    r, g, b = numpy.int_(color)
    a = (r + g + b) / 3
    return r > 0.8*a and b > 0.8*a and g > 0.8*a
    
        
def is_fixed_point(im, x, y):
    col = im[0][y][x]
    if is_none_color(col):
        return False
    for subim in im:
        if numpy.any(subim[y][x] != col):
            return False
    return True


def colorize(im):
    result = Image.new("RGB", (im[0].shape[1], im[0].shape[0]))
    print(im[0].shape)
    for x in range(im[0].shape[1]):
        print(x)
        for y in range(im[0].shape[0]):
            try:
                sourceColor = im[-1][y][x]
                if is_fixed_point(im, x, y):
                    color = (0, 0, 0)
                elif is_none_color(sourceColor):
                    color = (128, 128, 128)
                elif is_rain_color(sourceColor):
                    color = (0, 0, 256)
                elif is_storm_color(sourceColor):
                    color = (256, 0, 0)
                else:
                    color = (0, 256, 0)
                result.putpixel((x, y), color)
            except BaseException:
                result.save("test.png")
                return
    result.save("test.png")
    
    
def load_image(fname):
    im = Image.open(fname)
    res = []
    while True:
        res.append(numpy.array(im.convert("RGB")))
        try:
            im.seek(im.tell() + 1)
        except EOFError:
            break
    return res


def analyze(fname):
    im = load_image(fname)
    return colorize(im)

    stormRange = None
    rainRange = None
    for d in range(30):
        stormRange = merge(stormRange, calcRange(im, is_storm_color))
        rainRange = merge(rainRange, calcRange(im, is_rain_color))
    if not stormRange:
        if not rainRange:
            return Status(None, None, TYPE_NONE)
        return Status(rainRange.start, rainRange.end, TYPE_RAIN)
    if not rainRange:
        return Status(stormRange.start, stormRange.end, TYPE_STORM)
    if rainRange.end < stormRange.start:
        return Status(rainRange.start, rainRange.end, TYPE_RAIN)
    if stormRange.end < rainRange.start:
        return Status(stormRange.start, stormRange.end, TYPE_STORM)
    stormRange = merge(stormRange, rainRange)
    return Status(stormRange.start, stormRange.end, TYPE_STORM)
        
print(analyze("images/2017-05-24T22:02:54.640131.gif"))
    
