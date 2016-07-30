#!/usr/bin/env python3.5

from contextlib import contextmanager
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, MetaData
import datetime


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
    def __init__(self, dbconfig):
        """Read current structure from database"""

        dbcreds = {}
        with open(dbconfig) as f:
            for line in f.readlines():
                row = line.split(" ")[1].split("=")
                dbcreds[row[0]] = row[1].strip()

        self.engine = create_engine('postgresql://{}:{}@{}/{}'.format(
            dbcreds['PGUSER'], dbcreds['PGPASSWORD'],
            dbcreds['PGHOST'], dbcreds['PGDATABASE']))

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
