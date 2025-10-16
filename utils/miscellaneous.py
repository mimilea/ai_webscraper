"""
This module contains miscellaneous utility functions.
"""

# =====
# SETUP
# =====
# The code below will help to set up the rest of the module.

# General imports
import asyncio
import json
import hashlib
import time
import random
from typing import List, Optional, Union

# Third-party imports
from tqdm.asyncio import tqdm as atqdm

# ==================
# DEFINING FUNCTIONS
# ==================
# Below, we'll define a number of miscellaneous utility functions.


def truncate_string(string: str, max_chars: int) -> str:
    """
    Truncates a string to a maximum number of characters.

    Args:
        string (str): The string to truncate.
        max_chars (int): The maximum number of characters to allow in the string.

    Returns:
        str: The truncated string.
    """

    # If the string is already shorter than the maximum number of characters, then we'll return it as is
    if len(string) <= max_chars:
        return string

    # Otherwise, we'll truncate the string
    return string[:max_chars] + "...\n[TRUNCATED DUE TO LENGTH RESTRICTIONS]"


def random_wait(min_seconds: float = 1, max_seconds: float = 2) -> None:
    """
    Waits for a random amount of time between min_seconds and max_seconds.
    """
    time.sleep(random.uniform(min_seconds, max_seconds))


async def atqdm_gather(*fs, return_exceptions=False, max_concurrency=None, **kwargs):
    if max_concurrency is None:
        # Default behavior: gather all at once
        if not return_exceptions:
            return await atqdm.gather(*fs, **kwargs)

        async def wrap(f):
            try:
                return await f
            except Exception as e:
                return e

        return await atqdm.gather(*map(wrap, fs), **kwargs)

    # Limit concurrency
    semaphore = asyncio.Semaphore(max_concurrency)

    async def sem_task(f):
        async with semaphore:
            try:
                return await f
            except Exception as e:
                if return_exceptions:
                    return e
                raise

    return await atqdm.gather(*(sem_task(f) for f in fs), **kwargs)


def chunk_string(
    string: str,
    max_chars_per_chunk: int,
    chunk_overlap_in_chars: Optional[int] = None,
) -> List[str]:
    """
    Splits a string into chunks of a specified maximum size, with optional overlap.

    Args:
        string (str): The string to split.
        max_chars_per_chunk (int): The maximum number of characters per chunk.
        chunk_overlap_in_chars (Optional[int]): The number of characters to overlap
            between chunks. Defaults to None.

    Returns:
        List[str]: A list of string chunks.

    Raises:
        ValueError: If chunk_overlap_in_chars is greater than or equal to
            max_chars_per_chunk.
    """
    if chunk_overlap_in_chars is None:
        chunk_overlap_in_chars = 0

    if chunk_overlap_in_chars >= max_chars_per_chunk:
        raise ValueError("chunk_overlap_in_chars must be less than max_chars_per_chunk")

    chunks = []
    start_index = 0
    step = max_chars_per_chunk - chunk_overlap_in_chars
    while start_index < len(string):
        end_index = start_index + max_chars_per_chunk
        chunk_str = string[start_index:end_index]

        # Add a note to the beginning of the chunk if it's not the first chunk
        if start_index > 0:
            chunk_str = (
                "... [TRUNCATED EARLIER TEXT DUE TO LENGTH RESTRICTIONS]...\n"
                + chunk_str
            )

        # Add a note to the end of the chunk if it was truncated due to length restrictions
        if end_index < len(string):
            chunk_str += "... [TRUNCATED DUE TO LENGTH RESTRICTIONS]"
        chunks.append(chunk_str)
        start_index += step

    return chunks


def parse_json_response(response: str) -> Union[dict, list]:
    """
    Parses a JSON response from a string.
    """

    # Check if the string is a JSON code block (surrounded by ```json...```)
    if response.startswith("```json") and response.endswith("```"):
        response = response[len("```json") : -len("```")]

    # Check if the string is a code block (surrounded by ```...```)
    elif response.startswith("```") and response.endswith("```"):
        response = response[len("```") : -len("```")]

    # Try and parse the response as JSON
    return json.loads(response)


def hash_string(string: str, max_length: Optional[int] = 16) -> str:
    """
    Hashes a string using SHA-256.
    """
    hash_str = hashlib.sha256(string.encode("utf-8")).hexdigest()
    if max_length is not None:
        hash_str = hash_str[:max_length]
    return hash_str
