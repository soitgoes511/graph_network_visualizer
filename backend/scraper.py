import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def get_domain(url):
    return urlparse(url).netloc

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

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

    start_domain = get_domain(start_url)

    while queue:
        current_url, depth = queue.pop(0)
        
        if current_url in visited:
            continue
        visited.add(current_url)
        
        try:
            headers = {
                'User-Agent': 'GraphNetworkVisualizer/1.0 (typical-student-project; +http://localhost)'
            }
            if logger: logger(f"Scraping: {current_url}")
            response = requests.get(current_url, headers=headers, timeout=5)
            if response.status_code != 200:
                if logger: logger(f"Failed to fetch {current_url}: Status {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.title.string if soup.title else current_url
            
            # Extract main text
            # Simple heuristic: join all p tags
            paragraphs = soup.find_all('p')
            text_content = "\\n".join([p.get_text() for p in paragraphs])
            
            if current_url not in node_ids:
                nodes.append({
                    "id": current_url, 
                    "title": title, 
                    "type": "web",
                    "text": text_content[:50000] # Limit text size to avoid memory issues
                })
                node_ids.add(current_url)

            if depth < max_depth:
                links_found = 0
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(current_url, href)
                    
                    if not is_valid_url(full_url):
                        continue
                        
                    # Filter to stay within domain or allow all? 
                    # User said "traverse all of the links within the wiki". Usually implies internal links.
                    # But graph might be interesting with external too. 
                    # Let's stick to same domain for now to avoid exploding graph.
                    if get_domain(full_url) == start_domain:
                        links.append({"source": current_url, "target": full_url})
                        if full_url not in visited:
                             queue.append((full_url, depth + 1))
                        links_found += 1
                    else:
                        # Add external link as a node but don't crawl it
                        if full_url not in node_ids:
                             nodes.append({"id": full_url, "title": full_url, "type": "external"})
                             node_ids.add(full_url)
                        links.append({"source": current_url, "target": full_url})
                        links_found += 1
                
                if logger: logger(f"Found {links_found} links on {current_url}")

        except Exception as e:
            if logger: logger(f"Error scraping {current_url}: {e}")
            print(f"Error scraping {current_url}: {e}")
            continue
    
    if logger: logger(f"Scrape complete. Total nodes: {len(nodes)}, Total links: {len(links)}")
    return {"nodes": nodes, "links": links}
