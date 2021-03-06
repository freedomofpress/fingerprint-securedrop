#!/usr/bin/env python3.5
#
# Call scrape_directories() on any number of hidden service directories and
# then call sort_onions() on a dict, the keys of which are class names and the
# values boolean lambda expressions that operate on the object reference "text"
# (the HTML text of a web page), returning True when the page belongs to the
# class named by the corresponding key.
#
# Data may either be written to a PostgreSQL database or to a pickle file,
# `fpsd/logging/class-data_<timestamp>.pickle`. Either way, `fpsd/crawler.py`
# has the utilities to fetch and operate on the data.

import asyncio
from ast import literal_eval
PYTHONASYNCIODEBUG = 1 # Enable asyncio debug mode
import aiohttp
import aiosocks
from aiosocks.connector import SocksConnector
from collections import OrderedDict
from os.path import abspath, dirname, join
import pickle
import random
import re
from stem.process import launch_tor_with_config
import socket
import ssl

from database import RawStorage
from utils import (coalesce_ordered_dict, find_free_port, get_config,
                   get_timestamp, setup_logging, symlink_cur_to_latest)

_repo_root = dirname(abspath(__file__))
_log_dir = join(_repo_root, "logging")

# The Sorter handles most errors internally so the user does not have to worry
# about exception handling
class SorterException(Exception):
    """Base class for Sorter exceptions."""

class SorterLoggedError(SorterException):
    """Raised when a Sorter encounters and logs a boring exception."""

class SorterResponseCodeError(SorterLoggedError):
    """Raised when the Sorter gets a non 200/"OK" response code from a page."""

class SorterTimeoutError(SorterLoggedError):
    """Raised when a page load times out."""

class SorterConnectionError(SorterLoggedError):
    """Raised when an error occurs in the connection to the server."""

class SorterCertError(SorterLoggedError):
    """Raised when a SSL certificate fails to be validated. This is common in
    onionspace due to limited availability of CA certs."""

class SorterEmptyDirectoryError(SorterException):
    """Raised when a directory URL seems to load correctly, but contains no
    .onion links."""


