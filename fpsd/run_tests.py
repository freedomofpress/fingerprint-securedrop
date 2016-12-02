#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import doctest
import getpass
import subprocess

unit_tests = ['utils', 'database', 'features', 'evaluation']
if getpass.getuser() != 'travis':
    #     # This test can take a long time because I've yet to implement my own
    #     # timeout function for page loads, and the selenium implementation is not
    #     # reliable. Since it often triggers Travis's timeout, we skip it.
    unit_tests.append('sketchy_sites')
    for unit_test in unit_tests:
        subprocess.call('python3 -m pytest tests/test_{}.py'.format(unit_test),
                        shell=True)

doctests = ['utils']
for doctest in doctests:
    subprocess.call('python3 -m doctest {}.py'.format(doctest),
                    shell=True)
