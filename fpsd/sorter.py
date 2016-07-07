#!/usr/bin/env python3.5

# Pass any number of hidden service directories to a Sorter instance and watch
# sort() scrape all the .onions the page, then scrape those .onions in turn,
# searching for SDs and sites that mention SD, sorting them accordingly. Be
# sure to read the note at the bottom regarding the ProxyConnector and how
# you'll need to setup Privoxy. Data is dumped into a pickle file.
# ./logging/class-data-latest.pickle will point you to the most recent results.

import asyncio
PYTHONASYNCIODEBUG = 1 # Enable asyncio debug mode
import aiohttp
import pickle
import utils
import re

class Sorter:
    def __init__(self, version, dir_urls):
        # Let's pretend we're Tor Browser
        u = 'Mozilla/5.0 (Windows NT 6.1; rv:38.0) Gecko/20100101 Firefox/38.0'
        self.headers = {'user-agent': u}
        # SD 0.3.6 still has 0.3.5 in the version string, so it's impossible to
        # differentiate between the two...
        self.version = version
        # 10 is a good balance between speed and not overloading connections,
        # increasing the chances of errors
        self.max_tasks = 10
        self.sets = ['master_sd', 'not_sd', 'deprecated_sd', 'mentions_sd']
        for i in self.sets + ['_seen_urls']:
            setattr(self, i, set())
        logger.info('Creating our asyncio queue...')
        self.q = asyncio.Queue()

        # aiohttp's ClientSession does connection pooling and HTTP keep-alives
        # for us
        self.session = aiohttp.ClientSession(loop=loop, connector=conn)

        logger.info('Putting directory URLs in the queue...')
        for dir_url in dir_urls:
            self.q.put_nowait((dir_url, True))


    async def sort(self):
        """Run the sorter until all work is done."""
        workers = [asyncio.Task(self.work()) for _ in range(self.max_tasks)]

        logger.info('Starting {} workers on queue...'.format(self.max_tasks))
        # When all work is done, exit and close client
        await self.q.join()
        logger.info('Queue is empty, let\'s lay off these workers...')
        for w in workers:
            w.cancel()
        logger.info('Closing out any lingering HTTP connections...')
        self.session.close()

    async def work(self):
        while True:
            url, is_dir_url = await self.q.get()

            # Download page and add new links to self.q
            try:
                await self.fetch(url, is_dir_url)
            except Exception as exc:
            # We probably got an 'OK' response code, but something else went
            # wrong. Let's log the error.
                logger.warning('{} {}'.format(url, exc))
            finally:
                self.q.task_done()

    async def fetch(self, url, is_dir_url):
        logger.info('Fetching {}'.format(url))
        with aiohttp.Timeout(20):
            async with self.session.get(url, allow_redirects=True,
                                        headers=self.headers) as response:
                try:
                    assert response.status == 200
                except:
                    # If we don't get a 'OK', log why, and move on to other URLs
                    logger.warning('{} {}'.format(url, response.status))
                    return

                if is_dir_url == True:
                    logger.info('Parsing .onions from directory "{}"'.format(url))
                    links = await self.parse_hs_links(response)
                    logger.info('Adding onions from "{}" to the queue'.format(url))
                    for url in links:
                        # Put all scraped links we haven't yet seen on our queue
                        if url not in self._seen_urls:
                            self._seen_urls.add(url)
                            self.q.put_nowait((url, False))

                # Does this site mention SecureDrop?
                sd_regex = '[Ss]{1}ecure {0,1}[Dd]{1}rop'
                if await self.regex_search(sd_regex, response):
                    # Does it have a SD version string?
                    v_str_regex = 'Powered by SecureDrop 0\.[0-3]\.[0-9\.]+'
                    v_str_match = await self.regex_search(v_str_regex, response)
                    if v_str_match:
                        v_str = v_str_match.group(0)
                        # Is it up to date?
                        if self.version in version:
                            self.master_sd.add(url)
                            logger.info('SD {}: {}'.format(self.version, url))
                        else:
                            self.deprecated_sd.add(url)
                            ver_num = re.search('[0-9\.]+', version).group(0)
                            logger.info('SD {}: {}'.format(ver_num, url))
                    else:
                        # Just mentions SD, but not one itself
                        self.mentions_sd.add(url)
                        logger.info('Mentions SD: {}'.format(url))
                else:
                    # Not an SD, doesn't even mention SD
                    self.not_sd.add(url)
                    logger.info('Not a SD: {}'.format(url))
                        
    async def regex_search(self, regex, response):
        return re.search(regex, await response.text())

    async def parse_hs_links(self, response):
        onion_regex = '[0-9a-z]{16}\.onion'
        onions = re.findall(onion_regex, await response.text())
        # Need to have the http prefix for aiohttp to know what to do
        return set(['http://' + x for x in onions])

    def pickle_onions(self):
        ts = utils.timestamp()
        pickle_jar = 'logging/class-data_{}.pickle'.format(ts)
        with open(pickle_jar, 'wb') as pj:
            for i in self.sets:
                # Convert to list because urls need a fixed order such that
                # data crawled across multiple machines can be combined
                pickle.dump(list(getattr(self, i)), pj)
        utils.symlink_cur_to_latest('class-data', ts, 'pickle')

if __name__ == "__main__":
    import configparser
    from os.path import abspath, dirname, join

    config = configparser.ConfigParser()
    config.read('config.ini')
    config = config['sorter']
    onion_dirs = config['onion_dirs'].split()
    version = config['current_version']

    repo_root = dirname(abspath(__file__))
    log_dir = join(repo_root, "logging")

    logger = utils.setup_logging(log_dir, "sorter")

    logger.info('Starting an asynchronous event loop...')
    loop = asyncio.get_event_loop()

    logger.info("Connecting to Privoxy at 127.0.0.1:8118")
    # SSL verification is disabled because we're mostly dealing with almost
    # exclusively self-signed certs in the HS space.
    conn = aiohttp.ProxyConnector(proxy="http://localhost:8118", verify_ssl=False)

    # The Sorter can begin with any number of directories from which to scrape
    # then sort onion URLs into the four categories in the next block
    logger.info("Initializing sorter with: {}...".format(onion_dirs))
    sorter = Sorter(version, onion_dirs)
    logger.info('Beginning to scrape and sort from onion directories...')
    loop.run_until_complete(sorter.sort())

    logger.info('Closing event loop...')
    loop.close()
    logger.info('Last, but not least, let\'s pickle the onions...')
    sorter.pickle_onions()
    logger.info('Program exiting succesfully...')
