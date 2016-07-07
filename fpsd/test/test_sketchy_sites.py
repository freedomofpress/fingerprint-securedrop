#!/usr/bin/env python3.5

# This test crawls some sets that have triggered http.client.RemoteDisconnected
# exceptions

import unittest
from crawler import Crawler

class CrawlBadSitesTest(unittest.TestCase):

    bad_sites = ["http://jlve2diknf45qwjv.onion/",
                 "http://money2mxtcfcauot.onion", 
                 "http://22222222aziwzse2.onion"]

    def test_crawl_of_bad_sites(self):
        with Crawler() as crawler:
            crawler.collect_set_of_traces(self.bad_sites, shuffle=False)

if __name__ == "__main__":
    unittest.main()
