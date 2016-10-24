#!/usr/bin/env python3.5
from collections import OrderedDict
from decimal import Decimal
import os
import pandas as pd
import pdb
import sqlalchemy
import unittest

from features import compute_bursts, FeatureStorage


def db_helper(db, table_name, feature_names):
    """Helper function for testing a table in the database. Takes some
    column(s) in a table and generates a dict.

    Args:
        db [FeatureStorage object]: database object
        table_name [string]: name of the table to test
        feature_names [list of strings]: names of the columns to test

    Returns:
        actual_output [dict]: Contains the actual output in a dict that 
            can be easily compared with the expected output dict defined
            in the test
    """

    select_query = "SELECT * FROM {} ORDER BY exampleid; ".format(table_name)
    result = db.engine.execute(select_query)

    # Ensure we preserve the order of the columns with an OrderedDict
    actual_output = OrderedDict({'exampleid': []})
    for feature_name in feature_names:
        actual_output.update({feature_name: []})

    column_names = ['exampleid'] + feature_names

    for row in result:
        for column_index, column_name in enumerate(column_names):
            # SQLAlchemy will by default return decimal.Decimal objects
            # which we want to convert to floats
            if isinstance(row[1], Decimal):
                actual_output[column_name].append(float(row[column_index]))
            else:
                actual_output[column_name].append(row[column_index])
    return dict(actual_output)


def populate_hs_crawls(engine):
    insert_test_hs = ("INSERT INTO raw.hs_history "
    "(hs_url, is_sd, sd_version, is_current, sorted_class, t_sort) VALUES "
    "('notarealonion.onion', 't', '038', 't', 'sd_038', '2016-07-30 16:42:02.298115');")
    engine.execute(insert_test_hs)

    insert_test_crawl = ("INSERT INTO raw.crawls "
    "(page_load_timeout, wait_on_page, wait_after_closing_circuits, "
    "entry_node, os, kernel, kernel_version, python_version, "
    "tor_version, tb_version, crawler_version, ip) VALUES "
    "(20, 5, 5, '1B60184DB9B96EA500A19C52D88F145BA5EC93CD', "
    "'Ubuntu', 'Linux', "
    "'1.1.1-generic', '3.5.2', '0.2.8.6', '6.0.3', '1.3', "
    "'1.1.1.1');")
    engine.execute(insert_test_crawl)


def cleanup(engine):
    clean_up_features_schema = ("DROP SCHEMA IF EXISTS features CASCADE; ")
    engine.execute(clean_up_features_schema)
    conn = engine.connect()
    conn.execute("TRUNCATE TABLE raw.frontpage_traces RESTART IDENTITY CASCADE;")
    conn.execute("TRUNCATE TABLE raw.frontpage_examples RESTART IDENTITY CASCADE;")
    conn.execute("TRUNCATE TABLE raw.hs_history RESTART IDENTITY CASCADE;")
    conn.execute("TRUNCATE TABLE raw.crawls RESTART IDENTITY CASCADE;")
    conn.execute("COMMIT;")


class BurstGenerationTest(unittest.TestCase):
    def test_incoming_burst(self):
        df = pd.DataFrame({'ingoing': [True, True, True]})
        bursts = compute_bursts(df)
        self.assertEqual(bursts, [3])

    def test_outgoing_burst(self):
        df = pd.DataFrame({'ingoing': [False, False, False]})
        bursts = compute_bursts(df)
        self.assertEqual(bursts, [3])

    def test_multiple_bursts(self):
        df = pd.DataFrame({'ingoing': [True, True, False, False, True,
                                       True, False, False, False]})
        bursts = compute_bursts(df)
        self.assertEqual(bursts, [2, 2, 2, 3])


