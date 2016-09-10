#!/usr/bin/env python3.5

import os
from datetime import datetime, timedelta
import logging
from sys import exit

def panic(error_msg):
    """Helper function prints a message to stdout and then exits 1."""
    print(error_msg)
    exit(1)

def get_lookback(lookback_length):
    """Take a string from the user and return a datetime.timedelta object."""
    time_units = {'weeks': 0, 'days': 0, 'hours': 0} 
    time_shortunits = [x[0] for x in time_units.keys()]
    lookback_unit = lookback_length[-1]
    lookback_value = lookback_length[:-1]

    try:
        lookback_unit = next(i for i in list(time_units) if
                             i.startswith(lookback_unit))
    except StopIteration:
        panic("hs_history_lookback time unit {lookback_unit} is not "
            "suppported. Please choose one of: "
            "{time_shortunits}.".format(**locals()))
    try:
        time_units[lookback_unit] = int(lookback_value)
    except ValueError as exc:
        panic("hs_history_lookback should be an integer value followed by a "
              "single time unit element from {time_shortunits}.\n"
              "ValueError: {exc}".format(**locals()))

    lookback_timedelta = timedelta(weeks=time_units['weeks'],
                                   days=time_units['days'],
                                   hours=time_units['hours'])

    return lookback_timedelta


def get_timestamp(format):
    if type == "log":
        return datetime.now().strftime('%m-%d_%H:%M:%S')
    elif type == "db":
        return datetime.now().isoformat()

def timestamp_file(filepath, ts, ext="", is_dir=False):
    filepath += "_{}".format(ts)
    if ext:
        filepath += ".{}".format(ext)
    if is_dir:
        os.mkdir(filepath)
    return filepath
    

def setup_logging(dir, filename):
    filepath = os.path.join(dir, filename)
    ts = get_timestamp("log")
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
