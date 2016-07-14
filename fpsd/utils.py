#!/usr/bin/env python3.5

import os
import logging
from datetime import datetime as dt


def timestamp():
    return dt.now().strftime('%m-%d_%H:%M:%S')

def timestamp_file(filepath, ts, ext="", is_dir=False):
    filepath += "_{}".format(ts)
    if ext:
        filepath += ".{}".format(ext)
    if is_dir:
        os.mkdir(filepath)
    return filepath
    

def setup_logging(dir, filename):
    filepath = os.path.join(dir, filename)
    ts = timestamp()
    ts_filepath = timestamp_file(filepath, ts, ext="log")

    logging.basicConfig(level=logging.INFO,
                        filename=ts_filepath,
                        format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
    logger = logging.getLogger(filename)

    symlink_cur_to_latest(filepath, ts, ext="log")

    return logger


def symlink_cur_to_latest(filepath, ts, ext=""):
    """Makes a symlink(file/folder)name-latest(.ext) point to
    (file/folder)name-timestamp(.ext)"""
    current = timestamp_file(filepath, ts, ext)
    latest = filepath + "-latest"
    if ext:
        latest += ".{}".format(ext)
    try:
        os.remove(latest)
    except OSError:
        pass
    finally:
        os.symlink(current, latest)
