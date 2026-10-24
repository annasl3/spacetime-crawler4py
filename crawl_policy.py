import gzip
import io
import logging
import time
from threading import Lock
from urllib.parse import urlsplit, urldefrag

from robots import RobotsRules, parse_sitemap


ALLOWED_DOMAINS = (
    "ics.uci.edu",
    "cs.uci.edu",
    "informatics.uci.edu",
    "stat.uci.edu",
)

MAX_BYTES = 5 * 1024 * 1024
MAX_SITEMAPS = 10


class CrawlPolicy:
    """Share robots rules and serialize requests per assignment domain."""

    def __init__(self, config, fetch, valid_page):
        self.config = config
        self.fetch = fetch
        self.valid_page = valid_page
        self.locks = {domain: Lock() for domain in ALLOWED_DOMAINS}
        self.delays = {
            domain: max(0.5, config.time_delay)
            for domain in ALLOWED_DOMAINS
        }
        self.last_finished = {}
        self.rules = {}
        self.sitemaps_done = set()
        self.logger = logging.getLogger("CRAWL_POLICY")

    @staticmethod
    def _origin(url):
        parsed = urlsplit(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    @staticmethod
    def _domain_key(url):
        """Group subdomains under the four assignment domains."""
        host = (urlsplit(url).hostname or "").lower()
        for domain in ALLOWED_DOMAINS:
            if host == domain or host.endswith("." + domain):
                return domain
        raise ValueError("URL is outside the allowed domains")

    @staticmethod
    def _in_scope(url):
        """Validate metadata URLs without rejecting .xml or .gz."""
        if (
            not url.isascii()
            or len(url) > 2048
            or any(char.isspace() for char in url)
        ):
            return False

        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
            return (
                parsed.scheme in ("http", "https")
                and parsed.username is None
                and parsed.password is None
                and parsed.port in (None, 80, 443)
                and any(
                    host == domain or host.endswith("." + domain)
                    for domain in ALLOWED_DOMAINS
                )
            )
        except ValueError:
            return False

    def _download(self, url):
        """Called while holding this domain group's lock."""
        domain = self._domain_key(url)
        previous = self.last_finished.get(domain)
        if previous is not None:
            remaining = self.delays[domain] - (
                time.monotonic() - previous
            )
            if remaining > 0:
                time.sleep(remaining)

        try:
            return self.fetch(url)
        except Exception:
            self.logger.exception("Download failed: %s", url)
            return None
        finally:
            self.last_finished[domain] = time.monotonic()

    def _body(self, response, requested_url, limit=MAX_BYTES, allow_cross_origin=False):
        if response is None or response.status != 200:
            return None

        raw = response.raw_response
        if raw is None:
            return None

        final_url = raw.url or requested_url

        # Keep redirected responses within the allowed domains.
        if not self._in_scope(final_url):
            return None

        # Allow a different origin only when explicitly requested.
        if (
            not allow_cross_origin
            and self._origin(final_url) != self._origin(requested_url)
        ):
            return None

        content = raw.content
        if content is None or len(content) > limit:
            return None

        return content

    def _get_rules(self, origin):
        cached = self.rules.get(origin)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        robots_url = origin + "/robots.txt"
        lifetime = 3600

        for attempt in range(3):
            response = self._download(robots_url)
            status = getattr(response, "status", None)

            if status == 404:
                text = ""  # No robots file: allow access.
                break

            if status in (401, 403):
                text = "User-agent: *\nDisallow: /"
                break

            content = self._body(
                response,
                robots_url,
                512 * 1024,
                allow_cross_origin=True,
            )
            if content is not None:
                text = content.decode("utf-8-sig", errors="replace")
                break

            if attempt < 2:
                self.logger.warning(
                    "Robots unavailable for %s; "
                    "attempt %d/3 failed, retrying in 60 seconds",
                    origin,
                    attempt + 1,
                )
                time.sleep(60)
            else:
                text = "User-agent: *\nDisallow: /"
                lifetime = 60
                self.logger.warning(
                    "Robots unavailable for %s after 3 attempts; "
                    "deny for 60 seconds",
                    origin,
                )

        rules = RobotsRules(robots_url, text)
        declared_delay = rules.crawl_delay(self.config.user_agent)
        if declared_delay is not None:
            domain = self._domain_key(origin)
            self.delays[domain] = max(self.delays[domain], declared_delay)

        self.rules[origin] = (
            time.monotonic() + lifetime,
            rules,
        )
        return rules

    def _sitemap_pages(self, origin, rules):
        if origin in self.sitemaps_done:
            return []

        pending = list(rules.sitemap_urls())
        visited = set()
        pages = set()

        while pending and len(visited) < MAX_SITEMAPS:
            url = urldefrag(pending.pop())[0]

            if (
                url in visited
                or not self._in_scope(url)
                or self._origin(url) != origin
            ):
                continue

            visited.add(url)

            if not rules.can_fetch(self.config.user_agent, url):
                continue

            for attempt in range(3):
                response = self._download(url)
                content = self._body(response, url)
                if content is not None:
                    break

                if getattr(response, "status", None) in (401, 403, 404):
                    break

                if attempt < 2:
                    self.logger.warning(
                        "Sitemap unavailable: %s; retrying in 5 seconds",
                        url,
                    )
                    time.sleep(5)

            if content is None:
                self.logger.warning("Skipping unavailable sitemap: %s", url)
                continue

            # Bound decompression output as well as compressed input.
            if content.startswith(b"\x1f\x8b"):
                try:
                    with gzip.GzipFile(
                        fileobj=io.BytesIO(content)
                    ) as stream:
                        content = stream.read(MAX_BYTES + 1)
                except (OSError, EOFError):
                    continue

            if len(content) > MAX_BYTES:
                continue

            page_urls, sitemap_urls = parse_sitemap(content)
            pending.extend(sitemap_urls)

            for page_url in page_urls:
                if (
                    self._in_scope(page_url)
                    and self._origin(page_url) == origin
                    and self.valid_page(page_url)
                    and rules.can_fetch(
                        self.config.user_agent, page_url
                    )
                ):
                    pages.add(page_url)

        if pending:
            self.logger.warning(
                "Sitemap limit reached for %s", origin
            )

        self.sitemaps_done.add(origin)
        return sorted(pages)

    def fetch_page(self, url):
        """Return (response, discovered_pages); None means no page fetched."""
        if not self._in_scope(url) or not self.valid_page(url):
            return None, []

        domain = self._domain_key(url)
        with self.locks[domain]:
            origin = self._origin(url)
            rules = self._get_rules(origin)

            if not rules.can_fetch(self.config.user_agent, url):
                self.logger.info("Robots blocked: %s", url)
                return None, []

            pages = self._sitemap_pages(origin, rules)
            response = self._download(url)

        # The original domain lock has been released.
        if response is None or response.raw_response is None:
            return response, pages

        final_url = response.raw_response.url or url
        if not self._in_scope(final_url):
            self.logger.info(
                "Final URL outside allowed scope: %s", final_url
            )
            return None, pages

        final_origin = self._origin(final_url)
        if final_origin == origin:
            final_rules = rules
        else:
            final_domain = self._domain_key(final_url)
            with self.locks[final_domain]:
                final_rules = self._get_rules(final_origin)

        if not final_rules.can_fetch(self.config.user_agent, final_url):
            self.logger.info("Robots blocked final URL: %s", final_url)
            return None, pages

        return response, pages