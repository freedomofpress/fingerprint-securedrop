#!/usr/bin/env python3.5

from subprocess import call
from os.path import dirname, abspath, join

# Run all the tests using py.test
call(["python3.5", "-m", "unittest", "-f", "-v", "test.test_sketchy_sites"])
