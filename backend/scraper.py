import re
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

def get_domain(url):
    return urlparse(url).netloc

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def canonicalize_url(url: str) -> str:
    if not url:
        return url
    normalized, _fragment = urldefrag(url)
    return normalized


def extract_structured_text(soup: BeautifulSoup, limit: int = 50000) -> str:
    removable_tags = ["script", "style", "noscript", "svg", "img", "nav", "footer", "aside", "form"]
    for tag in soup.find_all(removable_tags):
        tag.decompose()

    container = soup.find("main") or soup.find("article") or soup.body or soup
    blocks = []
    seen = set()

    for element in container.find_all(["h1", "h2", "h3", "p", "li"], limit=2500):
        text = normalize_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if len(text) < 20 and element.name in {"p", "li"}:
            continue

        if element.name in {"h1", "h2", "h3"}:
            block = f"{element.name.upper()}: {text}"
        else:
            block = text

        if block in seen:
            continue
        seen.add(block)
        blocks.append(block)

    joined = "\n".join(blocks)
    return joined[:limit]

def scrape_url(start_url: str, max_depth: int = 1, logger=None):
    """
    Scrapes a URL recursively up to max_depth.
    Returns:
        nodes: list of {id: url, title: string, type: 'web'}
        links: list of {source: url, target: url}
    """
    if logger: logger(f"Starting scrape for {start_url} with depth {max_depth}")
    
    visited = set()
    nodes = []
    links = []
    queue = [(start_url, 0)]
    
    # Track nodes by ID to avoid duplicates in list
    node_ids = set()

    start_url = canonicalize_url(start_url)
    start_domain = get_domain(start_url)
    session = requests.Session()

    while queue:
        current_url, depth = queue.pop(0)
        current_url = canonicalize_url(current_url)
        
        if current_url in visited:
            continue
        visited.add(current_url)
        
        try:
            headers = {
                'User-Agent': 'GraphNetworkVisualizer/1.0 (typical-student-project; +http://localhost)'
            }
            if logger: logger(f"Scraping: {current_url}")
            response = session.get(current_url, headers=headers, timeout=10)
            if response.status_code != 200:
                if logger: logger(f"Failed to fetch {current_url}: Status {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            title = normalize_text(soup.title.string if soup.title else current_url)
            
            text_content = extract_structured_text(soup, limit=50000)
            
            if current_url not in node_ids:
                nodes.append({
                    "id": current_url, 
                    "title": title, 
                    "type": "web",
                    "text": text_content,
                    "text_length": len(text_content),
                    "source_domain": start_domain
                })
                node_ids.add(current_url)

            if depth < max_depth:
                links_found = 0
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = canonicalize_url(urljoin(current_url, href))
                    
                    if not is_valid_url(full_url):
                        continue

                    anchor_text = normalize_text(link.get_text(" ", strip=True))
                    link_payload = {
                        "source": current_url,
                        "target": full_url,
                        "weight": 1.0,
                        "confidence": 1.0,
                        "source_doc": current_url,
                        "anchor_text": anchor_text[:160],
                        "evidence_sentence": anchor_text[:240],
                    }
                        
                    # Filter to stay within domain or allow all? 
                    # User said "traverse all of the links within the wiki". Usually implies internal links.
                    # But graph might be interesting with external too. 
                    # Let's stick to same domain for now to avoid exploding graph.
                    if get_domain(full_url) == start_domain:
                        link_payload["relation_type"] = "LINKS_TO_INTERNAL"
                        links.append(link_payload)
                        if full_url not in visited:
                             queue.append((full_url, depth + 1))
                        links_found += 1
                    else:
                        # Add external link as a node but don't crawl it
                        if full_url not in node_ids:
                             nodes.append({"id": full_url, "title": full_url, "type": "external"})
                             node_ids.add(full_url)
                        link_payload["relation_type"] = "LINKS_TO_EXTERNAL"
                        links.append(link_payload)
                        links_found += 1
                
                if logger: logger(f"Found {links_found} links on {current_url}")

        except Exception as e:
            if logger: logger(f"Error scraping {current_url}: {e}")
            print(f"Error scraping {current_url}: {e}")
            continue
    
    session.close()
    if logger: logger(f"Scrape complete. Total nodes: {len(nodes)}, Total links: {len(links)}")
    return {"nodes": nodes, "links": links}