class RawFeatureGenerationTest(unittest.TestCase):
    """Tests for all the feature generation methods that start
    with the raw.frontpage_traces table"""
    def setUp(self):
        pgdatabase = os.getenv("PGDATABASE")
        if pgdatabase and not pgdatabase.startswith("test"):
            pgdatabase = "test" + pgdatabase
        os.environ["PGDATABASE"] = pgdatabase
        self.db = FeatureStorage()

        clean_up_features_schema = ("DROP SCHEMA IF EXISTS features CASCADE; ")
        self.db.engine.execute(clean_up_features_schema)

        instantiate_features_schema = ("CREATE SCHEMA features; ")
        self.db.engine.execute(instantiate_features_schema)

        populate_hs_crawls(self.db.engine)

        insert_test_data_examples = ("INSERT INTO raw.frontpage_examples "
        "(exampleid, hsid, crawlid, t_scrape) VALUES "
        "(9, 1, 1, '2016-08-30 19:11:38.869066'), "
        "(10, 1, 1, '2016-08-30 19:11:39.879066');")
        self.db.engine.execute(insert_test_data_examples)

        insert_test_data_traces = ("INSERT INTO raw.frontpage_traces "
        "(cellid, exampleid, ingoing, circuit, stream, command, "
        "length, t_trace) VALUES "
        "(508, 9, 't', 3725647749, 0, 'EXTENDED2(15)', 66, 1472598678.735375),"
        "(509, 9, 'f', 3725647749, 0, 'EXTEND2(14)', 119, 1472598678.909463),"
        "(510, 9, 't', 3725647749, 0, 'EXTENDED2(15)', 66, 1472598679.262226),"
        "(922, 10, 'f', 3418218064, 59159, 'DATA(2)', 498, 1472598739.562103),"
        "(923, 10, 'f', 3418218064, 59159, 'DATA(2)', 424, 1472598739.562176),"
        "(924, 10, 'f', 3418218064, 59159, 'DATA(2)', 289, 1472598739.571273);")
        self.db.engine.execute(insert_test_data_traces)

        return None

    def test_aggregate_cell_numbers(self):
        table_name = self.db.create_table_cell_numbers()
        expected_output = {'exampleid': [9, 10],
                           'total_number_of_cells': [3, 3],
                           'total_number_of_incoming_cells': [2, 0],
                           'total_number_of_outgoing_cells': [1, 3]}

        actual_output = db_helper(self.db, table_name,
            ['total_number_of_cells',
             'total_number_of_incoming_cells',
             'total_number_of_outgoing_cells'])

        self.assertEqual(expected_output, actual_output)

    def test_aggregate_cell_timings(self):
        table_name = self.db.create_table_cell_timings()
        expected_output = {'exampleid': [9, 10],
                           'total_elapsed_time': [0.526851, 0.00917]}

        actual_output = db_helper(self.db, table_name, ['total_elapsed_time'])

        self.assertEqual(expected_output, actual_output)

    def test_intercell_timings(self):
        table_name = self.db.create_table_intercell_timings()
        expected_output = {'exampleid': [9, 10],
                           'mean_intercell_time': [0.2634255, 0.004585],
                           'standard_deviation_intercell_time': [0.1263423041285064,
                           0.006380931593427405]}

        actual_output = db_helper(self.db, table_name,
            ['mean_intercell_time', 'standard_deviation_intercell_time'])

        self.assertEqual(expected_output, actual_output)

    def test_initial_cell_directions(self):
        table = self.db.create_table_initial_cell_directions(num_cells=2)
        expected_output = {'exampleid': [9, 10],
                           'direction_cell_1': [0, 1],
                           'direction_cell_2': [1, 1]}

        actual_output = db_helper(self.db, table,
                                  ['direction_cell_1',
                                   'direction_cell_2'])

        self.assertEqual(expected_output, actual_output)

    def test_outgoing_cell_positions(self):
        table_name = self.db.create_table_outgoing_cell_positions(num_cells=2)
        expected_output = {'exampleid': [9, 10],
                           'outgoing_cell_position_1': [2, 1],
                           'outgoing_cell_position_2': [None, 2]}

        actual_output = db_helper(self.db, table_name,
                                  ['outgoing_cell_position_1',
                                   'outgoing_cell_position_2'])

        self.assertEqual(expected_output, actual_output)

    def test_outgoing_cell_positions_differences(self):
        table_name = self.db.create_table_outgoing_cell_positions_differences(num_cells=2)
        expected_output = {'exampleid': [9, 10],
                           'outgoing_cell_position_difference_1': [None, 1],
                           'outgoing_cell_position_difference_2': [None, 1]}

        actual_output = db_helper(self.db, table_name,
                                  ['outgoing_cell_position_difference_1',
                                   'outgoing_cell_position_difference_2'])

        self.assertEqual(expected_output, actual_output)

    def test_windowed_counts(self):
        table_name = self.db.create_table_windowed_counts(num_features=2,
                                                          size_window=2)
        expected_output = {'exampleid': [9, 10],
                           'num_outgoing_cell_in_window_1_of_size_2': [1, 2],
                           'num_outgoing_cell_in_window_2_of_size_2': [None, 1]}

        actual_output = db_helper(self.db, table_name,
                                  ['num_outgoing_cell_in_window_1_of_size_2',
                                   'num_outgoing_cell_in_window_2_of_size_2'])

        self.assertEqual(expected_output, actual_output)

    def test_burst_table_creation(self):
        self.db._create_temp_current_bursts()
        query = "SELECT * FROM public.current_bursts ORDER BY exampleid; "
        result = self.db.engine.execute(query)
        expected_output = {'exampleid': [9, 9, 9, 10],
                           'burst_length': [1, 1, 1, 3],
                           'burst_rank': [1, 2, 3, 1]}
        actual_output = {'exampleid': [],
                         'burst_length': [],
                         'burst_rank': []}
        for row in result:
            actual_output['exampleid'].append(row[1])
            actual_output['burst_length'].append(row[2])
            actual_output['burst_rank'].append(row[3])

        self.assertEqual(expected_output, actual_output)

    def tearDown(self):
        cleanup(self.db.engine)
        self.db.drop_table("public.current_bursts")


