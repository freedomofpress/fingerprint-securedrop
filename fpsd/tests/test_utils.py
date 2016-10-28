from collections import OrderedDict
import datetime
import unittest

from utils import coalesce_ordered_dict, get_config, get_lookback

class ConfigParsingTest(unittest.TestCase):
    def test_read_config(self):
        config = get_config()
        self.assertTrue(config.has_section('sorter'))
        self.assertTrue(config.has_section('crawler'))
        self.assertTrue(config.has_section('database'))
        self.assertTrue(config.has_section('test_database'))
        self.assertIsInstance(config.getint('sorter', 'page_load_timeout'),
                              int)
        entry_nodes = config['crawler']['entry_nodes'].split(',')
        self.assertRegex(entry_nodes[0], "[0-9A-F]{40}")

    def test_coalesce_ordered_dict(self):
        config = get_config()
        class_tests = coalesce_ordered_dict(config['sorter']['class_tests'])
        self.assertIsInstance(class_tests, OrderedDict)



class LookbackTimeTest(unittest.TestCase):
    def test_one_week(self):
        self.assertEqual(get_lookback('1w'), datetime.timedelta(7))

    def test_four_weeks(self):
        self.assertEqual(get_lookback('4w'), datetime.timedelta(28))

    def test_one_month(self):
        with self.assertRaises(SystemExit):
            lookback_time = get_lookback('1m')

    def test_no_units(self):
        with self.assertRaises(SystemExit):
            lookback_time = get_lookback('666')
