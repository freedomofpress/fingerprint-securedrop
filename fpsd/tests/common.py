from configparser import ConfigParser

from database import Database
from utils import get_config

class TestDatabase(Database):
    """A mixin class that fetches the values for the test database from
    the configuration file."""
    def __init__(self, **kwargs):
        config = get_config()
        test_db_config = dict(config.items("test_database"))
        super().__init__(test_db_config)
