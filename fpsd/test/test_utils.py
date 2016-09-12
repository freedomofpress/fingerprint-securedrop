import datetime
import unittest

from utils import get_lookback

class LookbackTimeTest(unittest.TestCase):
    def test_one_week(self):
        self.assertEqual(get_lookback('1w'), datetime.timedelta(7))

    def test_four_weeks(self):
        self.assertEqual(get_lookback('4w'), datetime.timedelta(28))

    def test_one_month(self):
        with self.assertRaises(TypeError):
            lookback_time = get_lookback('1m')

    def test_no_units(self):
        with self.assertRaises(TypeError):
            lookback_time = get_lookback('666')
