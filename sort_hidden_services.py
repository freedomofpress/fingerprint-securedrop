#!/usr/bin/env python

# Pass any number of hidden service directories to a Crawler instance and watch
# crawl() scrape all the .onion links on the page, then crawl them searching
# for SDs and sites that mention SD, sorting them accordingly. Be sure to read
# the note at the bottom regarding the ProxyConnector and how you'll need to
# setup Privoxy.

from ast import literal_eval
import configparser
config = configparser.ConfigParser()
config.read('config.ini')
directories_to_scrape_and_sort = literal_eval(config['Sort Hidden Services']['directories_to_scrape_and_sort'])

import asyncio
PYTHONASYNCIODEBUG = 1 # Enable asyncio debug mode
import aiohttp
import re
from utils import setup_logging

class Crawler:
    def __init__(self, dir_urls):
        self.max_tasks = 10
        for i in ['master_sd', 'deprecated_sd', 'mentions_sd', 'not_sd']:
            setattr(self, i, set())
        self.q = asyncio.Queue()

        # aiohttp's ClientSession does connection pooling and HTTP keep-alives
        # for us
        self.session = aiohttp.ClientSession(loop=loop, connector=conn)

        # Put (URL, is_dir_url) in the queue
        for dir_url in dir_urls:
            self.q.put_nowait((dir_url, True))


    async def crawl(self):
        """Run the crawler until all work is done."""
        workers = [asyncio.Task(self.work()) for _ in range(self.max_tasks)]

        # When all work is done, exit and close client
        await self.q.join()
        for w in workers:
            w.cancel()
        self.session.close()

        return self.master_sd, self.deprecated_sd, self.mentions_sd, self.not_sd

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
        async with self.session.get(url, allow_redirects=True) as response:
            try:
                assert response.status == 200
            except:
                # If we don't get a 'OK', log why, and move on to other URLs
                logger.warning('{} {}'.format(url, response.status))
                return

            if is_dir_url == True:
                links = await self.parse_hs_links(response)
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
    
if __name__ == "__main__":
    logger = setup_logging('sorter')
    loop = asyncio.get_event_loop()
    # SSL verification is disabled because we're mostly dealing with almost
    # exclusively self-signed certs in the HS space.
    conn = aiohttp.ProxyConnector(proxy="http://[::1]:8118", verify_ssl=False)
    # The Crawler can begin with any number of directories from which to scrape
    # then sort onion URLs into the four categories in the next block
    crawler = Crawler(directories_to_scrape_and_sort)
    master_sd, deprecated_sd, mentions_sd, not_sd = loop.run_until_complete(crawler.crawl())
    loop.close()

    logger.info('Up to date SDs: {}'.format(master_sd))
    logger.info('Not up to date SDs: {}'.format(deprecated_sd))
    logger.info('Mentions SD: {}'.format(mentions_sd))
    logger.info('Not SDs: {}'.format(not_sd))