class Sorter:
    def __init__(self,
                 take_ownership=True, # Tor dies when the Sorter does
                 torrc_config={"ControlPort": "9051",
                               "CookieAuth": "1"},
                 socks_port=9050,
                 page_load_timeout=20,
                 max_tasks=10,
                 db_handler=None):

        self.logger = setup_logging(_log_dir, "sorter")
        self.db_handler = db_handler

        self.logger.info("Opening event loop for Sorter...")
        self.loop = asyncio.get_event_loop()
        self.max_tasks = max_tasks
        self.logger.info("Creating Sorter queue...")
        self.q = asyncio.Queue()

        # Start tor and create an aiohttp tor connector
        self.torrc_config = torrc_config
        self.socks_port = str(find_free_port(socks_port))
        self.torrc_config.update({"SocksPort": self.socks_port})
        self.logger.info("Starting tor process with config "
                         "{self.torrc_config}.".format(**locals()))
        self.tor_process = launch_tor_with_config(config=self.torrc_config,
                                                  take_ownership=take_ownership)
        onion_proxy = aiosocks.Socks5Addr('127.0.0.1', socks_port)
        conn = SocksConnector(proxy=onion_proxy, remote_resolve=True)

        # aiohttp's ClientSession does connection pooling and HTTP keep-alives
        # for us
        self.logger.info("Creating aiohttp ClientSession with our event loop "
                         "and tor proxy connector...")
        self.session = aiohttp.ClientSession(loop=self.loop, connector=conn)

        # Pretend we're Tor Browser in order to get rejected by less sites/WAFs
        u = "Mozilla/5.0 (Windows NT 6.1; rv:45.0) Gecko/20100101 Firefox/45.0"
        self.headers = {'user-agent': u}

        self.page_load_timeout = page_load_timeout


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def __del__(self):
        self.close()


    def close(self):
        self.logger.info("Beginning the Sorter exit process...")
        if "session" in dir(self):
            self.logger.info("Closing out any lingering HTTP connections...")
            self.session.close()
        if "loop" in dir(self):
            self.logger.info("Closing the event loop...")
            self.loop.close()
        if "tor_process" in dir(self):
            self.logger.info("Killing the Tor process...")
            self.tor_process.kill()
        self.logger.info("Sorter exit complete.")


    def scrape_directories(self, onion_dirs):
        """Creates the self.onions set attribute of the Sorter from all the
        .onion URLs found by scraping the directory URLs."""
        self.loop.run_until_complete(self._scrape_directories(onion_dirs))


    async def _scrape_directories(self, onion_dirs):
        self.onions = set()
        self.failed_onion_dirs = set()

        self.logger.info("Putting directory URLs {onion_dirs} in the "
                         "queue...".format(**locals()))
        for onion_dir in onion_dirs:
            self.q.put_nowait(onion_dir)

        self.logger.info("Starting {self.max_tasks} workers scraping .onion "
                         "URLs from the directory URLs...".format(**locals()))
        workers = [asyncio.Task(self.scrape_directory()) for _ in range(self.max_tasks)]

        await self.q.join()

        if self.failed_onion_dirs:
            self.logger.info("Retrying directory URLs "
                             "{self.failed_onion_dirs} unable to be "
                             "processed on first "
                             "attempt.".format(**locals()))
            for failed_dir in self.failed_onion_dirs:
                self.q.put_nowait(failed_dir)

        await self.q.join()
        self.logger.info("All directory URLs have been scraped. "
                         "{} unique .onion URLs have been "
                         "stored.".format(len(self.onions), **locals()))
        self.logger.info("Stopping all workers...")
        for w in workers:
            w.cancel()


    async def scrape_directory(self):
        while True:
            onion_dir = await self.q.get()
            self.onions.add(onion_dir)
            try:
                response = await self.fetch(onion_dir)
                self.logger.info("{onion_dir}: parsing hidden service links "
                                 "on page...".format(**locals()))
                onions = await self.parse_onion_links(response)
                self.logger.info("{onion_dir}: found {} links on "
                                 "page...".format(len(onions), **locals()))
                self.onions.update(onions)
            except SorterLoggedError:
                self.failed_onion_dirs.add(onion_dir)
            except SorterEmptyDirectoryError:
                msg = ("{onion_dir}: seems to be an empty "
                       "directory".format(**locals()))
                self.logger.warning(msg)
                print(msg)
                # Could be user error, but we'll retry it in case the page just
                # didn't load properly
                self.failed_onion_dirs.add(onion_dir)
            except:
                self.logger.exception("{onion_dir}: unusual exception "
                                      "encountered:".format(**locals()))
                self.failed_onion_dirs.add(onion_dir)
            finally:
                self.q.task_done()


    async def fetch(self, url):
        """Load a webpage and read return the body as plaintext."""
        self.logger.info("{url}: loading...".format(**locals()))
        try:
            with aiohttp.Timeout(self.page_load_timeout, loop=self.loop):
                async with self.session.get(url,
                                            allow_redirects=True,
                                            headers=self.headers) as resp:

                    if resp.status != 200:
                        self.logger.warning("{url} was not reachable. HTTP "
                                            "error code {resp.status} was "
                                            "returned".format(**locals()))
                        raise SorterResponseCodeError

                    self.logger.info("{url}: loaded "
                                     "successfully.".format(**locals()))
                    return await resp.text()
        except asyncio.TimeoutError:
            self.logger.warning("{url}: timed out after "
                                "{self.page_load_timeout}.".format(**locals()))
            raise SorterTimeoutError
        except (aiosocks.errors.SocksError,
                aiohttp.errors.ServerDisconnectedError,
                aiohttp.errors.ClientResponseError) as exc:
            self.logger.warning("{url} was not reachable: "
                                "{exc}".format(**locals()))
            raise SorterConnectionError
        except aiohttp.errors.ClientOSError as exception_msg:
            if "SSL" in exception_msg:
                self.logger.warning("{url}: certificate error (probably due to "
                                    "use of a self-signed "
                                    "cert.".format(**locals()))
                raise SorterCertError
            else:
                raise
        except (ssl.CertificateError, aiohttp.errors.ClientOSError):
            self.logger.warning("{url}: certificate error (probably due to "
                                "use of a self-signed "
                                "cert.".format(**locals()))
            raise SorterCertError


    async def parse_onion_links(self, response):
        """Find all .onion URLs in a webpage text."""
        onion_regex = "[0-9a-z]{16}\.onion"
        onions = re.findall(onion_regex, response)
        if not onions:
            raise SorterEmptyDirectoryError
        return set(["http://" + x for x in onions])


    def sort_onions(self, class_tests):
        """Sort the self.onions set of onion services into the sets defined by
        the keys of the class_tests dictionary using the tests given by the
        associated values."""
        self.loop.run_until_complete(self._sort_onions(class_tests))


    async def _sort_onions(self, class_tests):
        self.class_data = OrderedDict()
        for class_name in class_tests.keys():
            self.class_data[class_name] = set()
        self.failed_onions = set()

        self.logger.info("Putting {} onions on the queue to be "
                         "sorted...".format(len(self.onions)))
        for onion_service in self.onions:
            self.q.put_nowait(onion_service)

        self.logger.info("Starting {self.max_tasks} workers sorting .onion "
                         "URLs into the sets {}...".format(list(class_tests),
                                                          **locals()))
        workers = [asyncio.Task(self.sort_onion(class_tests)) for _ in range(self.max_tasks)]

        await self.q.join()

        if self.failed_onions:
            self.logger.info("Retrying {} onion services that the sorter "
                             "was unable to reach on first "
                             "attempt.".format(len(self.failed_onions)))
            for failed_onion in self.failed_onions:
                self.q.put_nowait(failed_onion)

        await self.q.join()
        self.logger.info("Sorting onions process completed.")
        self.logger.info("Stopping all workers...")
        for w in workers:
            w.cancel()

        if self.db_handler:
            self.upload_onions()
        else:
            self.pickle_onions()


    async def sort_onion(self, class_tests):
        while True:
            onion_service = await self.q.get()
            try:
                response = await self.fetch(onion_service)
                for class_name, class_test in class_tests.items():
                    lambda_fn = lambda text: eval(class_test)
                    if lambda_fn(response):
                        self.logger.info("{onion_service}: sorted into "
                                         "{class_name}.".format(**locals()))
                        self.class_data[class_name].add(onion_service)
                        break
            except SorterLoggedError:
                self.failed_onions.add(onion_service)
            except:
                self.logger.exception("{onion_service}: unusual exception "
                                      "encountered:".format(**locals()))
                self.failed_onions.add(onion_service)
            finally:
                self.q.task_done()


    def pickle_onions(self):
        ts = get_timestamp("log")
        pickle_jar = join(_log_dir, "class-data_{}.pickle".format(ts))
        self.logger.info("Pickling class data to "
                         "{pickle_jar}...".format(**locals()))
        with open(pickle_jar, "wb") as pj:
                pickle.dump(self.class_data, pj)
        symlink_cur_to_latest(join(_log_dir, "class-data"), ts, "pickle")


    def upload_onions(self):
        self.logger.info("Saving class data to database...")
        self.db_handler.add_onions(self.class_data)


def _securedrop_sort():
    config = get_config()['sorter']
    if config.getboolean("use_database"):
        fpdb = RawStorage()
    else:
        fpdb = None
    class_tests = coalesce_ordered_dict(config["class_tests"])
    
    with Sorter(page_load_timeout=config.getint("page_load_timeout"),
                max_tasks=config.getint("max_tasks"),
                db_handler=fpdb) as sorter:
        sorter.scrape_directories(config["onion_dirs"].split(","))
        sorter.sort_onions(class_tests)


if __name__ == "__main__":
    _securedrop_sort()
