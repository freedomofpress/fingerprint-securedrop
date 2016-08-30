#!/usr/bin/env python3.5

from contextlib import contextmanager
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, MetaData
from collections import OrderedDict
import datetime
import re
import os

from utils import get_lookback


@contextmanager
def safe_session(engine):
    """Context manager for database session"""
    session = Session(bind=engine)
    try:
        yield session
        session.commit()
    except:
        # if something goes wrong, do not commit
        session.rollback()
        raise
    finally:
        session.close()


class RawStorage(object):
    """Store raw crawled data in the database"""
    def __init__(self):
        """Read current structure from database"""

        self.engine = create_engine('postgresql://{}:{}@{}/{}'.format(
            os.environ['PGUSER'], os.environ['PGPASSWORD'],
            os.environ['PGHOST'], os.environ['PGDATABASE']))

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

    def add_onions(self, class_data):
        """Add sorted onions into the HS history table"""
        onions = []
        ts = datetime.datetime.now().isoformat()
        for class_type in class_data:
            for hs_entry in class_data[class_type]:
                onions.append(self.Onion(
                hs_url='{}{}'.format(hs_entry.split('onion')[0], 'onion'),
                is_sd=True if 'sd' in class_type else False,
                sd_version=class_type.split('_')[1] if 'sd' in class_type else 'N/A',
                is_current=True,
                sorted_class=class_type,
                t_sort=ts))

        with safe_session(self.engine) as session:
            session.bulk_save_objects(onions)

    def _get_single_onion_class(self, is_monitored):
        """Get a class of onions from the database

        Args:
            is_monitored: boolean determining whether to get
            monitored HSes or non-monitored HSes

        Returns:
            onion_class: a dict mapping individual HS URLs to
            their ID in the database
            class_name: a string describing the selected class
        """

        onion_class = {}
        with safe_session(self.engine) as session:
            for row in session.query(self.Onion).\
                       filter(self.Onion.t_sort >= self.start_sort_time).\
                       filter(self.Onion.is_sd == is_monitored):
                onion_class.update({row.hs_url: row.hsid})
            class_name = row.sorted_class
        return onion_class, class_name

    def get_onions(self, timespan):
        """Get sorted HSes from the database"""
        # Define what time we should pull traces from
        self.start_sort_time = datetime.datetime.now() - get_lookback(timespan)

        hs_mon, hs_mon_name = self._get_single_onion_class(is_monitored=True)
        hs_nonmon, _ = self._get_single_onion_class(is_monitored=False)
        
        class_data = OrderedDict()
        class_data['non-monitored'] = hs_nonmon
        class_data[hs_mon_name] = hs_mon
        return class_data

    def add_crawl(self, control_data):
        """Insert row for new crawl into the crawls table"""
        new_crawl = self.Crawl(
            page_load_timeout=control_data["page_load_timeout"],
            wait_on_page=control_data["wait_on_page"],
            wait_after_closing_circuits=control_data["wait_after_closing_circuits"],
            entry_node=control_data["entry_node"],
            os=control_data["os_distribution"],
            kernel=control_data["kernel"],
            kernel_version=control_data["kernel_version"],
            python_version=control_data["python_version"],
            tor_version=control_data["tor_version"],
            tb_version=control_data["tb_version"],
            crawler_version=control_data["crawler_version"],
            city=control_data["city"],
            country=control_data["country"],
            asn=control_data["asn"],
            ip=control_data["ip"])

        with safe_session(self.engine) as session:
            session.add(new_crawl)
            session.flush()
            inserted_primary_key = new_crawl.crawlid
        return inserted_primary_key

    def add_example(self, example):
        """Insert row for new example into the frontpage_examples table"""
        new_example = self.Example(
            hsid=example["hsid"], crawlid=example["crawlid"],
            t_scrape=example["t_scrape"])

        with safe_session(self.engine) as session:
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

        with safe_session(self.engine) as session:
            session.bulk_save_objects(cells)
        return None
