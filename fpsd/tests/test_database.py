# Sort the SecureDrop directory and then crawl all sorted SecureDrop instances
# using the database for storage and retrieval.

from collections import OrderedDict
from datetime import datetime
import os
from time import sleep
import unittest

from crawler import Crawler
from database import RawStorage, safe_session
from sorter import Sorter
from utils import get_lookback

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
    class_tests = OrderedDict(sd_039="'Powered by SecureDrop 0.3.9' in text")
    class_tests["out_of_date"] = "'Powered by SecureDrop' in text"


    def setUp(self):
        # Ensure we're using a test database
        pgdatabase = os.getenv("PGDATABASE")
        if pgdatabase and not pgdatabase.startswith("test"):
            pgdatabase = "test" + pgdatabase
        os.environ["PGDATABASE"] = pgdatabase
        self.db_handler = RawStorage()


    def tearDown(self):
        # Delete entries while keeping table structure intact
        self.db_handler.wipe_database()
        with safe_session(self.db_handler.engine) as sessionbot9k:
            for table in [self.db_handler.Cell, self.db_handler.Example,
                          self.db_handler.Onion, self.db_handler.Crawl]:
                self.assertEqual(sessionbot9k.query(table).count(), 0)


    def test_sortcrawl_sd_dir(self):
        # Sort all SDs in the SD directory into sd_039 and out_of_date classes
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
        self.assertEqual(uptodate_name, "sd_039")

        outofdate_class, outofdate_name = \
                self.db_handler.get_onion_class(self.get_cur_runtime(), False)
        self.assertEqual(type(outofdate_class), dict)
        # At least 2 of our instances will be lagging behind versions :'(
        self.assertGreaterEqual(len(outofdate_class), 2)
        self.assertRegex(list(outofdate_class)[0], "http")
        self.assertRegex(list(outofdate_class)[0], ".onion")
        self.assertEqual(outofdate_name, "out_of_date")

        class_data = self.db_handler.get_onions(self.get_cur_runtime())
        nonmonitored_name, monitored_name = class_data.keys()
        self.assertEqual(nonmonitored_name, "nonmonitored")
        self.assertEqual(monitored_name, list(self.class_tests)[0])
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
