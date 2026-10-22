from threading import Thread

from inspect import getsource
from utils.download import download
from utils import get_logger
import scraper
import time


class Worker(Thread):
    def __init__(self, worker_id, config, frontier):
        self.logger = get_logger(f"Worker-{worker_id}", "Worker")
        self.config = config
        self.frontier = frontier
        # basic check for requests in scraper
        assert {getsource(scraper).find(req) for req in {"from requests import", "import requests"}} == {-1}, "Do not use requests in scraper.py"
        assert {getsource(scraper).find(req) for req in {"from urllib.request import", "import urllib.request"}} == {-1}, "Do not use urllib.request in scraper.py"
        super().__init__(daemon=True)
        
    def run(self):
        while True:
            # Waits until some domain is free and rested. That domain is now ours.
            tbd_url = self.frontier.get_tbd_url()
            if tbd_url is None:
                self.logger.info("Frontier is empty. Stopping Crawler.")
                break
            try:
                resp = download(tbd_url, self.config, self.logger)
                self.logger.info(
                    f"Downloaded {tbd_url}, status <{resp.status}>, "
                    f"using cache {self.config.cache_server}.")
                # Add new links BEFORE giving the domain back, so the frontier
                # doesn't think we are finished while we still have links.
                for scraped_url in scraper.scraper(tbd_url, resp):
                    self.frontier.add_url(scraped_url)
                self.frontier.mark_url_complete(tbd_url)
            except Exception as e:
                self.logger.error(f"Error on {tbd_url}: {e}")
            finally:
                # Always give the domain back, even after an error,
                # otherwise it stays "busy" forever.
                self.frontier.release_domain(tbd_url)
            # No time.sleep here: the frontier makes us wait instead.
