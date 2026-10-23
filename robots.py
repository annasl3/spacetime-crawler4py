from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser


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