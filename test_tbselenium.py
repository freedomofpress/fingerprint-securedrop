#!/usr/bin/env python2.7

import os
import site
import sys
sys.path.append(os.path.join(os.getcwd(), 'tor-browser-selenium'))
# site.addsitedir(path.join(getcwd(), 'tor-browser-selenium'))
from tbselenium.tbdriver import TorBrowserDriver

with TorBrowserDriver('~/.tb-stable/tor-browser_en-US/') as driver:
    driver.get('https://check.torproject.org')
    sleep(1)  # stay one second in the page
