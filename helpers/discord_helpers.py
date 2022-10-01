from pathlib import Path


def get_token_from_file(file: Path) -> str:
    """ Naively parse a file for a token. Expects the format to be <TOKEN_NAME>=<TOKEN>."""
    with file.open() as f:
        return f.read().split('=')[1]
