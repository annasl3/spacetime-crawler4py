def stable_hash(text):
    """Compute a deterministic 64-bit FNV-1a hash."""
    value = 14695981039346656037

    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 1099511628211) & ((1 << 64) - 1)

    return value


class DuplicateDetector:
    """Track previously seen token sequences."""

    def __init__(self, threshold=3):
        if not 0 <= threshold <= 64:
            raise ValueError("threshold must be between 0 and 64")

        self.exact_buckets = {}
        self.fingerprints = []
        self.threshold = threshold

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
    
    def is_duplicate(self, url, tokens):
        """Record content and report exact or near duplication."""
        # Empty content provides no useful similarity evidence.
        if not tokens:
            return False

        if self.is_exact_duplicate(tokens):
            return True

        fingerprint = simhash(tokens)

        for previous_url, previous_fingerprint in self.fingerprints:
            distance = hamming_distance(
                fingerprint, previous_fingerprint
            )
            if distance <= self.threshold:
                return True

        # Keep one representative for each accepted content group.
        self.fingerprints.append((url, fingerprint))
        return False


def simhash(tokens):
    """Build a 64-bit fingerprint using token-frequency weights."""
    votes = [0] * 64

    for token in tokens:
        token_hash = stable_hash(token)

        for bit in range(64):
            if token_hash & (1 << bit):
                votes[bit] += 1
            else:
                votes[bit] -= 1

    fingerprint = 0
    for bit in range(64):
        if votes[bit] > 0:
            fingerprint |= 1 << bit

    return fingerprint

def hamming_distance(left, right):
    """Count the differing bits between two fingerprints."""
    different = left ^ right
    distance = 0

    while different:
        different &= different - 1
        distance += 1

    return distance