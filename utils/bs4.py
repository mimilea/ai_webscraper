"""
This module contains utilities for using BeautifulSoup to parse HTML content.
"""

# =====
# SETUP
# =====
# The code below will help to set up the rest of the module.

# General imports
import re
from typing import Optional
import logging
from urllib.parse import urljoin, urldefrag, urlparse
from collections import defaultdict

# Third-party imports
from bs4 import BeautifulSoup
from bs4.element import NavigableString

# Local imports
from .miscellaneous import truncate_string

# Set up the logger
logger = logging.getLogger(__name__)

# =====
# UTILS
# =====


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Resolves a URL against an optional base, removes fragments, and normalizes
    trailing slashes.

    Args:
        url (str): The URL to normalize.
        base_url (Optional[str]): The base URL to resolve relative URLs against.

    Returns:
        str: The normalized URL.
    """
    if base_url:
        # Resolve relative URLs
        resolved_url = urljoin(base_url, url)
    else:
        resolved_url = url

    # Remove fragment
    defragged_url, _ = urldefrag(resolved_url)

    # Normalize by removing trailing slash from path, but not from root
    parsed_url = urlparse(defragged_url)
    if parsed_url.path.endswith("/") and parsed_url.path != "/":
        normalized = defragged_url[:-1]
    else:
        normalized = defragged_url

    return normalized


def clean_raw_html(
    html_content: str,
    base_url: str,
    preserve_links: bool = True,
    max_chars: Optional[int] = None,
) -> str:
    """
    Parse HTML content with BeautifulSoup and clean it.

    Args:
        html_content (str): Raw HTML content to clean
        base_url (str): Base URL for making relative URLs absolute
        preserve_links (bool): Whether to preserve link information in the cleaned text

    Returns:
        str: Cleaned text content from the page
    """
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    if preserve_links:
        # Convert links to a readable format that preserves URL information
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True)
            href = link.get("href")

            # Make relative URLs absolute
            if href.startswith("/"):
                href = urljoin(base_url, href)
            elif not href.startswith(("http://", "https://")):
                href = urljoin(base_url, href)

            # Replace the link with readable text that includes the URL
            link.replace_with(f"{link_text} [URL: {href}]")

    # Get the text content (now with URL information preserved if requested)
    text_content = soup.get_text()

    # Clean up the text - normalize whitespace and remove empty lines
    lines = (line.strip() for line in text_content.splitlines())
    cleaned_text = "\n".join(line for line in lines if line)

    # If a maximum number of characters is specified, then we'll truncate the text
    if max_chars is not None:
        cleaned_text = truncate_string(cleaned_text, max_chars)

    # Log the result
    pct_reduction = (
        1 - len(cleaned_text) / len(html_content) if len(html_content) > 0 else 0
    )
    logger.debug(
        f"Cleaned HTML content from {base_url}; {len(cleaned_text):,} characters ({pct_reduction:.2%} reduction)"
    )

    return cleaned_text


def get_interactive_elements_html(
    html_content: str,
    base_url: str,
    max_chars: Optional[int] = None,
) -> str:
    """
    Cleans HTML by preserving only interactive and heading elements, while stripping
    away most of the text content from other elements. This creates a "structural"
    view of the page, useful for LLMs to analyze page layout without being
    overwhelmed by text.

    Args:
        html_content (str): Raw HTML content to clean
        base_url (str): Base URL for logging purposes
        max_chars (Optional[int]): The maximum number of characters to allow in the page content.

    Returns:
        str: Cleaned HTML with only interactive elements and structure.
    """
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script, style, and other non-content-related elements
    for element in soup(["script", "style", "meta", "link", "svg", "path"]):
        element.decompose()

    # Define tags where we want to preserve the text content
    preserve_text_tags = {
        "a",
        "button",
        "input",
        "select",
        "option",
        "label",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "title",
        "span",  # Spans are often used inside buttons or for icons
    }

    # Iterate over all tags and clear text from non-essential ones
    for tag in soup.find_all(True):
        if tag.name not in preserve_text_tags:
            # We replace the direct text contents with an empty string
            for content in tag.contents:
                if isinstance(content, NavigableString) and content.strip():
                    content.replace_with(" ")

    # Get the text content of the modified soup
    cleaned_html = str(soup.prettify())

    # If a maximum number of characters is specified, then we'll truncate the text
    if max_chars is not None:
        cleaned_html = truncate_string(cleaned_html, max_chars)

    # Log the result
    pct_reduction = (
        1 - len(cleaned_html) / len(html_content) if len(html_content) > 0 else 0
    )
    logger.debug(
        f"Cleaned HTML for interactive elements from {base_url}; {len(cleaned_html):,} characters ({pct_reduction:.2%} reduction)"
    )

    return cleaned_html


def find_pagination_candidates(html_content: str, max_candidates: int = 5) -> list[str]:
    """
    Analyzes raw HTML to find and extract candidate snippets that are likely
    to be pagination controls. It uses a series of heuristics to identify
    potential pagination elements and their containers.

    This function is designed to be comprehensive for arbitrary web pages and
    efficient by returning only small, relevant HTML snippets.

    Args:
        html_content (str): The raw HTML content of the page.
        max_candidates (int): The maximum number of candidate snippets to return.

    Returns:
        list[str]: A list of HTML snippets (as strings), each representing a
                   potential pagination control.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # --- Heuristics to find potential pagination elements ---

    # 1. Keywords in class, id, or ARIA labels. This is the most common pattern.
    keyword_selectors = [
        '[class*="pagination"]',
        '[id*="pagination"]',
        '[class*="pager"]',
        '[id*="pager"]',
        '[class*="pages"]',
        '[id*="pages"]',
        '[aria-label*="pagination"]',
        '[role="navigation"]',
    ]

    # 2. "Next" / "Previous" / "More" buttons or links.
    next_prev_texts = re.compile(
        r"next|previous|prev|back|more|older|newer|continuar|siguiente|anterior", re.I
    )
    next_prev_symbols = ["»", "›", ">", "→", "«", "‹", "<", "←"]

    # 3. Structural patterns: Look for navigation elements with lists of links.
    structural_selectors = ["nav ul li a"]

    # 4. "Load more" buttons, a common alternative to classic pagination.
    load_more_selectors = [
        'button:-soup-contains("Load more")',
        'button:-soup-contains("Show more")',
        'a:-soup-contains("Load more")',
        'a:-soup-contains("Show more")',
    ]

    candidate_elements = set()

    # --- Gather all potential elements based on heuristics ---

    # Heuristic 1 & 3: Find elements using CSS selectors
    all_selectors = keyword_selectors + structural_selectors + load_more_selectors
    for selector in all_selectors:
        try:
            elements = soup.select(selector)
            for el in elements:
                candidate_elements.add(el)
        except Exception:
            # The :-soup-contains selector might fail in some cases
            continue

    # Heuristic 2: Find links/buttons by text or content
    interactive_tags = soup.find_all(["a", "button"])
    for tag in interactive_tags:
        # Check text content
        if tag.string and (
            next_prev_texts.search(tag.string)
            or tag.string.strip() in next_prev_symbols
        ):
            candidate_elements.add(tag)
        # Check aria-label
        elif tag.get("aria-label") and next_prev_texts.search(tag.get("aria-label")):
            candidate_elements.add(tag)
        # Check for number-only content (a strong signal in a list)
        elif tag.string and tag.string.strip().isdigit():
            candidate_elements.add(tag)

    # --- Consolidate candidates into parent containers ---

    candidate_containers = set()
    for element in candidate_elements:
        # Travel up the DOM to find the most likely container
        # We're looking for a container that groups multiple pagination-like elements
        container = element
        for _ in range(5):  # Limit search depth to 5 parents
            parent = container.find_parent()
            if not parent:
                break

            # A good container often has a role of "navigation" or a relevant class name.
            parent_class = parent.get("class", "")
            parent_id = parent.get("id", "")
            parent_role = parent.get("role", "")

            if (
                any(
                    keyword in " ".join(parent_class).lower()
                    for keyword in ["pagination", "pager"]
                )
                or any(
                    keyword in parent_id.lower() for keyword in ["pagination", "pager"]
                )
                or parent_role == "navigation"
            ):
                container = parent
                break  # Found a great container, stop searching up

            container = parent

        candidate_containers.add(container)

    # --- Filter out redundant or nested containers ---

    # If one container is a child of another, we only want the parent.
    final_containers = []
    sorted_containers = sorted(list(candidate_containers), key=lambda x: len(str(x)))

    for container in sorted_containers:
        is_redundant = False
        for existing_container in final_containers:
            if container in existing_container.find_all(True):
                is_redundant = True
                break
        if not is_redundant:
            final_containers.append(container)

    # --- Generate clean snippets from the final containers ---

    html_snippets = []
    # Preserve text for these tags to give context to the LLM
    preserve_text_tags = {"a", "button", "span", "option", "label"}

    for container in final_containers[:max_candidates]:
        # Create a deep copy to avoid modifying the original soup
        snippet_soup = BeautifulSoup(str(container), "html.parser")

        for tag in snippet_soup.find_all(True):
            # Clean non-essential text but keep structure
            if tag.name not in preserve_text_tags:
                for content in tag.contents:
                    if isinstance(content, NavigableString) and content.strip():
                        content.replace_with(" ")

        html_snippets.append(str(snippet_soup.prettify()))

    return html_snippets


