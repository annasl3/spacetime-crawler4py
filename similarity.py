def stable_hash(text):
    """Compute a deterministic 64-bit FNV-1a hash."""
    value = 14695981039346656037

    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 1099511628211) & ((1 << 64) - 1)

    return value


class DuplicateDetector:
    """Track previously seen token sequences."""

    def __init__(self):
        self.exact_buckets = {}

    def is_exact_duplicate(self, tokens):
        """Return True if this token sequence was already recorded."""
        text = " ".join(tokens)
        checksum = stable_hash(text)
        bucket = self.exact_buckets.setdefault(checksum, set())

        # Compare the text too, so hash collisions cannot cause false matches.
        if text in bucket:
            return True

        bucket.add(text)
        return False