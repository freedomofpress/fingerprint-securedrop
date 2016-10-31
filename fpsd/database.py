#!/usr/bin/python3
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime as dt
import os
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
                                 values will read from the [database]
                                 section of './config.ini'.

    :raises: An :exc:OperationalError, when unable to initialize the
             database engine with the given database configuration.
    """
    def __init__(self, database_config=None):
        if not database_config:
            config = get_config()
            database_config = dict(config.items("test_database"))
        try:
            self.engine = create_engine(
                'postgresql://{pguser}:@{pghost}:{pgport}/{pgdatabase}'.format(
                    **database_config))
        except OperationalError as exc:
            panic("fingerprint-securedrop Postgres support relies on use of a "
                  "PGPASSFILE. Make sure this file and the env var pointing "
                  "to it exist and set 0600 permissions & user ownership."
                  "\n{}.".format(exc))


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
