from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree
from urllib.parse import urldefrag


class RobotsRules:
    """Parse robots rules already obtained through the course cache."""

    def __init__(self, robots_url, text):
        self.origin = self._origin(robots_url)
        self.parser = RobotFileParser(robots_url)
        self.parser.parse(text.splitlines())

    @staticmethod
    def _origin(url):
        parsed = urlsplit(url)
        return parsed.scheme.lower(), parsed.netloc.lower()

    def can_fetch(self, user_agent, url):
        """Apply these rules only to URLs from the same origin."""
        if self._origin(url) != self.origin:
            return False

        return self.parser.can_fetch(user_agent, url)

    def sitemap_urls(self):
        """Return sitemap locations declared in robots.txt."""
        return self.parser.site_maps() or []

    def crawl_delay(self, user_agent):
        """Return the declared delay, or None if absent."""
        return self.parser.crawl_delay(user_agent)

def parse_sitemap(content):
    """Return (page_urls, sitemap_urls) from uncompressed XML bytes."""
    # Use a conservative crawler limit, rather than the protocol maximum.
    if not content or len(content) > 5 * 1024 * 1024:
        return [], []

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return [], []

    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

    if root.tag == namespace + "urlset":
        entry_tag = namespace + "url"
        is_index = False
    elif root.tag == namespace + "sitemapindex":
        entry_tag = namespace + "sitemap"
        is_index = True
    else:
        return [], []

    urls = []
    seen = set()

    for entry in root.findall(entry_tag):
        location = entry.find(namespace + "loc")
        if location is None or not location.text:
            continue

        url = urldefrag(location.text.strip())[0]

        # Sitemap locations must be absolute HTTP(S) URLs.
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                continue
        except ValueError:
            continue

        if not url.isascii() or any(char.isspace() for char in url):
            continue

        if url not in seen:
            seen.add(url)
            urls.append(url)

    if is_index:
        return [], urls

    return urls, []