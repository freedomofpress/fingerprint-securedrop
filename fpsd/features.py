#!/usr/bin/env python3.5
import os
import pandas as pd
import pdb
from sqlalchemy import create_engine
import subprocess
from tqdm import tqdm

from utils import panic


def compute_bursts(df):
    """Compute list of burst lengths for a given trace for both incoming
    and outgoing bursts
    """

    bursts = []
    current_incoming_burst_length = 0
    current_outgoing_burst_length = 0

    for row in df.itertuples():
        if row.ingoing == False:
            if current_incoming_burst_length > 0:
                # then an incoming burst just ended!
                bursts.append(current_incoming_burst_length)
                # reset burst lengths
                current_incoming_burst_length = 0
                current_outgoing_burst_length = 0
            current_outgoing_burst_length += 1

        else:  # row.ingoing == True
            if current_outgoing_burst_length > 0:
                # then an outgoing burst just ended!
                bursts.append(current_outgoing_burst_length)
                # reset burst lengths
                current_outgoing_burst_length = 0
                current_incoming_burst_length = 0
            current_incoming_burst_length += 1

    # If we were in a burst at the end of the trace, let's save it
    if current_incoming_burst_length > 0:
        bursts.append(current_incoming_burst_length)
    elif current_outgoing_burst_length > 0:
        bursts.append(current_outgoing_burst_length)

    # For some features we need to know the positions of bursts,
    # so let's save this information as well
    ranks = list(range(1, len(bursts) + 1))
    return bursts, ranks


