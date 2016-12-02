from configparser import ConfigParser

from database import Database
from utils import get_db_creds

class TestDatabase(Database):
    """A mixin class that fetches the values for the test database from
    the configuration file."""
    def __init__(self, **kwargs):
        test_db_config = get_db_creds()
        test_db_config["pghost"] = "localhost"
        test_db_config["pgdatabase"] = "testfpsd"
        super().__init__(test_db_config)
