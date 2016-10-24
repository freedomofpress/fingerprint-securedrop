#!/usr/bin/env python3.5

from subprocess import call
from os.path import dirname, abspath, join
from getpass import getuser

# Run all the tests using py.test
if getuser() == "travis":
    call(["python3.5", "-m", "unittest", "-f", "-v", "test.test_sketchy_sites"])
call(["python3.5", "-m", "unittest", "-f", "-v", "test.test_utils"])
call(["python3.5", "-m", "unittest", "-f", "-v", "test.test_database_methods"])
call(["python3.5", "-m", "unittest", "-f", "-v", "test.test_features"])