class BurstFeatureGeneration(unittest.TestCase):
    """Tests for the feature generation methods
    that begin with the bursts table"""
    def setUp(self):
        pgdatabase = os.getenv("PGDATABASE")
        if pgdatabase and not pgdatabase.startswith("test"):
            pgdatabase = "test" + pgdatabase
        os.environ["PGDATABASE"] = pgdatabase
        self.db = FeatureStorage()

        clean_up_features_schema = ("DROP SCHEMA IF EXISTS features CASCADE; ")
        self.db.engine.execute(clean_up_features_schema)

        instantiate_features_schema = ("CREATE SCHEMA features; ")
        self.db.engine.execute(instantiate_features_schema)

        populate_hs_crawls(self.db.engine)

        insert_test_data_examples = ("INSERT INTO raw.frontpage_examples "
        "(exampleid, hsid, crawlid, t_scrape) VALUES "
        "(9, 1, 1, '2016-08-30 19:11:38.869066'), "
        "(10, 1, 1, '2016-08-30 19:11:39.879066');")
        self.db.engine.execute(insert_test_data_examples)

        insert_test_data_traces = ("INSERT INTO raw.frontpage_traces "
        "(cellid, exampleid, ingoing, circuit, stream, command, "
        "length, t_trace) VALUES "
        "(508, 9, 't', 3725647749, 0, 'EXTENDED2(15)', 66, 1472598678.735375),"
        "(922, 10, 'f', 3418218064, 59159, 'DATA(2)', 498, 1472598739.562103)")
        self.db.engine.execute(insert_test_data_traces)

        create_bursts_table = ("CREATE TABLE public.current_bursts ("
                               "burstid SERIAL PRIMARY KEY, "
                               "burst BIGINT, "
                               "exampleid BIGINT, "
                               "rank BIGINT);")
        self.db.engine.execute(create_bursts_table)

        insert_test_bursts = ("INSERT INTO public.current_bursts "
                              "(burstid, burst, exampleid, rank) VALUES "
                              "(33653, 1, 9, 22), "
                              "(33643, 9, 9, 12), "
                              "(33649, 1, 9, 18), "
                              "(33650, 3, 9, 19), "
                              "(2961, 2, 10, 11), "
                              "(2954, 8, 10, 4), "
                              "(2953, 1, 10, 3);")
        self.db.engine.execute(insert_test_bursts)

    def test_burst_length_aggregates(self):
        table_name = self.db.create_table_burst_length_aggregates()
        expected_output = {'exampleid': [9.0, 10.0],
                           'mean_burst_length': [3.5, 3.6666666666666665],
                           'num_bursts': [4.0, 3.0],
                           'max_burst_length': [9.0, 8.0]}

        actual_output = db_helper(self.db, table_name,
                                  ['mean_burst_length', 'num_bursts',
                                   'max_burst_length'])
        self.assertEqual(expected_output, actual_output)

    def test_burst_length_windowed_bursts(self):
        table_name = self.db.create_table_windowed_bursts(lengths=[2, 5])
        expected_output = {'exampleid': [9, 10],
                           'num_bursts_with_length_gt_2': [2, 1],
                           'num_bursts_with_length_gt_5': [1, 1]}

        actual_output = db_helper(self.db, table_name,
                                  ['num_bursts_with_length_gt_2',
                                   'num_bursts_with_length_gt_5'])
        self.assertEqual(expected_output, actual_output)

    def test_burst_lengths(self):
        table_name = self.db.create_table_burst_lengths(num_bursts=2)
        expected_output = {'exampleid': [9, 10],
                           'length_burst_1': [9, 1],
                           'length_burst_2': [1, 8]}

        actual_output = db_helper(self.db, table_name,
                                  ['length_burst_1', 'length_burst_2'])
        self.assertEqual(expected_output, actual_output)

    def tearDown(self):
        cleanup(self.db.engine)
        self.db.drop_table("public.current_bursts")

if __name__ == '__main__':
    unittest.main()
