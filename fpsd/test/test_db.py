# Sort the SecureDrop directory and then crawl all sorted SecureDrop instances
# using the database for storage and retrieval.

from collections import OrderedDict
from datetime import datetime, timedelta
from time import sleep
import unittest

from crawler import Crawler
from database import RawStorage
from sorter import Sorter
from utils import get_lookback

class DatabaseTest(unittest.TestCase):

    use_database = True
    sd_directory = [
        "http://secrdrop5wyphb5x.onion/sites/securedrop.org/files/securedrop_list.txt"]
    class_tests = OrderedDict(sd_038="'Powered by SecureDrop 0.3.8' in text")
    class_tests["out_of_date"] = "'Powered by SecureDrop' in text"
    test_start_time = datetime.now()

    def setUp(self):
        self.db_handler = RawStorage()

    def test_sort_securedrop_directory(self):
        # Sort all SDs in the SD directory into sd_038 and out_of_date classes
        with Sorter(db_handler=self.db_handler) as sortbot9k:
            sortbot9k.scrape_directories(self.sd_directory)
            sortbot9k.sort_onions(self.class_tests)

        uptodate_class, uptodate_name = \
                self.db_handler.get_onion_class(datetime.now-self.test_start_time, True)
        # At least 10 of our instances should be on the latest version
        self.assertGreater(len(uptodate_class), 9)
        self.assertRegex(list(uptodate_class)[0], "http")
        self.assertRegex(list(uptodate_class)[0], ".onion")
        self.assertEqual(uptodate_name, "sd_038")

        outofdate_class, outofdate_name = \
                self.db_handler.get_onion_class(datetime.now-self.test_start_time, False)
        # At least 2 of our instances will be lagging behind versions :'(
        self.assertGreater(len(outofdate_class), 1)
        self.assertRegex(list(outofdate_class)[0], "http")
        self.assertRegex(list(outofdate_class)[0], ".onion")
        self.assertEqual(outofdate_name, "out_of_date")


if __name__ == "__main__":
    unittest.main()