class FeatureStorage():
    def __init__(self):
        """Set up database engine"""
        try:
            self.engine = create_engine(
                'postgresql://{}:@{}/{}'.format(
                    *[os.environ[i] for i in
                      ["PGUSER", "PGHOST", "PGDATABASE"]]))
        except KeyError as exc:
            panic("The following env vars must be set in order to know which "
                  "database to connect to: PGUSER, PGHOST, & PGDATABASE."
                  "\n{}.".format(exc))
        except OperationalError as exc:
            panic("FingerprintSecureDrop Postgres support relies on use of a "
                  "PGPASSFILE. Make sure this file and the env var pointing "
                  "to it exist and set 0600 permissions & user ownership."
                  "\n{}.".format(exc))

    def drop_table(self, table_name):
        """Try to remove a table even if views depend on it

        Args:
            table_name [string]: Name of table to be dropped
        """

        query = "DROP TABLE IF EXISTS {} CASCADE;".format(table_name)
        self.engine.execute(query)

    def generate_table_undefended_frontpage_links(self):
        """This method creates a table of exampleids that were present 
        at the time of feature generation that the unified view can join
        on. The table contains one integer column, exampleid.
        """

        self.drop_table("features.undefended_frontpage_examples")

        query = ("CREATE TABLE features.undefended_frontpage_examples AS ( "
                 "SELECT foo.exampleid FROM ( SELECT exampleid, "
                 "count(*) FROM raw.frontpage_traces GROUP BY exampleid) foo);")
        self.engine.execute(query)

    def _create_temp_packet_positions(self, outgoing_only=True):
        """This method takes all rows in raw.frontpage_traces and
        creates a temporary table packet_positions with the following
        format:

        exampleid  | position |  ingoing
        (integer)  | (bigint) |  (boolean)
        ------------------------------------
        9          | 4        | f
        9          | 5        | f
        9          | 15       | f

        where position describes where the cell is in the trace. For
        example, for the first outgoing cell in the trace with
        exampleid=9 was the 4th packet in the trace. This table is used
        by the position-based feature generation functions.

        Args:
            outgoing_only [boolean]: describes whether or not we should
                only use outgoing cells to create this table
        """

        self.drop_table("packet_positions")

        if outgoing_only:
            where_only_outgoing = "WHERE ingoing <= false"
        else:
            where_only_outgoing = ""

        query = ("CREATE TEMP TABLE packet_positions AS             "
                 "(SELECT exampleid, position, ingoing              "
                 "  FROM (                                          "
                 "    SELECT                                        "
                 "      ROW_NUMBER() OVER                           "
                 "      (PARTITION BY exampleid ORDER BY t_trace)   "
                 "      AS position,                                "
                 "      t.*                                         "
                 "    FROM raw.frontpage_traces t)                  "
                 "x {} );").format(where_only_outgoing)

        self.engine.execute(query)

    def _create_table_outgoing_cell_positions(self, num_cells=500):
        """This method takes the first num_cells rows for each exampleid
        in packet_positions and creates a temporary table
        first_(num_cells)_outgoing_packet_positions with the following
        format:

        exampleid  | position |  outgoing_cell_order
        (integer)  | (bigint) |  (bigint)
        -----------------------------------------------
        9          | 4        | 1
        9          | 5        | 2
        9          | 15       | 3

        For example, the third outgoing cell was at position 15 in the
        trace. This table is used by the position-based feature
        generation functions.
        """
        table_name = "first_{}_outgoing_packet_positions".format(num_cells)
        self.drop_table(table_name)

        query = ("CREATE TEMP TABLE first_{n}_outgoing_packet_positions AS "
                 "(SELECT exampleid, outgoing_cell_order, position      "
                 "  FROM (                                                 "
                 "    SELECT                                               "
                 "      ROW_NUMBER() OVER                                  "
                 "      (PARTITION BY exampleid ORDER BY position)         "
                 "      AS outgoing_cell_order,                         "
                 "      t.*                                                "
                 "    FROM packet_positions t) x                           "
                 "  WHERE x.outgoing_cell_order <= {n}                  "
                 ");").format(n=num_cells)

        self.engine.execute(query)

    def get_exampleids(self):
        """Get list of exampleids"""
        query = "SELECT DISTINCT exampleid FROM raw.frontpage_traces"
        df = pd.read_sql(query, self.engine)
        return df.exampleid.values

    def get_trace_cells(self, exampleid):
        """Get trace for a given exampleid"""
        df = pd.read_sql(("SELECT ingoing, t_trace FROM raw.frontpage_traces "
                          "WHERE exampleid={} "
                          "ORDER BY t_trace").format(exampleid),
                         self.engine)
        return df

    def generate_table_cell_numbers(self):
        """This method takes all examples and produces a table
        features.cell_numbers with the following format:

        exampleid  | a        | b        | c
        (integer)  | (bigint) | (bigint) | (bigint)
        -----------------------------------------------
        9          | 326      | 37       | 363
        10         | 493      | 47       | 540
        11         | 652      | 77       | 729

        where a, b, c are the feature columns:

        total_number_of_incoming_cells,
        total_number_of_outgoing_cells,
        and total_number_of_cells.

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.cell_numbers")

        query = ("CREATE TABLE features.cell_numbers AS                 "
                 "(SELECT t1.exampleid, CASE WHEN                       "
                 " t1.total_number_cells IS NULL THEN 0 ELSE            "
                 " t1.total_number_cells END,                           "
                 " CASE WHEN t2.total_number_incoming_cells IS          "
                 " NULL THEN 0 ELSE t2.total_number_incoming_cells END, "
                 " CASE WHEN t3.total_number_outgoing_cells IS          "
                 " NULL THEN 0 ELSE t3.total_number_outgoing_cells END  "
                 "  FROM                                                "
                 "   (SELECT exampleid, count(*)                        "
                 "    AS total_number_cells                             "
                 "    FROM raw.frontpage_traces                         "
                 "    GROUP BY exampleid) t1                            "
                 " LEFT OUTER JOIN                                      "
                 "   (SELECT exampleid, count(*)                        "
                 "    AS total_number_incoming_cells                    "
                 "    FROM raw.frontpage_traces                         "
                 "    WHERE raw.frontpage_traces.ingoing = 't'          "
                 "    GROUP BY exampleid) t2                            "
                 " ON t1.exampleid = t2.exampleid                       "
                 " LEFT OUTER JOIN                                      "
                 "   (SELECT exampleid, count(*)                        "
                 "    AS total_number_outgoing_cells                    "
                 "    FROM raw.frontpage_traces                         "
                 "    WHERE raw.frontpage_traces.ingoing = 'f'          "
                 "    GROUP BY exampleid) t3                            "
                 " ON t1.exampleid = t3.exampleid);                     ")
        self.engine.execute(query)

        return "features.cell_numbers"

    def generate_table_cell_timings(self):
        """This method takes all examples and produces a table
        features.cell_timings with the following format:

        exampleid  | total_elapsed_time
        (integer)  | (numeric)
        -----------------------------------------------
        9          | 19.738556
        10         | 16.512998
        11         | 22.946719

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.cell_timings")

        query = ("CREATE TABLE features.cell_timings AS           "
                 "  (SELECT exampleid, MAX(t_trace) -             "
                 "  MIN(t_trace) as total_elapsed_time            "
                 "  FROM raw.frontpage_traces GROUP BY exampleid);")
        self.engine.execute(query)

        return "features.cell_timings"

    def generate_table_interpacket_timings(self):
        """This method takes all examples and produces a table
        features.interpacket_timings with the following format:

        exampleid  | a         | b
        (integer)  | (numeric) | (numeric)
        -----------------------------------------------
        9          | 0.0545    | 0.2424
        10         | 0.0306    | 0.1690
        11         | 0.0315    | 0.1135

        where a and b are the feature columns:
        mean_intercell_time and standard_deviation_intercell_time.

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.interpacket_timings")

        query = ("CREATE TABLE features.interpacket_timings AS ( "
                 "WITH interpacket_times as (                       "
                 "  SELECT                                          "
                 "    exampleid,                                    "
                 "    t_trace - lag(t_trace) over                   "
                 "    (partition BY exampleid ORDER BY t_trace)     "
                 "    as difference                                 "
                 "  FROM raw.frontpage_traces )                     "
                 "SELECT exampleid,                                 "
                 "  avg( difference ) as mean_intercell_time,       "
                 "  stddev( difference )                            "
                 "  as standard_deviation_intercell_time            "
                 "FROM interpacket_times GROUP BY exampleid);       ")
        self.engine.execute(query)

        return "features.interpacket_timings"

    def generate_table_initial_cell_directions(self, num_cells=10):
        """This method takes all examples and produces a table
        features.initial_cell_directions with the following format:

        exampleid  | a         | b         ...    | num_cells
        (integer)  | (integer) | (integer) ...    | (integer)
        ------------------------------------------------------
        9          | 0         | 1         ...
        10         | 1         | 1         ...
        11         | 1         | 0         ...

        where there are a variable number (num_cells) of feature
        columns, each named direction_cell_x where x is the position in
        the trace, beginning at 1. This feature represents the direction
        (where outgoing is positive) of the cell.

        Args:
            num_cells [int]: number of initial cells to use as features

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.initial_cell_directions")

        crosstab_columns = ['direction_cell_{} integer'.format(x+1)
                            for x in range(num_cells)]
        query = ("CREATE TABLE features.initial_cell_directions AS  "
                 "  (SELECT *                                       "
                 "  FROM crosstab(                                  "
                 "    'SELECT                                       "
                 "    exampleid, position,                          "
                 "     case when ingoing = true then 0 else 1 end   "
                 "  FROM (                                          "
                 "    SELECT                                        "
                 "      ROW_NUMBER() OVER                           "
                 "      (PARTITION BY exampleid ORDER BY t_trace)   "
                 "      AS position,                                "
                 "      t.*                                         "
                 "    FROM raw.frontpage_traces t) x                "
                 "  WHERE x.position <= 10')                        "
                 "  AS  ct(exampleid integer, {})                   "
                 ");").format(', '.join(crosstab_columns))

        self.engine.execute(query)
        return "features.initial_cell_directions"

    def generate_table_outgoing_cell_positions(self, num_cells=500):
        """This method takes all examples and produces a table with the
        following format:

        exampleid  | a         | b         ...    | num_cells
        (integer)  | (bigint)  | (bigint)  ...    | (bigint)
        ---------------------------------------------------------
        9          | 2         | 4         ...
        10         | 1         | 2         ...
        11         | 1         | 3         ...

        where there are a variable number (num_cells) of feature
        columns, each named outgoing_cell_position_x where x is the
        position in the trace, beginning at 1.

        Args:
            num_cells [int]: number of cells to use as features

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.cell_positions")

        self._create_temp_packet_positions(outgoing_only=True)
        self._create_table_outgoing_cell_positions(num_cells=num_cells)

        crosstab_columns = ['outgoing_cell_position_{} bigint'.format(x+1)
                            for x in range(num_cells)]

        query = ("CREATE TABLE features.cell_positions AS             "
                 "(SELECT * FROM crosstab(                            "
                 "'SELECT exampleid, outgoing_cell_order, position "
                 "FROM first_{}_outgoing_packet_positions')           "
                 "AS ct(exampleid integer,                            "
                 "{}));").format(num_cells,
                                 ', '.join(crosstab_columns))

        self.engine.execute(query)
        return "features.cell_positions"

    def generate_table_outgoing_cell_positions_differences(self,
                                                           num_cells=500):
        """This method takes all examples and produces a table with the
        following format:

        exampleid  | a         | b         ...    | num_cells
        (integer)  | (bigint)  | (bigint)  ...    | (bigint)
        --------------------------------------------------------
        9          | 2         | 1         ...
        10         | 1         | 2         ...
        11         | 2         | 1         ...

        where there are a variable number (num_cells) of feature
        columns, each named outgoing_cell_position_difference_x where x
        is the position in the trace + 1, beginning at 1. For example,
        outgoing_cell_position_difference_1 is the difference in
        position between the 2nd and 1st outgoing cells.

        Args:
            num_cells [int]: number of features to create

        Returns:
            [string] name of newly created table
        """

        num_ranks = num_cells + 1

        self.drop_table("features.cell_positions_differences")

        self._create_temp_packet_positions(outgoing_only=True)
        self._create_table_outgoing_cell_positions(num_cells=num_ranks)

        self.drop_table("first_{}_cell_positions".format(num_ranks))

        crosstab_columns = ['outgoing_cell_position_{} bigint'.format(x)
                            for x in range(1, num_ranks + 1)]

        query = ("CREATE TEMP TABLE first_{n}_cell_positions AS         "
                 "(SELECT * FROM crosstab(                           "
                 "'SELECT * FROM first_{n}_outgoing_packet_positions') "
                 "AS ct(exampleid integer,                           "
                 "{cols})); ").format(n=num_ranks,
                                      cols=', '.join(crosstab_columns))
        self.engine.execute(query)

        diff_columns = [("({prefix}_{n2} - {prefix}_{n1}) "
                         "AS {prefix}_difference_{n1}").format(
                            prefix='outgoing_cell_position', n2=x+1, n1=x)
                        for x in range(1, num_ranks)]

        feat_columns = ', '.join(diff_columns)
        query = ("CREATE TABLE features.cell_positions_differences   "
                 "AS (SELECT exampleid, {cols}                      "
                 "FROM first_{n}_cell_positions); ".format(cols=feat_columns,
                                                        n=num_ranks))

        self.engine.execute(query)
        return "features.cell_positions_differences"

    def generate_table_binned_counts(self, num_features=100, size_window=30):
        """This method takes all examples and produces a table with the
        following format:

        exampleid  | a         | b         ...    | num_features
        (integer)  | (bigint)  | (bigint)  ...    | (bigint)
        --------------------------------------------------------
        9          | 11        | 11        ...
        10         | 12        | 14        ...
        11         | 13        | 16        ...

        where there are a variable number (num_features) of feature
        columns, each named num_outgoing_packets_in_window_x_of_size_y.
        num_outgoing_packets_in_window_x_of_size_y is the number of
        cells in the xth bin or "window" of size y

        Args:
            num_features [int]: number of features to create
            size_window [int]: size of each bin

        Returns:
            [string] name of newly created table
        """

        self._create_temp_packet_positions(outgoing_only=False)
        feature_table_name = "features.size_{}_windows".format(size_window)

        self.drop_table(feature_table_name)

        if num_features > 1:
            feature_columns = ["num_outgoing_packets_in_window_{}_of_size_{}".format(x,
                                                                                     size_window)
                               for x in range(1, num_features + 1)]

            # Use LEFT OUTER JOIN because many of the later windows
            # will be Null.
            # Note: count(*) will return Null if count(*) = 0
            arr_subqueries = [("LEFT OUTER JOIN (SELECT exampleid,             "
                               "COALESCE(count(*), 0)                          "
                               "AS {colname} FROM packet_positions WHERE       "
                               "ingoing = false AND position > {pos_start} AND "
                               "position <= {pos_stop} GROUP BY exampleid)     "
                               "t{feat_ind} ON foo.exampleid =                 "
                               "t{feat_ind}.exampleid").format(colname=feature_columns[x-1],
                                                               pos_start=(x-1)*size_window,
                                                               pos_stop=x*size_window,
                                                               feat_ind=x)
                              for x in range(1, num_features + 1)]

            subqueries = " ".join(arr_subqueries)
        else:
            subqueries = ""

        query = ("CREATE TABLE features.size_{}_windows AS ( "
                 "SELECT foo.exampleid, {} FROM ( "
                 "(SELECT exampleid, count(*) FROM " 
                 "raw.frontpage_traces GROUP BY exampleid) foo"
                 " {} ));").format(size_window,
                               ', '.join(feature_columns),
                               subqueries)

        self.engine.execute(query)
        return feature_table_name

    def create_bursts(self):
        """This method takes all examples and produces a table
        public.current_bursts with all bursts in the following format:

        burstid   | burst     | exampleid   | rank
        (integer) | (bigint)  | (bigint)    | (bigint)
        --------------------------------------------------
        1         | 1         | 251         | 1
        2         | 2         | 251         | 2
        3         | 4         | 251         | 3

        This table is then used by the burst table creation methods
        called by generate_burst_tables().

        Returns:
            [string] name of newly created table
        """

        # Preprocessing that would ideally be done in SQL (for speed)
        final_df = pd.DataFrame()
        for example in tqdm(self.get_exampleids()):
            trace_df = self.get_trace_cells(example)
            bursts, ranks = compute_bursts(trace_df)
            final_df = final_df.append(pd.DataFrame({'exampleid': example,
                                                     'burst': bursts,
                                                     'rank': ranks}))
        final_df = final_df.reset_index().drop('index', axis=1)
        self.drop_table("public.current_bursts")

        table_creation = ("CREATE TABLE public.current_bursts             "
                          "(burstid SERIAL PRIMARY KEY, exampleid BIGINT, "
                          "burst BIGINT, rank BIGINT)                     ")
        self.engine.execute(table_creation)

        burst_rows = ['({}, {}, {})'.format(row[0], row[1], row[2])
                      for row in final_df.values]

        cols = final_df.columns
        insert_query = ("INSERT INTO public.current_bursts "
                        "({}, {}, {}) VALUES {};".format(cols[0],
                                                         cols[1],
                                                         cols[2],
                                                         ', '.join(burst_rows)))
        self.engine.execute(insert_query)
        return "public.current_bursts"

    def generate_table_burst_length_aggregates(self):
        """This method takes all bursts and produces a table with the
        following format:

        exampleid  | a         | b          | c
        (integer)  | (numeric) | (bigint)   | (bigint)
        -----------------------------------------------------
        9          | 1.27      | 37         | 4
        10         | 1.51      | 59         | 12
        11         | 1.69      | 49         | 12

        where a and b are the feature columns mean_burst_length,
        num_bursts, and max_burst_length.

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.burst_length_aggregates")

        query = ("CREATE TABLE features.burst_length_aggregates AS    "
                 "(SELECT exampleid, avg(burst) AS mean_burst_length, "
                 "count(burst) AS num_bursts,                         "
                 "max(burst) AS max_burst_length                      "
                 "FROM public.current_bursts                          "
                 "GROUP BY exampleid);                                ")

        self.engine.execute(query)
        return "features.burst_length_aggregates"

    def generate_table_binned_bursts(self, lengths=[2, 5, 10, 15, 20, 50]):
        """This method takes all bursts and produces a table with the
        following format:

        exampleid  | a         | b         ...    | n
        (integer)  | (bigint)  | (bigint)  ...    | (bigint)
        --------------------------------------------------------
        9          | 3         | 0         ...
        10         | 2         | 0         ...
        11         | 6         | 1         ...

        where there are a variable number (n=len(lengths)) of feature
        columns, each named num_bursts_with_length_gt_x.
        num_bursts_with_length_gt_x is the number of bursts with length
        greater than x

        Args:
            lengths [list of int]: number of lengths to create bins.
            Bin limits are from the given length to the end of the trace

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.burst_binned_lengths")

        feature_columns = ["num_bursts_with_length_gt_{}".format(length)
                           for length in lengths]

        # Use LEFT OUTER JOIN because many of the later windows will be Null
        # Note: count(*) will return Null if count(*) = 0 hence coalesce is
        # used to set those cells to 0
        subqueries = [("LEFT OUTER JOIN (SELECT exampleid,        "
                       "COALESCE(count(burst), 0) AS {colname}    "
                       "FROM public.current_bursts WHERE          "
                       "burst > {length} GROUP BY exampleid)      "
                       "t{table_ref} ON foo.exampleid =           "
                       "t{table_ref}.exampleid").format(colname=feature_columns[feat_ind],
                                                        length=length,
                                                        table_ref=feat_ind)
                      for feat_ind, length in enumerate(lengths)]

        query = ("CREATE TABLE features.burst_binned_lengths AS ( "
                 "SELECT foo.exampleid, {} FROM ( "
                 "(SELECT exampleid, count(*) FROM " 
                 "raw.frontpage_traces GROUP BY exampleid) foo "
                 "{} ));").format(", ".join(feature_columns),
                                  " ".join(subqueries))

        self.engine.execute(query)
        return "features.burst_binned_lengths"

    def generate_table_burst_lengths(self, num_bursts=100):
        """This method takes all bursts and produces a table with the
        following format:

        exampleid  | a         | b         ...    | num_bursts
        (integer)  | (bigint)  | (bigint)  ...    | (bigint)
        --------------------------------------------------------
        9          | 1         | 2         ...
        10         | 2         | 2         ...
        11         | 1         | 3         ...

        where there are a variable number (num_bursts) of feature
        columns, each named length_burst_x. For example, length_burst_1
        is the length of the first burst.

        Args:
            num_bursts [int]: number of bursts to make features for

        Returns:
            [string] name of newly created table
        """

        self.drop_table("features.burst_lengths")

        column_names = ['length_burst_{} bigint'.format(x)
                        for x in range(1, num_bursts + 1)]

        query = ("CREATE TABLE features.burst_lengths AS         "
                 "(SELECT * FROM crosstab(                       "
                 "'SELECT exampleid, rank, burst                 "
                 "FROM public.current_bursts')                   "
                 "AS ct(exampleid bigint,                        "
                 "{}));").format(', '.join(column_names))

        self.engine.execute(query)
        return "features.burst_lengths"

    def generate_burst_tables(self):
        self.create_bursts()
        self.generate_table_burst_length_aggregates()
        self.generate_table_binned_bursts()
        self.generate_table_burst_lengths()

        return ["features.burst_length_aggregates",
                "features.burst_binned_lengths",
                "features.burst_lengths"]

    def _get_column_tables_of_table(self, schema_name, table_name):
        query = ("SELECT column_name FROM information_schema.columns "
                 "WHERE table_schema='{}' "
                 "AND table_name='{}'").format(schema_name,
                                               table_name)
        result = self.engine.execute(query)
        colnames = []
        for row in result:
            colnames.append(row[0])
        return colnames

    def create_master_feature_view(self, feature_table_names):
        """This generates a view of all the feature tables at
        features.frontpage_features in the following form:

        exampleid  | feature_1 | feature_2 ...    | feature_n
        (integer)  | (bigint)  | (bigint)  ...    | (bigint)
        --------------------------------------------------------
        9          | 1         | 2         ...    | 34
        10         | 2         | 2         ...    | 21
        11         | 1         | 3         ...    | 36

        A single row represents a single example along with the features
        for that example. The purpose of the view is to provide a simple
        way to select train and test sets.

        Args:
            feature_table_names [list of strings]: list of tables that
            contain features that we would like to put into the view
        """

        master_features = {}

        for schema_and_table in feature_table_names:
            schema_name = schema_and_table.split('.')[0]
            table_name = schema_and_table.split('.')[1]
            table_columns = self._get_column_tables_of_table(schema_name,
                                                             table_name)
            table_columns.remove("exampleid")
            master_features.update({schema_and_table: table_columns})

        columns_to_select = "foo.exampleid"
        full_join_query = ("FROM ( (SELECT exampleid FROM      " 
                           "features.undefended_frontpage_examples) foo ")

        for table_num, table_name in enumerate(list(master_features.keys())):
            prefix = 't{}.'.format(table_num)
            prefixed_columns = [prefix + s for s in master_features[table_name]]
            columns_to_select = columns_to_select + ', ' + ', '.join(prefixed_columns)
            join_query = ("LEFT OUTER JOIN {name} t{num} "
                          "ON foo.exampleid = t{num}.exampleid ").format(name=table_name,
                                                                         num=table_num)
            full_join_query = full_join_query + join_query

        drop_view = "DROP VIEW IF EXISTS features.frontpage_features; "
        self.engine.execute(drop_view)

        create_new_view = ("CREATE VIEW features.frontpage_features "
                           "AS ( SELECT {} {} ));").format(columns_to_select,
                                                          full_join_query)
        self.engine.execute(create_new_view)


def main():
    db = FeatureStorage()

    # Create master table to store list of examples that we have generated features for
    db.generate_table_undefended_frontpage_links()

    # Create individual feature tables and save the names of the tables
    feature_tables = []
    feature_tables.append(db.generate_table_cell_numbers())
    feature_tables.append(db.generate_table_cell_timings())
    feature_tables.append(db.generate_table_interpacket_timings())
    feature_tables.append(db.generate_table_initial_cell_directions())
    feature_tables.append(db.generate_table_outgoing_cell_positions())
    feature_tables.append(db.generate_table_outgoing_cell_positions_differences())
    feature_tables.append(db.generate_table_binned_counts())
    feature_tables += db.generate_burst_tables()

    # Create master feature view from the created tables
    db.create_master_feature_view(feature_tables)


if __name__ == '__main__':
    main()
