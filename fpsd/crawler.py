#!/usr/bin/env python3.5

# Automates visiting onion services using Tor Browser in a virtual framebuffer
# and logs Tor cell traces from them

from io import SEEK_END, SEEK_SET
from os import mkdir
from os.path import abspath, dirname, expanduser, join
# import pyasn
import random
import stem
from stem.process import launch_tor, launch_tor_with_config
from stem.control import Controller
from sys import exit, exc_info
from time import sleep
import urllib.parse

from site import addsitedir
_repo_root = dirname(abspath(__file__))
_log_dir = join(_repo_root, "logging")
_tbselenium_path = join(_repo_root, "tor-browser-selenium")
addsitedir(_tbselenium_path)
from tbselenium.tbdriver import TorBrowserDriver
from tbselenium.common import USE_RUNNING_TOR
from tbselenium.utils import start_xvfb, stop_xvfb

from utils import setup_logging, timestamp, timestamp_file, symlink_cur_to_latest

from selenium.common.exceptions import WebDriverException, TimeoutException
import http.client
from traceback import format_exception

# The Crawler handles most errors internally so the user does not have to worry
# about exception handling
class CrawlerException(Exception):
    """Base class for Crawler exceptions."""

class CrawlerLoggedError(CrawlerException):
    """Raised when a crawler encounters and logs a boring exception."""

class CrawlerReachedErrorPage(CrawlerException):
    """Raised when the crawler reaches an error page or the about:newtab
    page"""

class CrawlerNoRendCircError(CrawlerException):
    """Raised when no rendezvous circuits are identified for an onion service
    we have already successfully loaded."""

# These exceptions are known to crash the Crawler
_sketchy_exceptions = [http.client.RemoteDisconnected]


