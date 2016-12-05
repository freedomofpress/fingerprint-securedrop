from configparser import ConfigParser

from database import Database

class TestDatabase(Database):
    """A mixin class that fetches the values for the test database from
    the configuration file."""
    def __init__(self, **kwargs):
        test_db_config = dict()
        test_db_config["pghost"] = "localhost"
        test_db_config["pgdatabase"] = "testfpsd"
        test_db_config["pguser"] = "fp_user"
        test_db_config["pgport"] = 5432
        super().__init__(test_db_config)
