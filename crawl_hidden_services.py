#!/usr/bin/env python

from time import sleep
from os import (path, environ)
import configparser
config = configparser.ConfigParser()
config.read('config.ini')
home_dir = path.expanduser('~')
fpsd_dir = path.join(home_dir, 'FingerprintSecureDrop')
hs_sorter_log = path.join(fpsd_dir, 'logging',
                          config.get('Crawl Hidden Services',
                                     'hs_sorter_log'))
tbb_path = path.join(home_dir, config.get('Crawl Hidden Services', 'tbb_path'))
environ['TBB_PATH'] = tbb_path # Required by tbselenium.test.__init__ checks
tbb_logfile_path = path.join(fpsd_dir, 'logging', 
                             config.get('Crawl Hidden Services',
                                        'tbb_logfile'))

from site import addsitedir
addsitedir(path.join(fpsd_dir, 'tor-browser-selenium'))
from tbselenium.test.conftest import (start_xvfb, stop_xvfb)
from tbselenium.tbdriver import TorBrowserDriver
from tbselenium.common import USE_RUNNING_TOR
tor_cfg = USE_RUNNING_TOR

from ast import literal_eval
import re

class Crawler:
    def __init__(self, hs_sorter_log):
        with open(hs_sorter_log, 'r') as logfile:
            logfile = logfile.readlines()
            self.sds = self.extract_set(logfile, -4, 'Up to date SDs:')
            self.not_sds = self.extract_set(logfile, -1, 'Not SDs:')

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

    def crawl_url_set(self, url_set, **kwargs):
        for url in url_set:
            with VirtTBDriver(**kwargs) as driver:
                driver.get(url)
                driver.get_screenshot_as_file(path.join(fpsd_dir,'logging',
                                                        '{}.png'.format(url)[7:]))
                sleep(1)

from contextlib import contextmanager
@contextmanager
def VirtTBDriver(**kwargs):
    virt_framebuffer = start_xvfb()
    yield TorBrowserDriver(**kwargs)
    stop_xvfb(virt_framebuffer)

if __name__ == '__main__':
    crawler = Crawler(hs_sorter_log=hs_sorter_log,)
    crawler.crawl_url_set(crawler.not_sds,
                          tbb_path=tbb_path,
                          tbb_logfile_path=tbb_logfile_path,
                          tor_cfg=tor_cfg)
