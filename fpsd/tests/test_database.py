# Sort the SecureDrop directory and then crawl all sorted SecureDrop instances
# using the database for storage and retrieval.

from collections import OrderedDict
from datetime import datetime
import os
from time import sleep
import unittest

from crawler import Crawler
from database import RawStorage
from sorter import Sorter
from . import common
from utils import coalesce_ordered_dict, get_config, get_lookback


class TestDatabaseMethods(unittest.TestCase):
    """Tests database methods by sorting the SecureDrop directory into
    up-to-date (non-monitored) and out-of-date (monitored) classes, then crawls
    them."""
    # Database
    test_start_time = datetime.now()
    def get_cur_runtime(self):
        """Returns the how long the test case has been running as a
        datetime.timedelta object."""
        return datetime.now() - self.test_start_time

    # Sorter
    sd_directory = [
        "http://secrdrop5wyphb5x.onion/sites/securedrop.org/files/securedrop_list.txt"]
    config = get_config()
    config = config["sorter"]
    class_tests = coalesce_ordered_dict(config['class_tests'])


    def setUp(self):
        class TestRawStorage(RawStorage, common.TestDatabase):
            pass

        self.db_handler = TestRawStorage()


    def tearDown(self):
        # Delete entries while keeping table structure intact
        self.db_handler._wipe_raw_schema()


    def test_sortcrawl_sd_dir(self):
        with Sorter(db_handler=self.db_handler) as sortbot9k:
            sortbot9k.scrape_directories(self.sd_directory)
            sortbot9k.sort_onions(self.class_tests)

        uptodate_class, uptodate_name = \
                self.db_handler.get_onion_class(self.get_cur_runtime(), True)
        self.assertEqual(type(uptodate_class), dict)
        # At least 10 of our instances should be on the latest version
        self.assertGreaterEqual(len(uptodate_class), 10)
        self.assertRegex(list(uptodate_class)[0], "http")
        self.assertRegex(list(uptodate_class)[0], ".onion")

        outofdate_class, outofdate_name = \
                self.db_handler.get_onion_class(self.get_cur_runtime(), False)
        self.assertEqual(type(outofdate_class), dict)
        # At least 1 of our instances will be lagging behind versions :'(
        self.assertGreaterEqual(len(outofdate_class), 1)
        self.assertRegex(list(outofdate_class)[0], "http")
        self.assertRegex(list(outofdate_class)[0], ".onion")

        class_data = self.db_handler.get_onions(self.get_cur_runtime())
        nonmonitored_name, monitored_name = class_data.keys()
        # Test that we get the expected class names, and data types back
        self.assertEqual(nonmonitored_name, 'nonmonitored')
        self.assertRegex(monitored_name, 'sd')
        nonmonitored_class, monitored_class = class_data.values()
        self.assertEqual(type(nonmonitored_class), dict)
        self.assertEqual(type(monitored_class), dict)

        with Crawler(db_handler=self.db_handler) as crawlbot9k:
            crawlbot9k.collect_set_of_traces(nonmonitored_class)

        # There are not yet methods to query crawled data, but in the future,
        # tests will be added here to verify Crawler-related data is being
        # read/written to the database in the expected manner.

if __name__ == "__main__":
    unittest.main()
