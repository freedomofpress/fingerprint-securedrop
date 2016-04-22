#!/usr/bin/env python

import os
import logging
from datetime import datetime as dt


def timestamp():
    return dt.now().strftime('%m-%d_%H:%M:%S')


def setup_logging(name):

    try:
        os.stat('logging')
    except FileNotFoundError:
        os.mkdir('logging')

    ts = timestamp()
    logfile = '{}-log_{}.txt'.format(name, ts)
    logging.basicConfig(level=logging.INFO,
                        filename='logging/{}'.format(logfile),
                        format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
    logger = logging.getLogger(name)
    symlink_cur_to_latest('{}-log'.format(name), ts, 'txt')
    return logger


def symlink_cur_to_latest(file_prefix, ts, file_ext):
    latest = '{}-latest.{}'.format(file_prefix, file_ext)
    llatest = os.path.join('logging', latest)
    try:
        if os.stat(llatest):
            os.unlink(llatest)
    except FileNotFoundError:
        pass
    finally:
        os.symlink('{}_{}.{}'.format(file_prefix, ts, file_ext), llatest)
