def stable_hash(text):
    """Compute a deterministic 64-bit FNV-1a hash."""
    value = 14695981039346656037

    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 1099511628211) & ((1 << 64) - 1)

    return value