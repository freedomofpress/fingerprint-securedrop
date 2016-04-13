#!/usr/bin/env python

from os import (path, getcwd, environ)
from site import addsitedir
addsitedir(path.join(getcwd(), 'tor-browser-selenium'))
from tbselenium.tbdriver import TorBrowserDriver
from time import sleep

home_dir = path.expanduser('~')
tbb_path = path.join(home_dir, 'tbb', 'tor-browser_en-US')
environ['TBB_PATH'] = tbb_path
tbb_logfile_path = path.join(home_dir, 'FingerprintSecureDrop', 'logging',
                            'firefox.log')

from tbselenium.test.conftest import (start_xvfb, stop_xvfb)

virt_framebuffer = start_xvfb()

with TorBrowserDriver(tbb_path=tbb_path,
                      tbb_logfile_path=tbb_logfile_path) as driver:
    driver.get('https://check.torproject.org')
    sleep(1)  # stay one second in the page
    print("Successfully loaded https://check.torproject.org!")

stop_xvfb(virt_framebuffer)
