from urllib.parse import urldefrag

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
    def __init__(self):
        self.seen_urls = set()
        self.longest_url = None
        self.longest_word_count = 0
        self.word_frequencies = {}

    def record_page(self, url, tokens):
        """Record a new page; return False if its URL was recorded."""
        url = urldefrag(url)[0]

        if url in self.seen_urls:
            return False

        self.seen_urls.add(url)

        word_count = len(tokens)
        if word_count > self.longest_word_count:
            self.longest_url = url
            self.longest_word_count = word_count

        for token in tokens:
            if token in self.word_frequencies:
                self.word_frequencies[token] += 1
            else:
                self.word_frequencies[token] = 1

        return True