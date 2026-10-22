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