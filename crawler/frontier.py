import os
import shelve
import dbm.dumb

from threading import Thread, RLock
from queue import Queue, Empty

from utils import get_logger, get_urlhash, normalize
from scraper import is_valid

import time
from collections import deque
from threading import Lock
from urllib.parse import urlparse

# The 4 domains we crawl. Subdomains (like vision.ics.uci.edu) count as
# their parent domain (ics.uci.edu) for politeness.
DOMAINS = ["ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu"]


def get_domain(url):
    host = urlparse(url).netloc.lower()
    for d in DOMAINS:
        # "." + d so that informatics.uci.edu does not count as ics.uci.edu
        if host == d or host.endswith("." + d):
            return d
    return host

class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self.lock = Lock()          # every shared variable is used under this lock
        self.queues = {}            # domain -> deque of urls waiting
        self.busy = set()           # domains some thread is downloading right now
        self.next_time = {}         # domain -> earliest time it can be used again
        self.working = 0            # how many threads are downloading right now
        
        # Use shelve with a file backend.
        flag = "n" if restart else "c"
        self.save = shelve.Shelf(
            dbm.dumb.open(self.config.save_file, flag)
        )

        if restart:
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            # Set the frontier state with contents of save file.
            self._parse_save_file()
            if self._count() == 0:
                for url in self.config.seed_urls:
                    self.add_url(url)

    def _count(self):
        # How many urls are in the save file in total.
        return len(self.save)

    def _parse_save_file(self):
        ''' This function can be overridden for alternate saving techniques. '''
        total_count = self._count()
        tbd_count = 0
        for url, completed in self.save.values():
            if not completed and is_valid(url):
                self._push(url)
                tbd_count += 1
        self.logger.info(
            f"Found {tbd_count} urls to be downloaded from {total_count} "
            f"total urls discovered.")

    def _push(self, url):
        # Put url into its domain's queue.
        domain = get_domain(url)
        if domain not in self.queues:
            self.queues[domain] = deque()
        self.queues[domain].append(url)

    def get_tbd_url(self):
        # Keep trying until we get a url, or the crawl is finished.
        while True:
            with self.lock:
                now = time.time()
                anything_left = False
                for domain, q in self.queues.items():
                    if len(q) == 0:
                        continue
                    anything_left = True
                    free = domain not in self.busy
                    rested = now >= self.next_time.get(domain, 0)
                    if free and rested:
                        self.busy.add(domain)   # borrow it (still inside the lock!)
                        self.working += 1
                        return q.popleft()

                # Finished only if no urls are left AND nobody is still
                # downloading (they might still find new links).
                if not anything_left and self.working == 0:
                    return None

            # Nothing ready yet: wait a little (OUTSIDE the lock) and try again.
            time.sleep(0.05)

    def add_url(self, url):
        url = normalize(url)
        urlhash = get_urlhash(url)

        with self.lock:
            if urlhash not in self.save:
                self.save[urlhash] = (url, False)
                self.save.sync()
                self._push(url)

    def mark_url_complete(self, url):
        urlhash = get_urlhash(url)

        with self.lock:
            if urlhash not in self.save:
                self.logger.error(
                    f"Completed url {url}, but have not seen it before."
                )

            self.save[urlhash] = (url, True)
            self.save.sync()
            
    def release_domain(self, url):
        # Give the domain back and start its 0.5 s rest from NOW.
        domain = get_domain(url)
        with self.lock:
            self.busy.discard(domain)
            self.next_time[domain] = time.time() + self.config.time_delay
            self.working -= 1
