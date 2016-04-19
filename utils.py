#!/usr/bin/env python

from os import *

def setup_logging(name):
    import logging
    from datetime import datetime

    try:
        stat('logging')
    except FileNotFoundError:
        mkdir('logging')

    timestamp = datetime.now().strftime("%m-%d_%H:%M:%S")
    log_file = '{}-log_{}.txt'.format(name, timestamp)
    logging.basicConfig(level=logging.INFO,
                        filename='logging/{}'.format(log_file),
                        format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
    logger = logging.getLogger('{}'.format(name))

    try:
        stat('logging/{}-log-latest.txt'.format(name))
        unlink('logging/{}-log-latest.txt'.format(name))
    except FileNotFoundError:
        pass
    finally:
        symlink(log_file, 'logging/{}-log-latest.txt'.format(name))

    return logger
