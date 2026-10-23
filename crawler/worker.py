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
                resp, sitemap_pages = self.frontier.policy.fetch_page(
                    tbd_url
                )

                for page_url in sitemap_pages:
                    self.frontier.add_url(page_url)

                if resp is None:
                    # Leave it incomplete on disk so a later run can retry.
                    self.logger.info(
                        "Not fetched; blocked or unavailable: %s",
                        tbd_url,
                    )
                    continue

                self.logger.info(
                    "Downloaded %s, status <%s>, using cache %s.",
                    tbd_url,
                    resp.status,
                    self.config.cache_server,
                )

                for scraped_url in scraper.scraper(tbd_url, resp):
                    self.frontier.add_url(scraped_url)

                self.frontier.mark_url_complete(tbd_url)

            except Exception:
                self.logger.exception(
                    "Error processing %s", tbd_url
                )

            finally:
                # Always release the reserved domain, including on failure.
                self.frontier.release_domain(tbd_url)
