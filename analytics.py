import json
import os
from threading import RLock
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

def load_stop_words(path):
    """Load stop words using the same tokenization rules."""
    stop_words = set()

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            stop_words.update(tokenize(line))

    return stop_words

class Analytics:
    """Track statistics for unique crawled pages."""

    def __init__(self, save_path="analytics.json"):
        self.save_path = save_path
        self._lock = RLock()
        self._reset_statistics()
        self._load()

    def _reset_statistics(self):
        """Reset the in-memory statistics."""
        self.seen_urls = set()
        self.longest_url = None
        self.longest_word_count = 0
        self.word_frequencies = {}
        self.subdomain_counts = {}

    def record_page(self, url, tokens):
        """Update statistics and restore saved state if writing fails."""
        with self._lock:
            try:
                return self._record_page(url, tokens)
            except OSError:
                # Discard unsaved changes and restore the last snapshot.
                self._reset_statistics()
                self._load()
                raise

    def _record_page(self, url, tokens):
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

        # Filter stop words only when generating the report.
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

        # Save before the worker marks this page as complete.
        self.flush()
        return True

    def flush(self):
        """Save a consistent snapshot of the shared statistics."""
        with self._lock:
            self._save()

    def _save(self):
        """Save all statistics as one JSON snapshot."""
        data = {
            "seen_urls": list(self.seen_urls),
            "longest_url": self.longest_url,
            "longest_word_count": self.longest_word_count,
            "word_frequencies": self.word_frequencies,
            "subdomain_counts": self.subdomain_counts,
        }

        # Write a complete temporary file before replacing the old snapshot.
        temporary_path = self.save_path + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        os.replace(temporary_path, self.save_path)

    def _load(self):
        """Restore statistics from an existing JSON snapshot."""
        if not os.path.exists(self.save_path):
            return

        with open(self.save_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.seen_urls = set(data["seen_urls"])
        self.longest_url = data["longest_url"]
        self.longest_word_count = data["longest_word_count"]
        self.word_frequencies = data["word_frequencies"]
        self.subdomain_counts = data["subdomain_counts"]

    def top_words(self, stop_words, limit=50):
        """Return the most frequent words, excluding stop words."""
        words = []

        with self._lock:
            for word, count in self.word_frequencies.items():
                if word not in stop_words:
                    words.append((word, count))

        words.sort(key=lambda item: (-item[1], item[0]))
        return words[:limit]

    def subdomain_lines(self):
        """Return ICS subdomain URLs and counts in alphabetical order."""
        with self._lock:
            counts = sorted(self.subdomain_counts.items())

        return [
            f"http://{host}, {count}"
            for host, count in counts
        ]

    def report(self, stop_words):
        """Return the required crawl statistics as plain text."""
        with self._lock:
            longest_url = self.longest_url or "N/A"

            text = f"Unique pages: {len(self.seen_urls)}\n\n"
            text += f"Longest page: {longest_url}\n"
            text += f"Word count: {self.longest_word_count}\n\n"

            text += "Top 50 words (excluding English stop words):\n"
            for word, count in self.top_words(stop_words):
                text += f"{word}, {count}\n"

            text += f"\nICS subdomains: {len(self.subdomain_counts)}\n"
            for line in self.subdomain_lines():
                text += line + "\n"

            return text