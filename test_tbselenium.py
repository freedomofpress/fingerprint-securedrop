#!/usr/bin/env python

from time import sleep
from os import (path, getcwd, environ)
import configparser
config = configparser.ConfigParser()
config.read('config.ini')
home_dir = path.expanduser('~')
fpsd_path = path.join(home_dir, config.get('Crawl Hidden Services', 'fpsd_path'))
tbb_path = path.join(home_dir, config.get('Crawl Hidden Services', 'tbb_path'))
environ['TBB_PATH'] = tbb_path # Required by tbselenium.test.__init__ checks
tbb_logfile_path = path.join(fpsd_path, 'logging',
                             config.get('Crawl Hidden Services', 'tbb_logfile_path'))

from site import addsitedir
addsitedir(path.join(fpsd_path, 'tor-browser-selenium'))
from tbselenium.test.conftest import (start_xvfb, stop_xvfb)
from tbselenium.tbdriver import TorBrowserDriver
from tbselenium.common import USE_RUNNING_TOR

def main():
    with VirtTBDriver(tbb_path=tbb_path,
                      tbb_logfile_path=tbb_logfile_path,
                      tor_cfg=USE_RUNNING_TOR) as driver:
        driver.get('https://check.torproject.org')
        sleep(1)  # stay one second in the page
        assert (not driver.is_connection_error_page), "Failed to load \
https://check.torproject.org :-("
        print("Successfully loaded https://check.torproject.org!")

from contextlib import contextmanager
@contextmanager
def VirtTBDriver(**kwargs):
    virt_framebuffer = start_xvfb()
    yield TorBrowserDriver(**kwargs)
    stop_xvfb(virt_framebuffer)

if __name__ == '__main__':
    main()