def find_cookie_consent_candidates(
    html_content: str, max_candidates: int = 5
) -> list[str]:
    """
    Analyzes raw HTML to find and extract candidate snippets that are likely
    to be cookie consent "accept" buttons or their containers. It uses a series of
    heuristics to identify potential cookie banners.

    This function is designed to be comprehensive for arbitrary web pages and
    efficient by returning only small, relevant HTML snippets.

    Args:
        html_content (str): The raw HTML content of the page.
        max_candidates (int): The maximum number of candidate snippets to return.

    Returns:
        list[str]: A list of HTML snippets (as strings), each representing a
                   potential cookie consent control area.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # --- Heuristics to find potential cookie consent elements ---

    # 1. Keywords in class, id, or other attributes.
    keyword_selectors = [
        '[class*="cookie"]',
        '[id*="cookie"]',
        '[class*="consent"]',
        '[id*="consent"]',
        '[class*="banner"]',
        '[id*="banner"]',
        '[class*="cmp"]',  # Consent Management Platform
        '[id*="cmp"]',
        '[class*="dialog"]',
        '[id*="dialog"]',
        '[aria-label*="cookie"]',
        '[aria-label*="consent"]',
        '[aria-labelledby*="cookie"]',
        '[aria-describedby*="cookie"]',
        '[aria-labelledby*="consent"]',
        '[aria-describedby*="consent"]',
        # Common providers
        '[id*="onetrust"]',
        '[class*="onetrust"]',
        '[id*="cookiebot"]',
        '[class*="cookiebot"]',
    ]

    # 2. Text content indicating acceptance.
    accept_texts = re.compile(
        r"\\b(accept|agree|allow|ok|got it|i understand|continue to site|ja|akzeptieren|zustimmen|einverstanden|acepto|aceptar)\\b",
        re.I,
    )

    # 3. ARIA roles for dialogs which are often used for cookie banners.
    role_selectors = [
        '[role="dialog"]',
        '[role="alertdialog"]',
    ]

    candidate_elements = set()

    # --- Gather all potential elements based on heuristics ---

    # Heuristic 1 & 3: Find elements using CSS selectors
    all_selectors = keyword_selectors + role_selectors
    for selector in all_selectors:
        try:
            elements = soup.select(selector)
            for el in elements:
                candidate_elements.add(el)
        except Exception as e:
            logger.warning(f"CSS selector '{selector}' failed: {e}")
            continue

    # Heuristic 2: Find links/buttons by text content
    interactive_tags = soup.find_all(["a", "button"])
    for tag in interactive_tags:
        # Check text content
        if tag.string and accept_texts.search(tag.string):
            candidate_elements.add(tag)
        # Check aria-label
        elif tag.get("aria-label") and accept_texts.search(tag.get("aria-label")):
            candidate_elements.add(tag)

    # --- Consolidate candidates into parent containers ---
    candidate_containers = set()
    for element in candidate_elements:
        # Travel up the DOM to find the most likely container
        container = element
        for _ in range(5):  # Limit search depth to 5 parents
            parent = container.find_parent()
            if not parent or parent.name in ["body", "html"]:
                break

            # A good container often has a role of "dialog" or a relevant class/id.
            parent_class = " ".join(parent.get("class", [])).lower()
            parent_id = parent.get("id", "").lower()
            parent_role = parent.get("role", "").lower()

            if (
                any(
                    kw in parent_class
                    for kw in ["cookie", "consent", "banner", "dialog", "cmp"]
                )
                or any(
                    kw in parent_id
                    for kw in ["cookie", "consent", "banner", "dialog", "cmp"]
                )
                or parent_role in ["dialog", "alertdialog"]
            ):
                container = parent
                break  # Found a great container, stop searching up

            container = parent

        candidate_containers.add(container)

    # --- Filter out redundant or nested containers ---
    # If one container is a child of another, we prefer the parent.
    final_containers = []
    # Sort by string length (desc) to process parents before children
    sorted_containers = sorted(
        list(candidate_containers), key=lambda x: len(str(x)), reverse=True
    )

    for container in sorted_containers:
        is_redundant = False
        for existing_container in final_containers:
            # Check if the current container is a descendant of one already added
            if container in existing_container.find_all(True):
                is_redundant = True
                break
        if not is_redundant:
            final_containers.append(container)

    # --- Generate clean snippets from the final containers ---
    html_snippets = []
    # Preserve text for these tags to give context to the LLM
    preserve_text_tags = {"a", "button", "span", "p", "h1", "h2", "h3", "label"}

    for container in final_containers[:max_candidates]:
        # Create a deep copy to avoid modifying the original soup
        snippet_soup = BeautifulSoup(str(container), "html.parser")

        for tag in snippet_soup.find_all(True):
            # Clean non-essential text but keep structure
            if tag.name not in preserve_text_tags:
                for content in tag.contents:
                    if isinstance(content, NavigableString) and content.strip():
                        content.replace_with(" ")

        html_snippets.append(str(snippet_soup.prettify(formatter="html5")))

    return html_snippets


def extract_links_with_text(
    html_content: str,
    base_url: str,
) -> list[dict]:
    """
    Extracts all links from the HTML content, resolving them to absolute URLs (with fragments removed),
    and collects their associated text (all descendant text nodes) and title attributes.

    Args:
        html_content (str): The raw HTML content of the page.
        base_url (str): The base URL to resolve relative links.

    Returns:
        list[dict]: A list of dictionaries, each with:
            - 'url': The resolved absolute URL (str, with fragment removed)
            - 'associated_texts': List of unique associated texts and titles (list[str])
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links_and_text = []

    # A set of domains/protocols to ignore, as they are not relevant for finding funding opportunities.
    ignored_patterns = [
        "javascript:",
        "mailto:",
        "tel:",
        # Social media
        "whatsapp.com",
        "twitter.com",
        "facebook.com",
        "linkedin.com",
        "instagram.com",
    ]

    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or any(pattern in href for pattern in ignored_patterns):
            continue

        normalized_link = normalize_url(url=href, base_url=base_url)

        # Concatenate all descendant text nodes
        text = " ".join(s.strip() for s in a.stripped_strings if s.strip())
        title = a.get("title", "").strip()
        # Collect both text and title if present
        texts = set()
        if text:
            texts.add(text)
        if title:
            texts.add(title)
        # If neither, add empty string to preserve the link
        if not texts:
            texts.add("")
        links_and_text.append((normalized_link, texts))

    link_to_texts = defaultdict(set)
    for link, texts in links_and_text:
        if link:
            link_to_texts[link].update(texts)

    # Convert to list of dicts
    result = [
        {"url": link, "associated_texts": list(texts), "found_on_url": base_url}
        for link, texts in link_to_texts.items()
    ]
    return result
