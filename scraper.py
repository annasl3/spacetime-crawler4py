import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup

ALLOWED_DOMAINS = ("ics.uci.edu", "cs.uci.edu", 
                   "informatics.uci.edu", "stat.uci.edu")

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
    if resp is None or resp.status != 200 or resp.raw_response is None:
        return []

    base = urldefrag(resp.raw_response.url or url)[0]
    soup = BeautifulSoup(resp.raw_response.content, "lxml")
    return _collect_links(soup, base)

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
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False

        host = (parsed.hostname or "").lower()
        if not any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS):
            return False

        # trap checks before the return
        
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except (TypeError, ValueError):
        return False
