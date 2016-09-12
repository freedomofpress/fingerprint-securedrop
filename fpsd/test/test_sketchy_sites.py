# This test crawls some sets that have triggered http.client.RemoteDisconnected
# exceptions

import unittest
from crawler import Crawler

class CrawlBadSitesTest(unittest.TestCase):

    self.bad_sites = ["http://jlve2diknf45qwjv.onion/",
                      "http://money2mxtcfcauot.onion",
                      "http://22222222aziwzse2.onion",
                      "http://xnsoeplvch4fhk3s.onion",
                      "http://uptgsidhuvcsquoi.onion",
                      "http://cubie3atuvex2gdw.onion"]

    def test_crawl_of_bad_sites(self):
        with Crawler(restart_on_sketchy_exception=True) as crawler:
            crawler.collect_set_of_traces(self.bad_sites)

if __name__ == "__main__":
    unittest.main()
