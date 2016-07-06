#!/usr/bin/env python3.5

from crawl_onions import *


with Crawler() as crawler:
    crawler.collect_onion_trace("http://http://jlve2diknf45qwjv.onion/")
