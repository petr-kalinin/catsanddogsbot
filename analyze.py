#!/usr/bin/python3
from urllib import request
from datetime import datetime
import os
from PIL import Image
import time
from collections import namedtuple
import numpy
import math
import hashlib
import sys

IS_MAIN = __name__ == '__main__'

DIR = "images"
NNOV = (612,448)
#TEST = (420, 317)
#TEST = (365, 306)
#TEST = (240, 559)
#TEST = (569, 444)
#TEST = (625, 381)
#TEST = (627, 447)
TEST = NNOV

TYPE_HAIL = 3
TYPE_STORM = 2
TYPE_RAIN = 1
TYPE_NONE = 0

PERIOD = 10  # minutes

RADIUS = 96  # pixels
DIRECTIONS = 96  # better to be multiple of 8

FRAMES_OFFSET = 6  # how many cloned frames at gif end
FRAMES_CONSIDER = 9

MAX_TIME = 100*PERIOD
MAX_START = 1.5 * 60
MIN_LENGTH = 3

Range = namedtuple('Range', 'start end')
Status = namedtuple('Status', 'start end type')


class CouldNotLoadError(Exception):
    pass


def download(url, last_hash=None):
    os.makedirs(DIR, exist_ok=True)
    response = request.urlopen(url)
    try:
        data = response.read()
    except:
        return None, last_hash
    new_hash = hashlib.md5(data).hexdigest()
    if new_hash == last_hash:
        return None, last_hash

    fname = DIR + "/" + datetime.now().isoformat() + ".gif"
    with open(fname, "wb") as f:
        f.write(data)
    return fname, new_hash


def load_image(fname):
    try:
        im = Image.open(fname)
        res = []
        while True:
            res.append(numpy.array(im.convert("RGB")))
            try:
                im.seek(im.tell() + 1)
            except EOFError:
                break
        return res
    except:
        raise CouldNotLoadError()


def is_rain_color(color):
    r, g, b = color
    return b > 2*g and b > 2*r


def is_storm_color(color):
    r, g, b = color
    return (r > 1.3*g and r > 2*b)


def is_hail_color(color):
    r, g, b = color
    return ((g > 2*r and g > 2*b) # greens
        or (r > 3*g and b > 3*g and r > 0.5*b and b > 0.5*r)) # violets
        
        
def is_none_color(color):
    return not  (is_rain_color(color) or is_storm_color(color) or is_hail_color(color))
    
        
def is_fixed_point(im, x, y):
    col = im[0][y][x]
    if is_none_color(col):
        return False
    for subim in im:
        if numpy.any(subim[y][x] != col):
            return False
    return True


def solve_reg(xs, ys):
    if len(xs) <= 2:
        return None
    xs = numpy.array(xs)
    ys = numpy.array(ys)
    if all(ys == ys[0]):
        return None
    r = numpy.corrcoef(xs, ys)[0][1]
    if IS_MAIN:
        print("xs=",xs, "ys=",ys)
        print("r=",r)
    if r > -0.93:
        return None
    A = numpy.vstack([xs, numpy.ones(len(xs))]).T
    k, b = numpy.linalg.lstsq(A, ys)[0]
    if IS_MAIN:
        print("kb=", k, b)
    if abs(k) < 1:  # this is pixels per period
        return None
    return -b / k
    


def calcRange(im, center, is_needed_color, angle):
    starts = []
    ends = []
    sxs = []
    exs = []
    for d in range(-FRAMES_CONSIDER+1, 1):
        start = None
        end = None
        for i in range(RADIUS):
            x = int(center[0] + i * math.cos(angle))
            y = int(center[1] + i * math.sin(angle))
            if is_fixed_point(im, x, y):
                continue
            color = im[d - FRAMES_OFFSET][y][x]
            if start is None and is_needed_color(color):
                start = i
            if start is not None and end is None and is_none_color(color):
                end = i
                break
        if start is not None:
            starts.append(start)
            sxs.append(d)
            if d >= -3:
                starts.append(start)
                sxs.append(d)
        if end is not None:
            ends.append(end)
            exs.append(d)
            if d >= -3:
                ends.append(end)
                exs.append(d)
    if len(starts) < 0.7 * FRAMES_CONSIDER:
        return None
    expected_start = solve_reg(sxs, starts)
    if expected_start:
        expected_start *= PERIOD
    expected_end = solve_reg(exs, ends)
    if len(ends) < 0.5 * FRAMES_CONSIDER:
        expected_end = None
    if expected_end:
        expected_end *= PERIOD
    if IS_MAIN and expected_start:
        print("Angle = ", angle)
        print("starts=",starts, sxs)
        print(" ".join(["(%d %d)" % (int(center[0] + i * math.cos(angle)), int(center[1] + i * math.sin(angle)))
                        for i in starts]))
        print("ends=",ends, exs)
        print(" ".join(["(%d %d)" % (int(center[0] + i * math.cos(angle)), int(center[1] + i * math.sin(angle)))
                        for i in ends]))
        print("expecteds=", expected_start, expected_end)
    if not expected_start or expected_start < -PERIOD or expected_start > MAX_START:
        return None
    if not expected_end:
        return Range(expected_start, MAX_TIME)
    if expected_end < expected_start - PERIOD:
        return None
    return Range(expected_start, expected_end)


def merge(range1, range2):
    if not range1:
        return range2
    if not range2:
        return range1
    return Range(min(range1.start, range2.start), max(range1.end, range2.end))


def analyze(fname, center=NNOV):
    #return Status(13, 27, TYPE_STORM)
    TYPES = ((TYPE_RAIN, is_rain_color),
             (TYPE_STORM, is_storm_color),
             (TYPE_HAIL, is_hail_color))
    
    im = load_image(fname)
    #return colorize(im)
    statuses = []
    for t in TYPES:
        if IS_MAIN:
            print("Type ", t[0])
        r = None
        for d in range(DIRECTIONS):
            r = merge(r, calcRange(im, center, t[1], d / DIRECTIONS * 2 * math.pi))
        if r:
            statuses.append(Status(r.start, r.end, t[0]))
    if len(statuses) == 0:
        return None
    statuses.sort(key = lambda r: r.start)
    if IS_MAIN:
        print("statuses=", statuses)
    start = statuses[0].start
    end = statuses[0].end
    type = statuses[0].type
    for s in statuses:
        if s.start > end + PERIOD:
            break
        end = max(end, s.end)
        type = max(type, s.type)
    if start > MAX_START:
        return None
    if end < start + MIN_LENGTH:
        return None
    return Status(int(start), int(end), type)
        

# helper
def colorize(fname):
    im = load_image(fname)
    result = Image.new("RGB", (im[-1].shape[1], im[-1].shape[0]))
    #print(im[0].shape)
    for x in range(im[-1].shape[1]):
        #print(x)
        for y in range(im[-1].shape[0]):
            try:
                sourceColor = im[-1][y][x]
                if is_fixed_point(im, x, y):
                    color = (0, 0, 0)
                elif is_none_color(sourceColor):
                    color = (128, 128, 128)
                elif is_rain_color(sourceColor):
                    color = (0, 0, 256)
                elif is_storm_color(sourceColor):
                    color = (128, 0, 0)
                elif is_hail_color(sourceColor):
                    color = (256, 0, 0)
                else:
                    color = (0, 256, 0)
                result.putpixel((x, y), color)
            except BaseException:
                result.save("test.png")
                return
    result.save("test.png")
    
    
if IS_MAIN:
    #print(analyze(download()[0], NNOV))
    print(analyze(sys.argv[1], NNOV))
    #print(colorize(sys.argv[1]))
    
