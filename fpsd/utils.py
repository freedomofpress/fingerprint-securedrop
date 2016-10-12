from datetime import datetime, timedelta
import logging
import os
import random
import socket
import sys

def find_free_port(desired_port, *additional_conflicts):
    """Return a port that is unused and conflict-free.
    Args:
        desired_port: int of port to return if unused and conflict-free.
        additional_conflicts: 0+ ints that should not be returned.
    Returns:
        port: int of port determined unused and conflict-free.
    """
    try:
        sock = socket.socket()
        port = desired_port
        while not sock.connect_ex(('127.0.0.1', port)) and \
              port not in additional_conflicts:
            # The range 49152–65535 contains dynamic or private ports that
            # cannot be registered with IANA.
            port = random.randint(49152, 65536)
    finally:
        sock.close()
    return port

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
    if format == "log":
        return datetime.now().strftime('%m-%d_%H:%M:%S')
    elif format == "db":
        return datetime.now().isoformat()


def panic(error_msg):
    """Helper function prints a message to stdout and then exits 1."""
    print(error_msg)
    sys.exit(1)


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


def timestamp_file(filepath, ts, ext="", is_dir=False):
    filepath += "_{}".format(ts)
    if ext:
        filepath += ".{}".format(ext)
    if is_dir:
        os.mkdir(filepath)
    return filepath
