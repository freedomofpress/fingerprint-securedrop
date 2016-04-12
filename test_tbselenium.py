#!/usr/bin/env python

# NOTICE: this is only working right now because I'm working from a dirty
# submodule where I've implemented this
# https://github.com/fowlslegs/tor-browser-selenium/commit/8f7c88871735fc86ee0209595e718ea03841ffee
# commit

import os
import site
site.addsitedir(os.path.join(os.getcwd(), 'tor-browser-selenium'))
from tbselenium.tbdriver import TorBrowserDriver

home_dir = os.path.expanduser('~')
tbb_path = os.path.join(home_dir, 'tbb', 'tor-browser_en-US')
tbb_fx_path = os.path.join(tbb_path, 'Browser', 'firefox')
tbb_profile_path = os.path.join(tbb_path, 'Browser', 'TorBrowser', 'Data',
                                'Browser')
logfile_path = os.path.join(home_dir, 'FingerprintSecureDrop', 'logging',
                            'firefox.log')

with TorBrowserDriver(tbb_path=tbb_path,
                      tbb_logfile_path=logfile_path) as driver:
    driver.get('https://check.torproject.org')
    time.sleep(1)  # stay one second in the page
