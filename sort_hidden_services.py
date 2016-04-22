#!/usr/bin/env python

# Pass any number of hidden service directories to a Sorter instance and watch
# sort() scrape all the .onions the page, then scrape those .onions in turn,
# searching for SDs and sites that mention SD, sorting them accordingly. Be
# sure to read the note at the bottom regarding the ProxyConnector and how
# you'll need to setup Privoxy. Data is dumped into a pickle file.
# ./logging/class-data-latest.pickle will point you to the most recent results.

import configparser
config = configparser.ConfigParser()
config.read('config.ini')
config = config['Sort Hidden Services']
directories_to_sort = config['directories_to_sort'].split()

import asyncio
PYTHONASYNCIODEBUG = 1 # Enable asyncio debug mode
import aiohttp
import re
import pickle
import utils

class Sorter:
    def __init__(self, dir_urls):
        # Let's pretend we're Tor Browser
        self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 6.1; rv:38.0) Gecko/20100101 Firefox/38.0'}
        self.max_tasks = 10
        self.sets = ['master_sd', 'not_sd', 'deprecated_sd', 'mentions_sd']
        for i in self.sets:
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

        logger.info('Starting {} workers on the queue...'.format(self.max_tasks))
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
                logger.info('Adding .onions from "{}" to the queue'.format(url))
                for link in links:
                    # Put all scraped links on our queue
                    self.q.put_nowait((link, False))

            # See if our onion mentions SD
            elif await self.regex_search('[Ss]{1}ecure {0,1}[Dd]{1}rop',
                                         response):
                version = await self.regex_search('Powered by SecureDrop 0\.[0-3]\.[0-9\.]+',
                                                  response)
                # See if our onion actually is a SD instance
                if version:
                    version_str = version.group(0)
                    # Sort by version string
                    if '0.3.5' in version_str:
                        # SD 0.3.6 still has 0.3.5 in the version string, so
                        # it's impossible to differentiate between the two...
                        self.master_sd.add(url)
                        logger.info('SD 0.3.6: {}'.format(url))
                    else:
                        self.deprecated_sd.add(url)
                        # A deprecated SD instance--log the version string
                        logger.info('SD {}: {}'.format(re.search('[0-9\.]+',
                                                                 version_str).group(0),
                                                       url))
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
        return set(['http://' + x for x in re.findall('[0-9a-z]{16}\.onion',
                                                     await response.text())])

    def pickle_onions(self):
        ts = utils.timestamp()
        pickle_jar = 'logging/class-data_{}.pickle'.format(ts)
        with open(pickle_jar, 'wb') as pj:
            for i in self.sets:
                pickle.dump(getattr(self, i), pj)
        utils.symlink_cur_to_latest('class-data', ts, 'pickle')
        

    
if __name__ == "__main__":
    logger = utils.setup_logging('sorter')
    logger.info('Starting asynchronous event loop...')
    loop = asyncio.get_event_loop()
    proxy = "http://[::1]:8118"
    logger.info('Connecting to proxy "{}"'.format(proxy))
    # SSL verification is disabled because we're mostly dealing with almost
    # exclusively self-signed certs in the HS space.
    conn = aiohttp.ProxyConnector(proxy=proxy, verify_ssl=False)
    # The Sorter can begin with any number of directories from which to scrape
    # then sort onion URLs into the four categories in the next block
    logger.info('''Initializing sorter with directories from config file(s): \
{}...'''.format(directories_to_sort))
    sorter = Sorter(directories_to_sort)
    logger.info('Beginning to scrape and sort from directories...')
    loop.run_until_complete(sorter.sort())
    logger.info('Closing event loop...')
    loop.close()
    logger.info('Last, but not least, let\'s pickle the onions...')
    sorter.pickle_onions()
    logger.info('Program exiting succesfully...')