class Crawler:
    """Crawls your onions, but also manages Tor, drives Tor Browser, and uses
    information from your Tor cell log and stem to collect cell sequences."""

    def __init__(self, 
                 take_ownership=True, # Tor dies when the Crawler does
                 torrc_config=None, # torrc override options (dict)
                 torrc_path="/usr/local/etc/tor/torrc",
                 tor_cell_log=join(_log_dir,"tor_cell_seq.log"),
                 control_port=9051,
                 socks_port=9050, 
                 tor_cfg=USE_RUNNING_TOR,
                 run_in_xvfb=True,
                 tbb_path=join(expanduser("~"),"tbb","tor-browser_en-US"),
                 tb_log_path=join(_log_dir,"firefox.log"),
                 page_load_timeout=15,
                 wait_on_page=5,
                 restart_on_sketchy_exception=False):

        self.logger = setup_logging(_log_dir, "crawler")

        self.logger.info("Starting tor daemon...")
        if torrc_config:
            self.tor_process = launch_tor_with_config(config=torrc_config,
                                                      take_ownership=take_ownership)
        else:
            self.tor_process = launch_tor(torrc_path=torrc_path,
                                          take_ownership=take_ownership)
        self.torrc_config = torrc_config
        self.torrc_path = torrc_path
        self.take_ownership = take_ownership
        self.logger.info("Authenticating to the tor controlport...")
        self.authenticate_to_tor_controlport(control_port)
        self.control_port = control_port

        self.logger.info("Opening cell log stream...")
        self.cell_log = open(tor_cell_log, "rb")

        if run_in_xvfb:
            self.logger.info("Starting Xvfb...")
            self.run_in_xvfb = True
            self.virtual_framebuffer = start_xvfb()

        self.logger.info("Starting Tor Browser...")
        self.tb_driver = TorBrowserDriver(tbb_path=tbb_path,
                                          tor_cfg=tor_cfg,
                                          tbb_logfile_path=tb_log_path,
                                          socks_port=socks_port,
                                          control_port=control_port)
        self.tb_driver.set_page_load_timeout(page_load_timeout)
        self.wait_on_page = wait_on_page
        self.restart_on_sketchy_exception = restart_on_sketchy_exception
        # self.control_file = self.get_control_information()


    def authenticate_to_tor_controlport(self, control_port):
        try:
            self.controller = Controller.from_port(port=control_port)
        except stem.SocketError as exc:
            print("Unable to connect to tor on port {}: "
                  "{}".format(self.control_port, exc))
            exit(1)
        try:
            self.controller.authenticate()
        except stem.connection.MissingPassword:
            print("Unable to authenticate to tor controlport. Please add "
                  "`CookieAuth 1` to your tor configuration file.")
            exit(1)

    
    # def get_control_information(self):
    #     os = os.uname().version
    #     ip = # tbd
    #     asn = "dummy" # will use pyasn
    #     location = #  do reverse ip lookup based on IP
    #     tb_version = "6.0.2" # read from Ansible yml file?
    #     sd_version = "0.3.7" # read from _version.py
    #     crawler_version = "1.0" # shell out to _version.py
    #     return dict(os, ip, asn, location, tb_version, sd_version,
    #     crawler_version, self.wait_on_page, self.page_load_timeout)


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.info("Exiting the Crawler...")
        self.logger.info("Closing Tor Browser...")
        self.tb_driver.quit()
        self.logger.info("Closing the virtual framebuffer...")
        if self.run_in_xvfb:
            stop_xvfb(self.virtual_framebuffer)
        self.logger.info("Closing the Tor cell stream...")
        self.cell_log.close()
        self.logger.info("Quitting the Tor process...")
        self.controller.close()
        self.logger.info("Crawler exit complete.")


    def collect_onion_trace(self, url, extra_fn=None, trace_dir=None,
                            iteration=0):
        """Crawl an onion service and collect a complete cell sequence for the
        activity at the time. Also, record additional information about the
        circuits with stem. Optionally, pass a function to execute additional
        actions after the page has loaded."""
        # Todo: create collect_trace method that works for regular sites as
        # well
        assert ".onion" in url, ("This method is only suitable for crawling "
                                 "onion services.")

        self.logger.info("{url}: closing existing circuits before starting "
                         "crawl.".format(**locals()))
        for circuit in self.controller.get_circuits():
            self.controller.close_circuit(circuit.id)

        if not trace_dir:
            # trace_dir = self.make_ts_dir(incl_ctrl_file=True)
            trace_dir = self.make_ts_dir()
        trace_name = urllib.parse.quote(url, safe="") + "-" + str(iteration)
        trace_path = join(trace_dir, trace_name)

        start_idx = self.get_cell_log_pos()
            
        try:
            self.crawl_url(url)
            rend_circ_ids = self.get_rend_circ_ids(url)
            if extra_fn:
                self.execute_extra_fn(url, trace_path, start_idx)
        except CrawlerLoggedError:
            return "failed"
        except CrawlerNoRendCircError:
            self.save_debug_log(url, trace_path, start_idx)
            return "failed"
        except:
            exc_type, exc_value, exc_traceback = exc_info()
            self.logger.warning("{url}: unusual exception {exc_type} "
                                "encountered:".format(**locals()))
            # Log traceback, this is for better formatting
            [self.logger.warning(line) for line in
             format_exception(exc_type, exc_value, exc_traceback)]
            # Also print active circuit info
            self.controller.get_circuits()

            if exc_type in _sketchy_exceptions:
                self.save_debug_log(url, trace_path, start_idx)
                if self.restart_on_sketchy_exception:
                    self.restart_tor()

            return "failed"

        self.logger.info("{url}: saving full trace...".format(**locals()))
        end_idx = self.get_cell_log_pos()
        full_trace = self.get_full_trace(start_idx, end_idx)
        with open(trace_path+"-full", "wb") as fh:
            fh.write(full_trace)

        return "succeeded"


    def make_ts_dir(self, parent_dir=_log_dir, raw_dir_name="batch"):
        """Creates a timestamped folder to hold a group of traces."""
        raw_dirpath = join(parent_dir, raw_dir_name)
        ts = timestamp()
        ts_dir = timestamp_file(raw_dirpath, ts, is_dir=True)
        # Todo: write control file to ts_dir
        symlink_cur_to_latest(raw_dirpath, ts)
        return ts_dir


    def get_cell_log_pos(self):
        """Returns the current position of the last byte in the Tor cell log."""
        return self.cell_log.seek(0, SEEK_END)


    def crawl_url(self, url):
        """Load a web page in Tor Browser and optionally pass a function
        to execute custom actions on it."""

        self.logger.info("{url}: starting page load...".format(**locals()))

        try:
            self.tb_driver.load_url(url, wait_on_page=self.wait_on_page,
                                    wait_for_page_body=True)
        except TimeoutException:
            self.logger.warning("{url}: timed out.".format(**locals()))
            raise CrawlerLoggedError
        except http.client.CannotSendRequest:
            self.logger.warning("{url}: cannot send request--improper "
                                "connection state.".format(**locals()))
            raise CrawlerLoggedError

        # Make sure we haven't just hit an error page or nothing loaded
        try:
            if (self.tb_driver.is_connection_error_page
                or self.tb_driver.current_url == "about:newtab"):
                raise CrawlerReachedErrorPage
        except CrawlerReachedErrorPage:
            self.logger.warning("{url}: reached connection error "
                                "page.".format(**locals()))
            raise CrawlerLoggedError

        self.logger.info("{url}: successfully loaded.".format(**locals()))
            

    def get_rend_circ_ids(self, url):
        """Returns the rendezvous circuit id(s) associated with a given onion
        service."""
        self.logger.info("{url}: collecting circuit "
                         "information...".format(**locals()))
        active_circs = self.controller.get_circuits()
        rend_circ_ids = set()
                  
        for circ in active_circs:
            if (circ.purpose == "HS_CLIENT_REND" and
                circ.socks_username and 
                circ.socks_username in url):
                rend_circ_ids.add(circ.id)

        # If everything goes perfect, we should only see one. Multiple indicate
        # the first failed. Zero indicates one closed abruptly (or there's an
        # error with stem--still waiting on data to confirm or deny).
        rend_circ_ct = len(rend_circ_ids)
        self.logger.info("{url}: {rend_circ_ct} associated rendezvous circuits "
                         "discovered.".format(**locals()))
        if rend_circ_ct == 0:
            raise CrawlerNoRendCircError

        return rend_circ_ids


    def execute_extra_fn(self, url, trace_path, start_idx):
        self.logger.info("{url}: executing extra function "
                         "code...".format(**locals()))
        extra_fn(self, url, trace_path, start_idx)
        self.logger.info("{url}: extra function executed "
                         "successfully.".format(**locals()))


    def save_debug_log(self, url, trace_path, start_idx):
        self.logger.warning("{url}: saving debug log...".format(**locals()))
        exc_time = self.get_cell_log_pos()
        trace = self.get_full_trace(start_idx, exc_time)
        with open(trace_path + "@debug", "wb") as fh:
            fh.write(trace)
        return None


    def get_full_trace(self, start_idx, end_idx):
        """Returns the Tor DATA cells transmitted over a circuit during a
        specified time period."""
        # Sanity check
        assert start_idx >= 0 and end_idx > 0, ("Invalid (negative) logfile "
                                                "position")
        assert end_idx >= start_idx, ("logfile section end_idx must come " # s/>=/>
                                     "after start_idx")

        self.cell_log.seek(start_idx, SEEK_SET)
        return self.cell_log.read(end_idx - start_idx)


    # The take_ownership directive in the stem docs claims that if we delete
    # all references to the Popen subprocess returned by starting tor or closed
    # the connection of a Controller that the tor process will exit. In
    # practice, this doesn't happen. OTOH, calling stem.process.launch_tor will
    # restart the tor process. Todo: figure out why.
    def restart_tor(self):
        """Restart tor."""
        self.logger.info("Restarting the tor process...")
        if self.torrc_config:
            self.tor_process = launch_tor_with_config(config=self.torrc_config,
                                                      take_ownership=self.take_ownership)
        else:
            self.tor_process = launch_tor(torrc_path=self.torrc_path,
                                          take_ownership=self.take_ownership)
        self.controller = Controller.from_port(port=self.control_port)
        self.authenticate_to_tor_controlport(self.control_port)
        self.logger.info("Tor successfully restarted.")


    def collect_set_of_traces(self, url_set, extra_fn=None, trace_dir=None,
                              iteration=0, shuffle=True, retry=True):
        """Collect a set of traces."""
        if not trace_dir:
            # trace_dir = self.make_ts_dir(incl_ctrl_file=True)
            trace_dir = self.make_ts_dir()
        set_size = len(url_set)
        self.logger.info("Saving set of {set_size} traces to "
                         "{trace_dir}.".format(**locals()))

        if shuffle:
            random.shuffle(url_set)

        failed_urls = []

        for url_idx in range(set_size):
            self.logger.info("Collecting trace {} of "
                             "{set_size}...".format(url_idx+1, **locals()))
            url = url_set[url_idx]

            if (self.collect_onion_trace(url, extra_fn=extra_fn,
                                         trace_dir=trace_dir,
                                         iteration=iteration) == "failed"
                and retry):
                failed_urls.append(url)

        if failed_urls:
            failed_ct = len(failed_urls)
            self.logger.info("Retrying {failed_ct} of {set_size} traces that "
                             "failed.".format(**locals()))
            self.collect_set_of_traces(failed_urls, extra_fn=extra_fn,
                                       trace_dir=trace_dir,
                                       iteration=iteration, shuffle=shuffle,
                                       retry=False)


    def crawl_monitored_nonmonitored_classes(self,
                                          monitored_class,
                                          nonmonitored_class,
                                          extra_fn=None,
                                          shuffle=True,
                                          retry=True,
                                          monitored_class_name="monitored",
                                          nonmonitored_class_name="nonmonitored",
                                          ratio=40):
        """Crawl a monitored class ratio times interspersed between the
        crawling of a(n ostensibly larger) non-monitored class."""
        # trace_dir = self.make_ts_dir(incl_ctrl_file=True)
        trace_dir = self.make_ts_dir()
        mon_trace_dir = join(trace_dir, monitored_class_name)
        mkdir(mon_trace_dir)
        nonmon_trace_dir = join(trace_dir, nonmonitored_class_name)
        mkdir(nonmon_trace_dir)
        
        nonmonitored_class_ct = len(nonmonitored_class)
        chunk_size = int(nonmonitored_class_ct / ratio)

        for iteration in range(ratio):
            
            self.logger.info("Beggining iteration {} of {ratio} in the "
                             "{monitored_class_name} "
                             "class".format(iteration + 1, **locals()))
            self.collect_set_of_traces(monitored_class,
                                       trace_dir=mon_trace_dir,
                                       iteration=iteration)

            slice_lb = iteration * chunk_size
            slice_ub = min((iteration + 1) * chunk_size, nonmonitored_class_ct)
            self.logger.info("Crawling services {} through {slice_ub} of "
                             "{nonmonitored_class_ct} in the "
                             "{nonmonitored_class_name} "
                             "class".format(slice_lb + 1, **locals()))
            self.collect_set_of_traces(nonmonitored_class[slice_lb:slice_ub],
                                       trace_dir=nonmon_trace_dir)


if __name__ == "__main__":

    import configparser
    import pickle

    config = configparser.ConfigParser()
    config.read("config.ini")
    config = config["crawler"]

    with open(join(_log_dir, config["class_data"]), 'rb') as pj:
        sds = pickle.load(pj)
        not_sds = pickle.load(pj)

    with Crawler(page_load_timeout=int(config["page_load_timeout"]),
                 wait_on_page=int(config["wait_on_page"]),
                 restart_on_sketchy_exception=bool(config["restart_on_sketchy_exception"])) as crawler:
        crawler.crawl_monitored_nonmonitored_classes(sds, not_sds,
                                                     monitored_class_name="sds",
                                                     nonmonitored_class_name="not-sds",
                                                     ratio=int(config["monitored_nonmonitored_ratio"]))
