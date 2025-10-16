import asyncio
import json
import os

from crawlers.request_crawler import crawl_url_depth

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================
MAX_CRAWL_DEPTH = 2                    # Maximum depth to crawl (0 = start page only)
CORE_USAGE_PERCENTAGE = 0.5            # Percentage of CPU cores to use (0.1 to 1.0)
REQUEST_DELAY_SECONDS = 1.0            # Delay between requests in seconds
START_URL = "https://www.who.int/"     # Starting URL for crawling
# =============================================================================


# Async main function
async def main():
    """Main async function to run the crawler"""
    
    print("=== ASYNC WEB CRAWLER CONFIGURATION ===")
    print(f"Max crawl depth: {MAX_CRAWL_DEPTH}")
    print(f"Core usage: {CORE_USAGE_PERCENTAGE*100:.0f}% ({int(os.cpu_count() * CORE_USAGE_PERCENTAGE)}/{os.cpu_count()} cores)")
    print(f"Request delay: {REQUEST_DELAY_SECONDS} seconds")
    print(f"Start URL: {START_URL}")
    print("=" * 40)
    
    # Use the crawler function with configuration
    all_extracted_links = await crawl_url_depth(
        url=START_URL,
        max_depth=MAX_CRAWL_DEPTH,
        request_delay=REQUEST_DELAY_SECONDS,
        core_usage_percentage=CORE_USAGE_PERCENTAGE,
        verbose=True
    )
    
    # Print results
    print(f"\nFinal results: Found {len(all_extracted_links)} unique URLs")
    print("\nAll extracted links:")
    print(json.dumps(all_extracted_links, indent=2))


# Usage
if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())