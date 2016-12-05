#!/usr/bin/python3
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime as dt
import json
import os
import pandas as pd
from psycopg2 import OperationalError
import re
from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine.url import URL as SQL_connect_URL
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session

from utils import get_config, get_lookback, get_timestamp, panic


class Database:
    """A base class for database objects providing an engine and context
    management for safe transactions.

    :param dict database_config: An optional parameter supplying a
                                 database engine configuration. Contains
                                 the following keys: 'pguser', 'pghost',
                                 'pgport', & 'pgdatabase'. If not passed
                                 values then it will read from the
                                 PGPASSFILE that stores the password.

    :raises: An :exc:OperationalError, when unable to initialize the
             database engine with the given database configuration.
    """
    def __init__(self, database_config=None):
        if not database_config:
            database_config = get_config()['database']

        try:
            self.engine = create_engine(
                'postgresql://{pguser}:@{pghost}:{pgport}/{pgdatabase}'.format(
                    **database_config))
        except OperationalError as exc:
            panic("fingerprint-securedrop Postgres support relies on use of a "
                  "PGPASSFILE. Make sure this file exists in your homedir with "
                  "0600 permissions:\n{}.".format(exc))


    @contextmanager
    def safe_session(self):
        """Context manager for database session."""
        session = Session(bind=self.engine)
        try:
            yield session
            session.commit()
        except:
            # if something goes wrong, do not commit
            session.rollback()
            raise
        finally:
            session.close()


class RawStorage(Database):
    """Store raw crawled data in the database"""
    def __init__(self, **kwargs):
        """Read current structure from database"""
        super().__init__(**kwargs)

        # Generate mappings from existing tables
        metadata = MetaData(schema='raw')
        metadata.reflect(self.engine)
        Base = automap_base(metadata=metadata)
        Base.prepare()

        # Our fundamental objects are:
        self.Onion = Base.classes.hs_history
        self.Example = Base.classes.frontpage_examples
        self.Cell = Base.classes.frontpage_traces
        self.Crawl = Base.classes.crawls

    def _wipe_raw_schema(self):
        """Like with a cloth. Delete entries while keeping table structure
        intact."""
        with self.safe_session() as session:
            for table in self.Cell, self.Example, self.Onion, self.Crawl:
                session.query(table).delete()

    def add_onions(self, class_data):
        """Add sorted onions into the HS history table"""
        onions = []
        ts = get_timestamp("db")
        for class_name, class_urls in class_data.items():
            onions += [self.Onion(
                hs_url='{}{}'.format(hs_url.split('onion')[0], 'onion'),
                is_sd=True if 'sd' in class_name else False,
                sd_version=class_name.split('_')[1] if 'sd' in class_name else 'N/A',
                is_current=True,
                sorted_class=class_name,
                t_sort=ts)
                for hs_url in class_urls]

        with self.safe_session() as session:
            session.bulk_save_objects(onions)

    def get_onion_class(self, timespan, is_monitored):
        """Get a class of onions from the database.
        Args:
            timespan: determines from which point forward to fetch sorted onion
            entries from a particular class. Either (i) a str of the form
            "<integer>{w,m,h}", or (ii) a datetime.timedelta when more
            precision is needed.
            is_monitored: boolean determining whether to get monitored HSes or
            non-monitored HSes.
        Returns:
            onion_class: a dict mapping individual HS URLs to their ID in the
            database.
            class_name: a string describing the selected class.
        """
        if isinstance(timespan, str):
            start_sort_time = dt.now() - get_lookback(timespan)
        else:
            start_sort_time = dt.now() - timespan

        onion_class = {}
        class_name = ""
        with self.safe_session() as session:
            for row in session.query(self.Onion).\
                       filter(self.Onion.t_sort >= start_sort_time).\
                       filter(self.Onion.is_sd == is_monitored):
                onion_class.update({row.hs_url: row.hsid})
                class_name = row.sorted_class
        return onion_class, class_name

    def get_onions(self, timespan):
        """Get sorted HSes from the database."""
        monitored_class, monitored_name = self.get_onion_class(timespan, is_monitored=True)
        nonmonitored_class, _ = self.get_onion_class(timespan, is_monitored=False)
        class_data = OrderedDict()
        class_data['nonmonitored'] = nonmonitored_class
        class_data[monitored_name] = monitored_class
        return class_data

    def add_crawl(self, control_data):
        """Insert row for new crawl into the crawls table."""
        new_crawl = self.Crawl(**control_data)

        with self.safe_session() as session:
            session.add(new_crawl)
            session.flush()
            inserted_primary_key = new_crawl.crawlid
        return inserted_primary_key

    def add_example(self, example):
        """Insert row for new example into the frontpage_examples table"""
        new_example = self.Example(**example)

        with self.safe_session() as session:
            session.add(new_example)
            session.flush()
            inserted_primary_key = new_example.exampleid
        return inserted_primary_key

    def add_trace(self, trace, exampleid):
        """Insert rows for trace into frontpage_traces table"""
        words_to_remove = ['CIRC', 'STREAM', 'COMMAND', 'length']
        for word in words_to_remove:
            trace = re.sub(word, '', trace)

        trace = re.sub(',', ' ', trace)
        trace = trace.lstrip("b'").split('\\n\\n')

        cells = []
        for cell_entry in trace:
            row = [x for x in cell_entry.split(' ') if x != '']
            if len(row) == 6:
                cells.append(self.Cell(exampleid=exampleid,
                    ingoing=True if row[1] == 'INCOMING' else False,
                    circuit=int(row[2]), stream=int(row[3]),
                    command=row[4], length=int(row[5]), t_trace=float(row[0])))

        with self.safe_session() as session:
            session.bulk_save_objects(cells)
        return None


