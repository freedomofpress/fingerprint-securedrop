#!/usr/bin/env python

# Automates visiting sites using Tor Browser running in a virtual X
# framebuffer. Does not take an arbitrary list of sites, but rather parses a
# logfile created by running ./sort_hidden_services.py wherein sets of
# up-and-running hidden services sorted by whether they are SecureDrop or not
# can be found. Arguments found in the imports/ globals block starting with
# `import configparse` just below can be set via the ./config.ini file.

from ast import literal_eval
import re
from logging import setup_logging
from time import sleep
from os import (path, environ)

import configparser
config = configparser.ConfigParser()
config.read('config.ini')
home_dir = path.expanduser('~')
fpsd_path = path.join(home_dir,
                      config.get('Crawl Hidden Services', 'fpsd_path'))
hs_sorter_log = path.join(fpsd_path, 'logging',
                          config.get('Crawl Hidden Services', 'hs_sorter_log'))
tbb_path = path.join(home_dir, config.get('Crawl Hidden Services', 'tbb_path'))
environ['TBB_PATH'] = tbb_path # Required by tbselenium.test.__init__ checks
tbb_logfile_path = path.join(fpsd_dir, 'logging', 
                             config.get('Crawl Hidden Services',
                                        'tbb_logfile'))
page_load_timeout = config.get('Crawl Hidden Services', 'page_load_timeout')
from site import addsitedir
addsitedir(path.join(fpsd_dir, 'tor-browser-selenium'))
from tbselenium.test.conftest import (start_xvfb, stop_xvfb)
from tbselenium.tbdriver import TorBrowserDriver
from tbselenium.common import USE_RUNNING_TOR
tor_cfg = USE_RUNNING_TOR


class Crawler:
    def __init__(self, hs_sorter_log, **kwargs):
        with open(hs_sorter_log, 'r') as logfile:
            logfile = logfile.readlines()
            self.sds = self.extract_set(logfile, -4, 'Up to date SDs:')
            self.not_sds = self.extract_set(logfile, -1, 'Not SDs:')
        self.page_load_timeout=page_load_timeout

    def extract_set(self, hs_sets, subscript, expected_set_prefix):
        line = hs_sets[subscript]
        assert expected_set_prefix, 'Line did not begin with \
"{}" as expected. The log file specified is probably not from a complete run \
of the hidden service sorter script.'.format(set_prefix)
        set_str = re.search('{.+', line).group(0)
        # literal_eval does not support type set, so we must strip the
        # brackets, so literal_eval returns a tuple, then convert that tuple
        # into a set
        return set(literal_eval(set_str.strip('{}')))

    def crawl_url_sets(self, url_set_list, **kwargs):
        for url_set in url_set_list:
            for url in url_set:
                with VirtTBDriver(**kwargs) as driver:
                    logger.info("Starting crawl of {}".format(url))
                    driver.get(url)
                    logger.info("Stopping crawl of {}".format(url))
                    sleep(2)

from contextlib import contextmanager
@contextmanager
def VirtTBDriver(**kwargs):
    virt_framebuffer = start_xvfb()
    yield TorBrowserDriver(**kwargs)
    stop_xvfb(virt_framebuffer)

if __name__ == '__main__':
    logger = setup_logging('crawler')
    crawler = Crawler(hs_sorter_log=hs_sorter_log,
                      page_load_timeout=page_load_timeout)
    crawler.crawl_url_sets([crawler.not_sds, crawler.sds],
                            tbb_path=tbb_path,
                            tbb_logfile_path=tbb_logfile_path,
                            tor_cfg=tor_cfg)
