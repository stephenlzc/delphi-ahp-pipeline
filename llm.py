"""
LLM API caller module.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional, Iterator


def call_llm(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str = "You are a professional research assistant specializing in Delphi method studies.",
    temperature: float = 0.7,
    timeout: int = 120,
) -> str:
    """
    Call LLM API with OpenAI-compatible format.

    Args:
        base_url: API base URL
        api_key: API key
        model: Model name
        prompt: User prompt
        system_prompt: System prompt
        temperature: Temperature setting
        timeout: Request timeout in seconds

    Returns:
        LLM response text
    """
    url = f"{base_url}/chat/completions"
    # Validate URL has a proper scheme
    if not base_url or not any(base_url.startswith(s) for s in ("http://", "https://")):
        raise LLMError(f"Invalid base_url: '{base_url}', please check the expert's API configuration (provider address)")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))

        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        elif "content" in result:
            return result["content"]
        else:
            return str(result)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        # Retry with temperature=1 if model only accepts 1
        if e.code == 400 and "temperature" in error_body.lower() and temperature != 1:
            data["temperature"] = 1
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    result = json.loads(response.read().decode('utf-8'))
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                elif "content" in result:
                    return result["content"]
                else:
                    return str(result)
            except Exception:
                pass  # Fall through to raise original error
        raise LLMHTTPError(f"HTTP {e.code}: {error_body[:500]}")
    except Exception as e:
        raise LLMError(f"LLM call failed: {str(e)}")


def call_llm_stream(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str = "You are a professional research assistant specializing in Delphi method studies.",
    temperature: float = 0.7,
    timeout: int = 120,
) -> Iterator[str]:
    """
    Call LLM API with streaming output (SSE).

    Args:
        base_url: API base URL
        api_key: API key
        model: Model name
        prompt: User prompt
        system_prompt: System prompt
        temperature: Temperature setting
        timeout: Request timeout in seconds

    Yields:
        Response text chunks as they arrive
    """
    import http.client
    import urllib.parse

    url = f"{base_url}/chat/completions"
    # Validate URL has a proper scheme
    if not base_url or not any(base_url.startswith(s) for s in ("http://", "https://")):
        raise LLMError(f"Invalid base_url: '{base_url}', please check the expert's API configuration (provider address)")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "stream": True,
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Read streaming response line by line
            full_content = ""
            for line in response:
                line = line.decode('utf-8').strip()
                if not line or line.startswith(':'):
                    continue
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices")
                        if not choices or not isinstance(choices, list):
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield content
                    except (json.JSONDecodeError, IndexError):
                        continue

            return full_content

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        # Retry with temperature=1 if model only accepts 1
        if e.code == 400 and "temperature" in error_body.lower() and temperature != 1:
            data["temperature"] = 1
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    full_content = ""
                    for line in response:
                        line = line.decode('utf-8').strip()
                        if not line or line.startswith(':'):
                            continue
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices")
                                if not choices or not isinstance(choices, list):
                                    continue
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    yield content
                            except (json.JSONDecodeError, IndexError):
                                continue
                    return full_content
            except Exception:
                pass  # Fall through to raise original error
        raise LLMHTTPError(f"HTTP {e.code}: {error_body[:500]}")
    except Exception as e:
        raise LLMError(f"LLM streaming call failed: {str(e)}")


def check_api_health(base_url: str, api_key: str, model: str = "gpt-3.5-turbo") -> dict:
    """
    Quick health check for API availability.

    Args:
        base_url: API base URL
        api_key: API key
        model: Model to test (optional)

    Returns:
        dict with status, latency, and error info
    """
    import time

    url = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    start = time.time()
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            latency = time.time() - start
            result = json.loads(response.read().decode('utf-8'))

            # Try to get available models
            models = result.get("data", []) if isinstance(result, dict) else []
            model_list = [m.get("id", "") for m in models if isinstance(m, dict)]

            return {
                "status": "ok",
                "latency_ms": round(latency * 1000, 1),
                "models_available": len(model_list),
                "model_list": model_list[:10],  # First 10 models
            }
    except Exception as e:
        latency = time.time() - start
        return {
            "status": "error",
            "latency_ms": round(latency * 1000, 1),
            "error": str(e),
        }


def parse_json_response(text: str) -> Optional[dict]:
    """
    Try to extract and parse JSON from LLM response.
    Handles truncated JSON by finding complete object boundaries.

    Args:
        text: LLM response text

    Returns:
        Parsed JSON dict or None if parsing failed
    """
    import re

    # Try to find JSON object - find first '{' and last '}'
    brace_start = text.find('{')
    if brace_start != -1:
        # Find the last '}' that could close this object
        # Search backwards from end to find the last complete bracket
        last_brace = -1
        for i in range(len(text) - 1, brace_start, -1):
            if text[i] == '}':
                last_brace = i
                break

        if last_brace > brace_start:
            # Try parsing the substring between braces
            json_str = text[brace_start:last_brace + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    # Try to find JSON array
    bracket_start = text.find('[')
    if bracket_start != -1:
        # Find the last ']' that could close this array
        last_bracket = -1
        for i in range(len(text) - 1, bracket_start, -1):
            if text[i] == ']':
                last_bracket = i
                break

        if last_bracket > bracket_start:
            json_str = text[bracket_start:last_bracket + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    # Fallback: try original regex for simple cases
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMHTTPError(LLMError):
    """HTTP error from LLM API."""
    pass