class DatasetLoader(Database):
    """Load train/test sets"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def load_world(self, world_type):
        """For open world validation, we must keep track of which onion service
        a trace came from. However for closed world validation, we can select
        traces without consideration of which site they belong to.

        :returns: a pandas DataFrame df containing the dataset
        """

        select_hs_urls = ', t3.hs_url' if world_type is 'open' else ''

        labeled_query = ('select t1.*, t3.is_sd {} '
                           'from features.frontpage_features t1 '
                           'inner join raw.frontpage_examples t2 '
                           'on t1.exampleid = t2.exampleid '
                           'inner join raw.hs_history t3 '
                           'on t3.hsid = t2.hsid').format(select_hs_urls)

        df = pd.read_sql(labeled_query, self.engine)
        return df


class ModelStorage(Database):
    """Store trained models in the database"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.COMMON_METRICS = ("auc, tpr, fpr,                   "
             "precision_at_0_point_01_percent,                   "
             "precision_at_0_point_05_percent,                   "
             "precision_at_0_point_1_percent,                    "
             "precision_at_0_point_5_percent,                    "
             "precision_at_1_percent, precision_at_5_percent,    "
             "precision_at_10_percent,                           "
             "recall_at_0_point_01_percent,                      "
             "recall_at_0_point_05_percent,                      "
             "recall_at_0_point_1_percent,                       "
             "recall_at_0_point_5_percent,                       "
             "recall_at_1_percent, recall_at_5_percent,          "
             "recall_at_10_percent, f1_at_0_point_01_percent,    "
             "f1_at_0_point_05_percent, f1_at_0_point_1_percent, "
             "f1_at_0_point_5_percent, f1_at_1_percent,          "
             "f1_at_5_percent, f1_at_10_percent")

    def metric_formatter(self, metrics):
        """Format the metrics query"""
        for metric in ("tpr", "fpr"):
            metrics[metric] = [str(x) for x in metrics[metric]]
            #metrics[metric] = ["'{}'".format(x) for x in metrics[metric]]
            metrics[metric] = "'{{ {} }}'".format(", ".join(metrics[metric]))
        metrics_list = [metrics["auc"],
                        metrics["tpr"], metrics["fpr"],
                        metrics[0.01]["precision"], 
                        metrics[0.05]["precision"], metrics[0.1]["precision"],
                        metrics[0.5]["precision"], metrics[1]["precision"],
                        metrics[5]["precision"], metrics[10]["precision"],
                        metrics[0.01]["recall"], 
                        metrics[0.05]["recall"], metrics[0.1]["recall"],
                        metrics[0.5]["recall"], metrics[1]["recall"],
                        metrics[5]["recall"], metrics[10]["recall"],
                        metrics[0.01]["f1"],
                        metrics[0.05]["f1"], metrics[0.1]["f1"],
                        metrics[0.5]["f1"], metrics[1]["f1"],
                        metrics[5]["f1"], metrics[10]["f1"]]
        metrics_list = [str(x) for x in metrics_list]

        return ', '.join(metrics_list)

    def save_full_model(self, eval_metrics, model_timestamp, options):
        query = ("INSERT INTO models.undefended_frontpage_attacks  "
                 "(model_timestamp, numfolds,                      "
                 "train_class_balance, world_type, model_type,     "
                 "base_rate, hyperparameters, {})                  "
                 "VALUES ('{}', {}, {}, '{}', '{}', {}, '{}', {}     "
                 ") ".format(self.COMMON_METRICS, model_timestamp,
                    options["numfolds"], options["train_class_balance"],
                    options["world_type"], options["model_type"],
                    options["base_rate"], json.dumps(options["hyperparameters"]),
                    self.metric_formatter(eval_metrics)))
        with self.safe_session() as session:
            session.execute(query)

    def save_fold_of_model(self, eval_metrics, model_timestamp, fold_timestamp):
        query = ("INSERT INTO models.undefended_frontpage_folds    "
                 "(model_timestamp, fold_timestamp, {}) VALUES     "
                 "('{}', '{}', {}) ".format(self.COMMON_METRICS, 
                    model_timestamp, fold_timestamp,
                    self.metric_formatter(eval_metrics)))
        with self.safe_session() as session:
            session.execute(query)
