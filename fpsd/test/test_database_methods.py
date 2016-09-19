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
from utils import get_lookback

class TestDatabaseMethods(unittest.TestCase):

    # General
    test_start_time = datetime.now()

    def get_cur_runtime(self):
        """Returns the how long the test case has been running as a
        datetime.timedelta object."""
        return datetime.now() - self.test_start_time

    # Sorter specific
    sd_directory = [
        "http://secrdrop5wyphb5x.onion/sites/securedrop.org/files/securedrop_list.txt"]
    class_tests = OrderedDict(sd_038="'Powered by SecureDrop 0.3.8' in text")
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


    def test_sort_securedrop_directory(self):
        # Sort all SDs in the SD directory into sd_038 and out_of_date classes
        with Sorter(db_handler=self.db_handler,
                    take_ownership=False) as sortbot9k:
            sortbot9k.scrape_directories(self.sd_directory)
            sortbot9k.sort_onions(self.class_tests)

        uptodate_class, uptodate_name = \
                self.db_handler.get_onion_class(self.get_cur_runtime(), True)
        # At least 10 of our instances should be on the latest version
        self.assertGreater(len(uptodate_class), 9)
        self.assertRegex(list(uptodate_class)[0], "http")
        self.assertRegex(list(uptodate_class)[0], ".onion")
        self.assertEqual(uptodate_name, "sd_038")

        outofdate_class, outofdate_name = \
                self.db_handler.get_onion_class(self.get_cur_runtime(), False)
        # At least 2 of our instances will be lagging behind versions :'(
        self.assertGreater(len(outofdate_class), 1)
        self.assertRegex(list(outofdate_class)[0], "http")
        self.assertRegex(list(outofdate_class)[0], ".onion")
        self.assertEqual(outofdate_name, "out_of_date")

    def test_crawl_securedrops(self):
        class_data = self.db_handler.get_onions(self.get_cur_runtime())
        nonmonitored_name, monitored_name = class_data.keys()
        nonmonitored_class, monitored_class = class_data.values()

        with Crawler(db_handler=self.db_handler,
                     take_ownership=False) as crawlbot9k:
            crawlbot9k.collect_set_of_traces(nonmonitored_class)


if __name__ == "__main__":
    unittest.main()
