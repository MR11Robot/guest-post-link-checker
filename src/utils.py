from urllib.parse import urlparse, ParseResultBytes, ParseResult


def is_valid_url(string) -> bool:
    """Check if a string is a valid URL"""
    result: ParseResult | ParseResultBytes = urlparse(string)
    return bool(result.scheme and result.netloc)