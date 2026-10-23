from utils import get_logger
from crawler.frontier import Frontier
from crawler.worker import Worker
from crawl_policy import CrawlPolicy
from utils.download import download
from scraper import is_valid

class Crawler(object):
    def __init__(self, config, restart, frontier_factory=Frontier, worker_factory=Worker):
        self.config = config
        self.logger = get_logger("CRAWLER")
        self.frontier = frontier_factory(config, restart)
# Every worker must use this same policy instance.
        self.frontier.policy = CrawlPolicy(config,lambda url: download(url, config, self.logger),is_valid,)        
        self.workers = list()
        self.worker_factory = worker_factory

    def start_async(self):
        self.workers = [
            self.worker_factory(worker_id, self.config, self.frontier)
            for worker_id in range(self.config.threads_count)]
        for worker in self.workers:
            worker.start()

    def start(self):
        self.start_async()
        self.join()

    def join(self):
        for worker in self.workers:
            worker.join()
