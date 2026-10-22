import re
import atexit
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from analytics import Analytics, tokenize
from collections import Counter

ALLOWED_DOMAINS = ("ics.uci.edu", "cs.uci.edu", 
                   "informatics.uci.edu", "stat.uci.edu")

MAX_CONTENT_BYTES = 5 * 1024 * 1024   # skip pages larger than 5 MB

MIN_WORDS = 50                        # fewer words = low information page
LARGE_PAGE_BYTES = 1024 * 1024        # a 1 MB+ page with little text is junk
LARGE_PAGE_MIN_WORDS = 500

MAX_URL_LENGTH = 250
MAX_PATH_DEPTH = 12

analytics = Analytics()
atexit.register(analytics.flush)

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    if resp is None or resp.status != 200:
        return []
    raw = resp.raw_response
    if raw is None or not raw.content:
        return []
    if len(raw.content) > MAX_CONTENT_BYTES:
        return []

    # skip non-HTML content types when the header is present
    ctype = (getattr(raw, "headers", None) or {}).get("Content-Type", "")
    if ctype and "html" not in ctype.lower():
        return []

    final_url = urldefrag(raw.url or url)[0]
    try:
        soup = BeautifulSoup(raw.content, "lxml")
    except Exception:
        return []

    # collect links before stripping tags from the soup
    links = _collect_links(soup, final_url)

    # visible text only: drop scripts/styles so code is not counted as words
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    tokens = tokenize(soup.get_text(" ", strip=True))

    # record the page for the report (unique by defragmented URL)
    if not analytics.record_page(final_url, tokens):
        return []     # already processed (e.g. reached through a redirect)

    # low information value: too few words, or a big file with little text.
    # the page is still recorded above, but we don't follow its links.
    if len(tokens) < MIN_WORDS:
        return []
    if len(raw.content) > LARGE_PAGE_BYTES and len(tokens) < LARGE_PAGE_MIN_WORDS:
        return []

    return links

def _collect_links(soup, base_url):
    # resolve every <a href> against base_url, defragment, de-duplicate
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.lower().startswith(("mailto:", "javascript:", 
                                                "tel:", "data:")):
            continue
        try:
            absolute = urldefrag(urljoin(base_url, href))[0]
        except ValueError:
            continue
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        # must receive plain ASCII URLs 
        if not url.isascii() or any(c.isspace() for c in url):
            return False
        if len(url) > MAX_URL_LENGTH:
            return False
        
        
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False

        host = (parsed.hostname or "").lower()
        if not any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS):
            return False

        # trap checks before the return
        path = parsed.path.lower()

        # A segment repeated 3+ times, or a repeating pattern, is a loop
        # (typically a relative link that keeps appending to the path).
        segments = [s for s in path.split("/") if s]
        if segments and max(Counter(segments).values()) >= 3:
            return False
        if re.search(r"(/[^/]+?)\1{2,}", path):
            return False

        if len(segments) > MAX_PATH_DEPTH:
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", path)

    except (TypeError, ValueError):
        return False
