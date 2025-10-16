import asyncio
import aiohttp
import time
import os
from typing import Dict, Set, List, Optional
from urllib.parse import urlparse

from utils.bs4 import *


class AsyncWebRequestHandler:
    """Handles async web requests with configurable delay"""
    
    def __init__(self, delay: float = 1.0, max_concurrent: int = None, core_usage_percentage: float = 0.5):
        self.delay = delay
        self.last_request_time = 0
        # Use configured percentage of available cores if max_concurrent not specified
        if max_concurrent is None:
            max_concurrent = max(1, int(os.cpu_count() * core_usage_percentage))
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        
        print(f"Initialized async request handler with max {max_concurrent} concurrent requests")
        print(f"Using {core_usage_percentage*100:.0f}% of {os.cpu_count()} available CPU cores")
    
    async def __aenter__(self):
        """Async context manager entry"""
        # Configure connector with larger header limits and other settings
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Max connections per host
        )
        
        # Create session with custom timeout and header limits
        timeout = aiohttp.ClientTimeout(total=30)  # Increased timeout
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0'},
            max_line_size=16384,  # Increase max header line size
            max_field_size=16384,  # Increase max header field size
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get_content(self, url: str) -> Optional[str]:
        """Get content from URL with delay and concurrency control"""
        async with self.semaphore:  # Limit concurrent requests
            try:
                # Implement delay
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < self.delay:
                    await asyncio.sleep(self.delay - time_since_last)
                self.last_request_time = time.time()
                
                # Additional headers to appear more like a regular browser
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                async with self.session.get(
                    url, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    allow_redirects=True
                ) as response:
                    response.raise_for_status()
                    content = await response.read()
                    return content
                    
            except aiohttp.ClientError as e:
                print(f"Client error fetching {url}: {e}")
                return None
            except asyncio.TimeoutError:
                print(f"Timeout fetching {url}")
                return None
            except Exception as e:
                print(f"Unexpected error fetching {url}: {e}")
                return None


class AsyncDepthCrawler:
    """Async web crawler that crawls to a specified depth while avoiding URL collisions"""
    
    def __init__(self, max_depth: int = 4, request_handler: AsyncWebRequestHandler = None):
        self.max_depth = max_depth
        self.request_handler = request_handler
        self.visited_urls: Set[str] = set()
        self.all_links: Dict[str, dict] = {}
        
        print(f"Initialized crawler with max depth: {self.max_depth}")
    
    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain"""
        try:
            domain1 = urlparse(url1).netloc
            domain2 = urlparse(url2).netloc
            return domain1 == domain2
        except:
            return False
    
    async def process_url(self, url: str, current_depth: int, base_domain: str) -> List[str]:
        """Process a single URL and return extracted links for next depth level"""
        
        # Skip if URL is from different domain (optional constraint)
        if not self.is_same_domain(url, f"https://{base_domain}"):
            return []
        
        # Skip if already visited
        if url in self.visited_urls:
            return []
            
        # Mark as visited
        self.visited_urls.add(url)
        
        print(f"[Task] Crawling (depth {current_depth}): {url}")
        
        # Get page content
        content = await self.request_handler.get_content(url)
        if not content:
            return []
        
        next_level_urls = []
        
        # Extract links from this page
        try:
            extracted_links = extract_links_with_text(content, url)
            
            # Add links to our master dictionary (avoiding collisions)
            for link_data in extracted_links:
                link_url = link_data['url']
                if link_url not in self.all_links:
                    self.all_links[link_url] = {
                        'url': link_url,
                        'associated_texts': link_data['associated_texts'],
                        'found_on_urls': [link_data['found_on_url']],
                        'depth_found': current_depth
                    }
                else:
                    # Update existing entry with new source URL
                    if link_data['found_on_url'] not in self.all_links[link_url]['found_on_urls']:
                        self.all_links[link_url]['found_on_urls'].append(link_data['found_on_url'])
                
                # Collect URLs for next depth level
                if current_depth < self.max_depth - 1 and link_url not in self.visited_urls:
                    next_level_urls.append(link_url)
                        
        except Exception as e:
            print(f"Error processing {url}: {e}")
        
        return next_level_urls
    
    async def crawl_depth_level(self, urls: List[str], depth: int, base_domain: str) -> List[str]:
        """Crawl all URLs at a given depth level concurrently"""
        if not urls or depth >= self.max_depth:
            return []
        
        print(f"\nProcessing depth {depth} with {len(urls)} URLs...")
        
        # Process all URLs at this depth concurrently
        tasks = [self.process_url(url, depth, base_domain) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect next level URLs
        next_level_urls = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Task generated an exception: {result}")
            elif isinstance(result, list):
                next_level_urls.extend(result)
        
        # Remove duplicates while preserving order
        unique_next_urls = []
        seen = set()
        for url in next_level_urls:
            if url not in seen:
                seen.add(url)
                unique_next_urls.append(url)
        
        return unique_next_urls
    
    async def crawl(self, start_url: str) -> Dict[str, dict]:
        """Start crawling from the given URL using asyncio"""
        base_domain = urlparse(start_url).netloc
        
        current_urls = [start_url]
        current_depth = 0
        
        # Process URLs depth by depth
        while current_urls and current_depth < self.max_depth:
            current_urls = await self.crawl_depth_level(current_urls, current_depth, base_domain)
            current_depth += 1
        
        return self.all_links


# Main function to crawl a URL - this is the main interface
async def crawl_url_depth(
    url: str,
    max_depth: int = 4,
    request_delay: float = 1.0,
    core_usage_percentage: float = 0.5,
    verbose: bool = True
) -> Dict[str, dict]:
    """
    Crawl a URL to the specified depth and return all extracted links.
    
    Args:
        url (str): Starting URL to crawl
        max_depth (int): Maximum depth to crawl (0 = start page only)
        request_delay (float): Delay between requests in seconds
        core_usage_percentage (float): Percentage of CPU cores to use (0.1 to 1.0)
        verbose (bool): Whether to print progress information
    
    Returns:
        Dict[str, dict]: Dictionary of all extracted links with metadata
    """
    if verbose:
        print("=== ASYNC WEB CRAWLER ===")
        print(f"Target URL: {url}")
        print(f"Max crawl depth: {max_depth}")
        print(f"Core usage: {core_usage_percentage*100:.0f}% ({int(os.cpu_count() * core_usage_percentage)}/{os.cpu_count()} cores)")
        print(f"Request delay: {request_delay} seconds")
        print("=" * 25)
    
    # Create async request handler with configured settings
    async with AsyncWebRequestHandler(
        delay=request_delay,
        core_usage_percentage=core_usage_percentage
    ) as request_handler:
        
        # Create crawler with configured settings
        crawler = AsyncDepthCrawler(max_depth=max_depth, request_handler=request_handler)
        
        # Start crawling
        if verbose:
            print(f"\nStarting async crawl from {url} with max depth of {max_depth}...")
        
        all_extracted_links = await crawler.crawl(url)
        
        if verbose:
            print(f"\nCrawling complete! Found {len(all_extracted_links)} unique URLs")
        
        return all_extracted_links
