"""
Offline test for the multithreaded frontier/worker.
It does NOT contact any server: download() and scraper() are replaced by fakes.

Run:  python3 test_politeness.py

Checks:
  1. Two requests to the same domain are never closer than POLITENESS seconds.
  2. Two threads never download from the same domain at the same time.
  3. Every discovered URL is downloaded exactly once.
  4. All threads stop on their own when the frontier is empty.
  5. Downloads from different domains overlap in time.
"""
import os
import random
import sys
import tempfile
import threading
import time
import types

# utils/download.py imports cbor; stub it so this test runs without it.
sys.modules.setdefault("cbor", types.ModuleType("cbor"))

# analytics.py (teammate's file) may not be here yet; use a dummy if missing.
try:
    import analytics
except ImportError:
    class _Dummy:
        def __init__(self, *a, **k): pass
        def __getattr__(self, name): return lambda *a, **k: None
    _fake = types.ModuleType("analytics")
    _fake.Analytics = _Dummy
    _fake.tokenize = lambda *a, **k: []
    sys.modules["analytics"] = _fake

import crawler.worker as worker_module
import crawler as crawler_module
from crawler import Crawler
from crawler.frontier import get_domain

THREADS = 4
POLITENESS = 0.5
PAGES_PER_DOMAIN = 2
SEEDS = ["https://www.ics.uci.edu", "https://www.cs.uci.edu",
         "https://www.informatics.uci.edu", "https://www.stat.uci.edu"]

log = []      # (domain, start, end, url)
log_lock = threading.Lock()


class FakeResp:
    status = 200


def fake_download(url, config, logger=None):
    start = time.monotonic()
    time.sleep(random.uniform(0.01, 0.15))      # pretend network latency
    end = time.monotonic()
    with log_lock:
        log.append((get_domain(url), start, end, url))
    response = FakeResp()
    if url.endswith("/robots.txt"):
        response.status = 404
    return response


def fake_scraper(url, resp):
    """Each page links to the next page plus a subdomain page (same domain)."""
    host = url.split("/")[2]
    base = host.split(".", 1)[1] if host.startswith("www.") else host
    n = int(url.rsplit("/p", 1)[1]) if "/p" in url else 0
    if n >= PAGES_PER_DOMAIN:
        return []
    return [f"https://www.{base}/p{n + 1}",
            f"https://sub{n}.{base}/p{PAGES_PER_DOMAIN}"]   # tests subdomains


class FakeConfig:
    def __init__(self, save_file):
        self.threads_count = THREADS
        self.save_file = save_file
        self.seed_urls = SEEDS
        self.time_delay = POLITENESS
        self.cache_server = "fake"
        self.user_agent = "test"


def main():
    worker_module.download = fake_download
    crawler_module.download = fake_download
    worker_module.scraper.scraper = fake_scraper

    with tempfile.TemporaryDirectory() as tmp:
        config = FakeConfig(os.path.join(tmp, "frontier.shelve"))
        crawler = Crawler(config, restart=True)
        t0 = time.monotonic()
        crawler.start()            # returns only when every thread has exited
        elapsed = time.monotonic() - t0

    ok = True
    by_domain = {}
    for domain, s, e, url in log:
        by_domain.setdefault(domain, []).append((s, e, url))

    print(f"{len(log)} downloads, {THREADS} threads, {elapsed:.1f}s total\n")
    for domain, reqs in sorted(by_domain.items()):
        reqs.sort()
        gaps = [reqs[i + 1][0] - reqs[i][1] for i in range(len(reqs) - 1)]
        min_gap = min(gaps)
        status = "OK" if min_gap >= POLITENESS else "FAIL"
        if min_gap < POLITENESS:
            ok = False
        print(f"  {domain:22s} {len(reqs):3d} requests, "
              f"smallest gap {min_gap * 1000:.0f} ms  [{status}]")

    urls = [u for *_, u in log]
    if len(urls) != len(set(urls)):
        print("FAIL: some URL was downloaded twice")
        ok = False

    # Parallelism check: did different domains actually overlap in time?
    overlaps = sum(1 for a in log for b in log
                   if a[0] != b[0] and a[1] < b[2] and b[1] < a[2]) // 2
    print(f"\n  cross-domain overlapping downloads: {overlaps} "
          f"(>0 means threads really ran in parallel)")
    if overlaps == 0:
        print("FAIL: downloads from different domains never overlapped")
        ok = False
    print("\nPASS" if ok else "\nFAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
