from urllib.parse import urldefrag, urlparse

def tokenize(text):
    """Split text into lowercase ASCII alphanumeric tokens."""
    tokens = []
    token_characters = []

    for char in text:
        if char.isascii() and char.isalnum():
            token_characters.append(char.lower())
        elif token_characters:
            tokens.append("".join(token_characters))
            token_characters = []

    if token_characters:
        tokens.append("".join(token_characters))

    return tokens

class Analytics:
    """Track statistics for unique crawled pages."""
    def __init__(self):
        self.seen_urls = set()
        self.longest_url = None
        self.longest_word_count = 0
        self.word_frequencies = {}
        self.subdomain_counts = {}

    def record_page(self, url, tokens):
        """Update statistics for a new URL; return False for a repeated URL."""
        # Links to different sections of the same page count as one URL.
        url = urldefrag(url)[0] 

        if url in self.seen_urls:
            return False

        self.seen_urls.add(url)

        # Include stop words when measuring page length.
        word_count = len(tokens)
        if word_count > self.longest_word_count:
            self.longest_url = url
            self.longest_word_count = word_count

        # Keep all word counts, filter stop words when generating the report.
        for token in tokens:
            if token in self.word_frequencies:
                self.word_frequencies[token] += 1
            else:
                self.word_frequencies[token] = 1

        host = (urlparse(url).hostname or "").lower()

        # Count each full ICS subdomain separately.
        if host.endswith(".ics.uci.edu"):
            if host in self.subdomain_counts:
                self.subdomain_counts[host] += 1
            else:
                self.subdomain_counts[host] = 1

        return True