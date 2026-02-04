"""
JSON extraction utilities for handling LLM responses.
Handles responses that may contain markdown fences, explanatory text, or other formatting.
"""

import json
import re
from typing import Any, Optional
from rich.console import Console

console = Console()


def extract_json_from_response(response_text: str, strict: bool = False) -> Optional[dict]:
    """
    Extract JSON from LLM response that may contain markdown fences or explanatory text.

    Tries multiple strategies in order:
    1. Direct JSON parsing (if already clean)
    2. Extract from markdown code fences (```json ... ``` or ``` ... ```)
    3. Find JSON object in text (between { and })
    4. Find JSON array in text (between [ and ])

    Args:
        response_text: Raw response from LLM
        strict: If True, only attempts direct parsing and fence extraction

    Returns:
        Parsed JSON object/array, or None if extraction fails
    """
    if not response_text or not response_text.strip():
        return None

    # Strategy 1: Try direct parsing
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code fences
    # Try ```json ... ```
    json_fence_pattern = r'```json\s*(.*?)\s*```'
    match = re.search(json_fence_pattern, response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try ``` ... ``` (without language specifier)
    generic_fence_pattern = r'```\s*(.*?)\s*```'
    match = re.search(generic_fence_pattern, response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # If strict mode, stop here
    if strict:
        return None

    # Strategy 3: Find JSON object in text (between { and })
    # Look for the largest valid JSON object
    json_objects = []
    brace_count = 0
    start_idx = -1

    for i, char in enumerate(response_text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                potential_json = response_text[start_idx:i+1]
                try:
                    parsed = json.loads(potential_json)
                    json_objects.append((len(potential_json), parsed))
                except json.JSONDecodeError:
                    pass
                start_idx = -1

    if json_objects:
        # Return the largest valid JSON object
        json_objects.sort(key=lambda x: x[0], reverse=True)
        return json_objects[0][1]

    # Strategy 4: Find JSON array in text (between [ and ])
    json_arrays = []
    bracket_count = 0
    start_idx = -1

    for i, char in enumerate(response_text):
        if char == '[':
            if bracket_count == 0:
                start_idx = i
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0 and start_idx != -1:
                potential_json = response_text[start_idx:i+1]
                try:
                    parsed = json.loads(potential_json)
                    json_arrays.append((len(potential_json), parsed))
                except json.JSONDecodeError:
                    pass
                start_idx = -1

    if json_arrays:
        # Return the largest valid JSON array
        json_arrays.sort(key=lambda x: x[0], reverse=True)
        return json_arrays[0][1]

    # All strategies failed
    return None


def extract_json_with_fallback(
    response_text: str,
    fallback: Optional[dict] = None,
    log_failure: bool = True
) -> dict:
    """
    Extract JSON from response with fallback value.

    Args:
        response_text: Raw response from LLM
        fallback: Fallback value if extraction fails (default: empty dict)
        log_failure: Whether to log failure messages

    Returns:
        Parsed JSON or fallback value
    """
    if fallback is None:
        fallback = {}

    result = extract_json_from_response(response_text, strict=False)

    if result is None:
        if log_failure:
            console.print(f"[red]Failed to parse JSON from response[/red]")
            console.print(f"[dim]Raw (first 300 chars): {response_text[:300]}...[/dim]")
        return fallback

    return result


def clean_json_response(response_text: str) -> str:
    """
    Clean JSON response by removing markdown fences and explanatory text.
    Returns cleaned string that should be parseable as JSON.

    This is a simpler alternative that just cleans the text without parsing.
    Useful when you want to do custom parsing after cleaning.

    Args:
        response_text: Raw response from LLM

    Returns:
        Cleaned response text
    """
    cleaned = response_text.strip()

    # Remove markdown fences
    cleaned = re.sub(r'```json\s*', '', cleaned)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    cleaned = re.sub(r'^```\s*', '', cleaned)

    # Remove common explanatory prefixes
    explanatory_patterns = [
        r'^Here\'s the JSON:?\s*',
        r'^Here is the JSON:?\s*',
        r'^The JSON is:?\s*',
        r'^JSON:?\s*',
        r'^Response:?\s*',
    ]

    for pattern in explanatory_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

    return cleaned.strip()


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON with automatic extraction and fallback.

    Args:
        text: Text that may contain JSON
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    result = extract_json_from_response(text, strict=False)
    return result if result is not None else default
