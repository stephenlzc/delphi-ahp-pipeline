"""
Step 2: API Configuration
Supports multiple models per provider with health testing.
Models are fetched dynamically via GET /models when available.
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from providers import (
    PROVIDER_TEMPLATES, get_provider_display_name,
    get_special_model_params, is_reasoning_model, list_providers_by_category,
    get_static_fallback_models,
    CATEGORY_DOMESTIC, CATEGORY_INTERNATIONAL, CATEGORY_AGGREGATOR, CATEGORY_CUSTOM
)
from models import Provider
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white, gray,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)

import questionary


def interactive_select(title: str, items: List[str], multi_select: bool = False) -> List[int]:
    """
    Interactive selection function with arrow key navigation.

    Args:
        title: Selection title
        items: List of options
        multi_select: True=multi-select (Space to select), False=single select (Enter to confirm)

    Returns:
        List of selected indices
    """
    if not items:
        return []

    print(f"\n{Colors.BRIGHT_CYAN}{title}{Colors.RESET}")

    if multi_select:
        # Multi-select mode: use checkbox
        selected = questionary.checkbox(
            'Use arrow keys to move, Space to select, Enter to confirm',
            choices=items,
            validate=lambda s: len(s) > 0 or "Please select at least one item"
        ).ask()
        if selected is None:
            return []
        # Find indices of selected items
        return [items.index(s) for s in selected if s in items]
    else:
        # Single select mode: use select
        selected = questionary.select(
            'Use arrow keys to move, Enter to confirm',
            choices=items,
        ).ask()
        if selected is None:
            return []
        return [items.index(selected)]


def print_step_header():
    """Print step 2 header."""
    print()
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Step 2/8: API Configuration{Colors.RESET}")
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")
    print()


def ask(prompt: str, default: str = "") -> str:
    """Ask user for input."""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    return input(f"{prompt}: ").strip()


def ask_int(prompt: str, default: int, min_val: int = 0, max_val: int = 999) -> int:
    """Ask user for integer input."""
    while True:
        response = ask(prompt, str(default))
        try:
            value = int(response)
            if min_val <= value <= max_val:
                return value
            print(f"{Colors.RED}Please enter a number between {min_val} and {max_val}{Colors.RESET}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number{Colors.RESET}")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask yes/no question with validation."""
    choices = "[Y/n]" if default else "[y/N]"
    default_hint = "(default Y)" if default else "(default n)"

    while True:
        response = ask(f"{prompt} {choices}{default_hint}", "Y" if default else "n")
        if not response:
            return default
        if response.upper() in ("Y", "YES"):
            return True
        if response.upper() in ("N", "NO"):
            return False
        print(f"  {Colors.RED}Error: Invalid input '{response}', please enter Y or N{Colors.RESET}")


def save_json(filepath: Path, data: dict):
    """Save JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{Colors.GREEN}  ✓ Saved: {filepath}{Colors.RESET}")


# ============================================================
# Display Functions
# ============================================================

def display_provider_overview(providers: Dict[str, Provider]):
    """Display configured providers overview table"""
    print(f"\n{Colors.BRIGHT_YELLOW}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}  Configured API Providers{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}{'=' * 70}{Colors.RESET}")

    if not providers:
        print(f"\n{Colors.YELLOW}  No providers configured yet{Colors.RESET}")
    else:
        print(f"\n{Colors.CYAN}  ┌────┬──────────────────────────┬──────────────────┬──────────────┐{Colors.RESET}")
        print(f"  {Colors.CYAN}│ #  │ Provider                  │ Enabled Models   │ Actions      │{Colors.RESET}")
        print(f"  {Colors.CYAN}├────┼──────────────────────────┼──────────────────┼──────────────┤{Colors.RESET}")

        for i, (key, p) in enumerate(providers.items(), 1):
            # Calculate number of enabled models
            enabled_count = len(p.models)

            # Display enabled model names (max 3)
            if p.models:
                model_preview = ", ".join(p.models[:3])
                if len(p.models) > 3:
                    model_preview += f"..."
            else:
                model_preview = "-"

            print(f"  {Colors.CYAN}│{Colors.RESET} {i:>2} {Colors.CYAN}│{Colors.RESET} {Colors.BRIGHT_CYAN}{p.name:<24}{Colors.RESET} {Colors.CYAN}│{Colors.RESET} {Colors.WHITE}{model_preview:<16}{Colors.RESET} {Colors.CYAN}│{Colors.RESET} {Colors.YELLOW}[Edit]{Colors.RESET} {Colors.RED}[Delete]{Colors.RESET} {Colors.CYAN}│{Colors.RESET}")

        print(f"  {Colors.CYAN}└────┴──────────────────────────┴──────────────────┴──────────────┘{Colors.RESET}")

    print(f"{Colors.BRIGHT_YELLOW}{'=' * 70}{Colors.RESET}")


def display_provider_menu():
    """Display available provider menu (sorted by name A-Z), returns list of selected provider keys"""
    print(f"\n{Colors.BRIGHT_CYAN}Select provider to add:{Colors.RESET}")
    print()

    # Build flat list of (name, key) and sort by name (A-Z)
    all_providers = [(template["name"], key) for key, template in PROVIDER_TEMPLATES.items()]
    all_providers.sort(key=lambda x: x[0])  # Sort by name

    display_items = [name for name, key in all_providers]
    provider_list = [key for name, key in all_providers]

    selected_indices = interactive_select(
        "Select Provider:",
        display_items,
        multi_select=False
    )

    if not selected_indices:
        return []

    return [provider_list[i] for i in selected_indices]


# ============================================================
# API Operation Functions
# ============================================================

def fetch_models_from_api(base_url: str, api_key: str) -> Tuple[list, dict]:
    """
    Fetch available model list from API.

    Returns:
        (models_list, error_info)
        - models_list: List of model IDs on success
        - error_info: Error info dict or None
    """
    try:
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))

        models = []
        if "data" in result:
            for item in result.get("data", []):
                if "id" in item:
                    models.append(item["id"])

        return models, None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')[:500] if e.fp else ""

        # 401 authentication error
        if e.code == 401:
            return [], {"type": "auth_error", "code": e.code, "message": "API Key is invalid", "detail": error_body}

        # 404 not supported
        if e.code == 404:
            return [], {"type": "not_found", "code": e.code, "message": "/models endpoint not supported in this version", "detail": error_body}

        return [], {"type": "http_error", "code": e.code, "message": f"HTTP {e.code}", "detail": error_body}

    except Exception as e:
        return [], {"type": "network_error", "message": str(e)}


def test_model_chat(base_url: str, api_key: str, model: str, adapter: str = "openai_chat_compatible") -> dict:
    """
    Test single model's chat endpoint.

    Returns:
        dict with keys: status, response_model, content, reasoning, finish_reason, notes
    """
    special_params = get_special_model_params(model)
    is_reasoning = is_reasoning_model(model)

    # Set parameters
    max_tokens = special_params.get("max_tokens", 256) if is_reasoning else 64
    temperature = special_params.get("temperature", 0)

    chat_url = f"{base_url}/chat/completions"
    chat_data = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(
            chat_url,
            data=json.dumps(chat_data).encode('utf-8'),
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        status = 200
        response_model = result.get("model", model)
        choices = result.get("choices", [])

        content = ""
        reasoning = ""
        finish_reason = ""

        if choices:
            choice = choices[0]
            finish_reason = choice.get("finish_reason", "")

            # OpenAI format
            message = choice.get("message", {})
            content = message.get("content", "")

            # reasoning_content (some models)
            if "reasoning_content" in message:
                reasoning = message.get("reasoning_content", "")

        # Check content
        notes = ""
        if not content and (finish_reason == "length" or reasoning):
            notes = "reasoning model, content may be empty"

        return {
            "status": status,
            "response_model": response_model,
            "content": content,
            "reasoning": reasoning,
            "finish_reason": finish_reason,
            "notes": notes
        }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')[:500] if e.fp else ""

        # 400 parameter error - possibly temperature issue
        if e.code == 400:
            error_str = error_body.lower()
            if "temperature" in error_str:
                # Retry with temperature=1
                return test_model_with_params(base_url, api_key, model, adapter, temperature=1, max_tokens=256)

            return {
                "status": "param_error",
                "response_model": model,
                "content": "",
                "reasoning": "",
                "finish_reason": "",
                "notes": f"Parameter error: {error_body[:100]}"
            }

        if e.code == 401:
            return {
                "status": "auth_error",
                "response_model": model,
                "content": "",
                "reasoning": "",
                "finish_reason": "",
                "notes": "Authentication failed, please check API Key"
            }

        return {
            "status": "http_error",
            "response_model": model,
            "content": "",
            "reasoning": "",
            "finish_reason": "",
            "notes": f"HTTP {e.code}: {error_body[:100]}"
        }

    except Exception as e:
        error_str = str(e).lower()
        if "timeout" in error_str or "timed out" in error_str:
            return {
                "status": "timeout",
                "response_model": model,
                "content": "",
                "reasoning": "",
                "finish_reason": "",
                "notes": "Connection timeout"
            }

        return {
            "status": "error",
            "response_model": model,
            "content": "",
            "reasoning": "",
            "finish_reason": "",
            "notes": f"Error: {str(e)[:100]}"
        }


def test_model_with_params(base_url: str, api_key: str, model: str, adapter: str, temperature: int, max_tokens: int) -> dict:
    """Test model with specified parameters"""
    chat_url = f"{base_url}/chat/completions"
    chat_data = {
        "model": model,
        "messages": [{"role": "user", "content": "This is a test message. Please reply with exactly: pong"}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(
            chat_url,
            data=json.dumps(chat_data).encode('utf-8'),
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        choices = result.get("choices", [])
        content = ""
        reasoning = ""
        finish_reason = ""

        if choices:
            choice = choices[0]
            finish_reason = choice.get("finish_reason", "")
            message = choice.get("message", {})
            content = message.get("content", "")
            if "reasoning_content" in message:
                reasoning = message.get("reasoning_content", "")

        return {
            "status": 200,
            "response_model": result.get("model", model),
            "content": content,
            "reasoning": reasoning,
            "finish_reason": finish_reason,
            "notes": f"Retry with t={temperature} succeeded" if temperature != 0 else ""
        }

    except Exception as e:
        return {
            "status": "error",
            "response_model": model,
            "content": "",
            "reasoning": "",
            "finish_reason": "",
            "notes": f"Retry failed: {str(e)[:100]}"
        }


def test_model_max_tokens(base_url: str, api_key: str, model: str, adapter: str = "openai_chat_compatible") -> int:
    """
    Test model's maximum output token capability.

    Test order: 8192 → 4096 → 2048 → 1024 → 512
    Returns the maximum supported token count.

    Returns:
        int: Maximum supported tokens, returns 0 on failure
    """
    test_tokens = [8192, 4096, 2048, 1024, 512]

    for max_tokens in test_tokens:
        result = test_model_with_params(
            base_url=base_url,
            api_key=api_key,
            model=model,
            adapter=adapter,
            temperature=0,
            max_tokens=max_tokens
        )
        if result["status"] == 200:
            # Check if content was actually retrieved or just truncated
            content = result.get("content", "")
            finish_reason = result.get("finish_reason", "")

            # If finish_reason is length, it means the limit was reached
            if finish_reason == "length" and not content:
                # No content but finish_reason is length, meaning the limit was indeed reached
                continue
            # Successfully got content, or has content and not length (meaning this max_tokens works)
            return max_tokens

    # All tests failed
    return 0


def get_max_tokens_label(max_tokens: int) -> tuple:
    """
    Return label and color based on max_tokens.

    Returns:
        tuple: (label text, color code)
    """
    if max_tokens >= 4096:
        return "✓ Recommended", Colors.GREEN
    elif max_tokens >= 2048:
        return "⚠ May truncate", Colors.YELLOW
    elif max_tokens > 0:
        return "✗ Not suitable", Colors.RED
    else:
        return "✗ Test failed", Colors.RED


# ============================================================
# Add Provider Flow
# ============================================================

def add_provider(existing: Optional[Provider] = None) -> Optional[Provider]:
    """Add new provider configuration or edit existing provider configuration"""
    # Step 1: Select provider (skip in edit mode)
    print()
    if existing is not None:
        # Edit mode: use existing configuration
        provider_key = existing.key
        template = PROVIDER_TEMPLATES.get(provider_key, {
            "name": existing.name,
            "base_url": existing.base_url,
            "adapter": existing.adapter,
            "category": CATEGORY_CUSTOM,
        })
        print(f"{Colors.BLUE}Editing: {existing.name}{Colors.RESET}")
    else:
        selected_keys = display_provider_menu()
        if not selected_keys:
            print(f"\n  {Colors.YELLOW}[Cancelled]{Colors.RESET}")
            return None
        provider_key = selected_keys[0]
        template = PROVIDER_TEMPLATES[provider_key]

        print(f"\n{Colors.BRIGHT_GREEN}Selected: {template['name']}{Colors.RESET}")

    # Step 2: Enter API Key
    print(f"\n{Colors.BRIGHT_RED}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.RED}  Step 1: Enter API Key{Colors.RESET}")
    print(f"{Colors.BRIGHT_RED}{'='*60}{Colors.RESET}")
    print(f"{Colors.YELLOW}  Note: API Key will not be saved in code, only in local config{Colors.RESET}")

    if existing is not None:
        default_key = existing.api_key
        print(f"  Current: {Colors.CYAN}{'*' * len(default_key)}{Colors.RESET}")
        new_key = ask("  Enter new API Key (press Enter to keep unchanged)")
        api_key = new_key if new_key.strip() else default_key
    else:
        api_key = ask("  API Key (required)")
        while not api_key:
            print(f"  {Colors.RED}[Error] API Key cannot be empty{Colors.RESET}")
            api_key = ask("  API Key (required)")

    # Check if it's a URL instead of a real key
    if api_key.startswith("http://") or api_key.startswith("https://"):
        print(f"\n  {Colors.YELLOW}[Warning] The API Key you entered looks like a URL, not a key{Colors.RESET}")
        print(f"  {Colors.YELLOW}Please confirm your API Key is correct. If Base URL was entered in the Key field,{Colors.RESET}")
        print(f"  {Colors.YELLOW}please correct it in the next step.{Colors.RESET}")

    print(f"  {Colors.GREEN}✓ API Key entered{Colors.RESET}")

    # Step 1.5: Custom provider name (only allowed for new providers)
    custom_name = template.get("name", "")
    if (template["category"] == CATEGORY_CUSTOM or "custom_" in provider_key) and existing is None:
        print(f"\n{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}  Step 1.5: Set Provider Display Name{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")
        print(f"  Current Name: {Colors.CYAN}{custom_name}{Colors.RESET}")
        new_name = ask("  Enter custom provider name (press Enter to keep default)")
        if new_name.strip():
            template = dict(template)
            template["name"] = new_name.strip()
            print(f"  {Colors.GREEN}✓ Name updated: {new_name.strip()}{Colors.RESET}")

    # Step 2: Configure Base URL (custom providers need to input)
    print(f"\n{Colors.BRIGHT_BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  Step 2: Confirm API Address{Colors.RESET}")
    print(f"{Colors.BRIGHT_BLUE}{'='*60}{Colors.RESET}")

    default_base_url = template["base_url"]

    if template["category"] == CATEGORY_CUSTOM or not default_base_url:
        if existing is not None:
            print(f"  Current: {Colors.CYAN}{existing.base_url}{Colors.RESET}")
        print(f"  {Colors.YELLOW}Please enter API Base URL:{Colors.RESET}")
        base_url = ask("  API Base URL (e.g., https://api.example.com/v1)")
        while not base_url:
            print(f"  {Colors.RED}[Error] API address cannot be empty{Colors.RESET}")
            base_url = ask("  API Base URL")
    else:
        print(f"  Default: {Colors.CYAN}{default_base_url}{Colors.RESET}")
        if existing is not None and existing.base_url != default_base_url:
            print(f"  Current: {Colors.CYAN}{existing.base_url}{Colors.RESET}")
            use_default = questionary.confirm("  Use default address", default=False).ask()
        else:
            use_default = questionary.confirm("  Use default address", default=True).ask()
        if use_default:
            base_url = default_base_url
        else:
            base_url = ask("  Enter custom API address")
            while not base_url:
                print(f"  {Colors.RED}[Error] API address cannot be empty{Colors.RESET}")
                base_url = ask("  Enter custom API address")

    print(f"  {Colors.GREEN}✓ API Address: {base_url}{Colors.RESET}")

    # Step 4: Fetch model list (dynamically)
    print(f"\n{Colors.BRIGHT_MAGENTA}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}  Step 3: Fetch Available Model List{Colors.RESET}")
    print(f"{Colors.BRIGHT_MAGENTA}{'='*60}{Colors.RESET}")

    print(f"\n  {Colors.CYAN}Fetching model list from API...{Colors.RESET}")

    models_result, error_info = fetch_models_from_api(base_url, api_key)

    available_models = []
    models_source = ""

    if error_info:
        if error_info["type"] == "auth_error":
            print(f"\n  {Colors.RED}[Error] Authentication failed!{Colors.RESET}")
            print(f"  {Colors.RED}Error: {error_info.get('message', 'Unknown')}{Colors.RESET}")
            print(f"  {Colors.YELLOW}Hint: If you see 'api key invalid', the key may be wrong or expired{Colors.RESET}")
            retry = questionary.confirm("\n  Reconfigure this provider", default=False).ask()
            if retry:
                return None
            return None

        elif error_info["type"] == "not_found":
            print(f"\n  {Colors.YELLOW}[Info] This API version does not support /models endpoint{Colors.RESET}")
            print(f"  {Colors.YELLOW}Will try to use static model list or let user input model names{Colors.RESET}")

            # Try to use static fallback
            static_models = get_static_fallback_models(provider_key)
            if static_models:
                print(f"  {Colors.CYAN}Available static model list ({len(static_models)}):{Colors.RESET}")
                for m in static_models:
                    print(f"    - {m}")
                available_models = static_models
                models_source = "Static list"
            else:
                print(f"  {Colors.YELLOW}No static model list available{Colors.RESET}")
                # Let user manually input model names
                print(f"\n  {Colors.CYAN}Please enter model names (1-4, separated by spaces):{Colors.RESET}")
                print(f"  {Colors.GRAY}  Example: gpt-4o claude-3.5-sonnet gemini-pro{Colors.RESET}")
                user_models = ask("  Model names (space separated)")
                if user_models.strip():
                    available_models = user_models.strip().split()
                    available_models = [m.strip() for m in available_models if m.strip()]
                    models_source = "User input"
                    print(f"  {Colors.GREEN}✓ Entered {len(available_models)} models: {', '.join(available_models)}{Colors.RESET}")
                else:
                    models_source = "None"

        else:
            print(f"\n  {Colors.YELLOW}[Warning] Failed to fetch model list: {error_info.get('message', 'Unknown')}{Colors.RESET}")
            static_models = get_static_fallback_models(provider_key)
            if static_models:
                available_models = static_models
                models_source = "Static list (API failed)"
            else:
                # Let user manually input model names
                print(f"  {Colors.CYAN}Please enter model names (1-4, separated by spaces):{Colors.RESET}")
                user_models = ask("  Model names (space separated)")
                if user_models.strip():
                    available_models = user_models.strip().split()
                    available_models = [m.strip() for m in available_models if m.strip()]
                    models_source = "User input"
                    print(f"  {Colors.GREEN}✓ Entered {len(available_models)} models: {', '.join(available_models)}{Colors.RESET}")
                else:
                    models_source = "None"
    else:
        print(f"\n  {Colors.GREEN}✓ Successfully fetched {len(models_result)} models{Colors.RESET}")
        available_models = models_result
        models_source = "API dynamic fetch"

        if len(models_result) > 50:
            print(f"  {Colors.CYAN}Model list (first 30):{Colors.RESET}")
            for m in models_result[:30]:
                print(f"    - {m}")
            print(f"  {Colors.YELLOW}... and {len(models_result) - 30} more models{Colors.RESET}")
            print(f"\n  {Colors.CYAN}Hint: You can select all or part of the models for testing{Colors.RESET}")
        elif len(models_result) > 0:
            print(f"  {Colors.CYAN}Available models:{Colors.RESET}")
            for m in models_result:
                print(f"    - {m}")

    # For providers that don't support /models (like MiniMax), let user input models to test
    if not available_models and provider_key == "minimax":
        print(f"\n  {Colors.YELLOW}MiniMax does not support /models endpoint{Colors.RESET}")
        print(f"  {Colors.CYAN}Please enter model names you want to test (comma separated):{Colors.RESET}")
        print(f"  {Colors.CYAN}Or press Enter to use default list{Colors.RESET}")

        default_minimax_models = get_static_fallback_models("minimax")
        print(f"  Default models: {', '.join(default_minimax_models)}")

        user_input = ask("  Enter model names (or press Enter for default)")
        if user_input.strip():
            available_models = [m.strip() for m in user_input.split(",") if m.strip()]
            models_source = "User input"
        else:
            available_models = default_minimax_models
            models_source = "Default list"

    print(f"\n  {Colors.GREEN}Model source: {models_source}{Colors.RESET}")
    print(f"  {Colors.GREEN}Available models: {len(available_models)}{Colors.RESET}")

    # Step 5: Select models to test
    print(f"\n{Colors.BRIGHT_GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}  Step 4: Select Models to Test{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}{'='*60}{Colors.RESET}")

    if len(available_models) == 0:
        print(f"\n  {Colors.RED}[Error] No available models to select{Colors.RESET}")
        retry = questionary.confirm("\n  Reconfigure this provider", default=False).ask()
        if retry:
            return None
        return None

    # Use numeric selection (multi-select)
    print(f"\n{Colors.BRIGHT_GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}  Step 4: Select Models to Test{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{len(available_models)} models available{Colors.RESET}\n")

    selected_indices = interactive_select(
        f"Select models to test ({len(available_models)} total):",
        available_models,
        multi_select=True
    )

    while not selected_indices:
        print(f"  {Colors.RED}[Error] At least 1 model must be selected{Colors.RESET}")
        selected_indices = interactive_select(
            f"Select models to test ({len(available_models)} total):",
            available_models,
            multi_select=True
        )

    selected_models = [available_models[i] for i in selected_indices]
    print(f"\n  {Colors.GREEN}✓ Selected {len(selected_models)} models for testing{Colors.RESET}")

    # Step 6: Test selected models
    print(f"\n{Colors.BRIGHT_YELLOW}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}  Step 5: Test Model Connectivity{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}{'='*60}{Colors.RESET}")

    print(f"\n{Colors.CYAN}Testing {len(selected_models)} models...{Colors.RESET}")
    print(f"{Colors.YELLOW}Note: reasoning models may return empty content, this is normal{Colors.RESET}\n")

    test_results = {}
    tested_models = []

    for model in selected_models:
        print(f"  {Colors.CYAN}Testing {model}...{Colors.RESET}", end=" ", flush=True)

        result = test_model_chat(base_url, api_key, model, template["adapter"])

        if result["status"] == "timeout":
            print(f"{Colors.YELLOW}Timeout, retrying...{Colors.RESET}", end=" ", flush=True)
            time.sleep(1)
            result = test_model_chat(base_url, api_key, model, template["adapter"])

        test_results[model] = result

        if result["status"] == 200:
            status_icon = f"{Colors.GREEN}✓{Colors.RESET}"
            status_text = "Pass"
            if result.get("content") == "pong":
                print(f"{status_icon} {status_text} | content: pong")
            elif result.get("notes"):
                print(f"{status_icon} {status_text} | {result['notes']}")
            else:
                print(f"{status_icon} {status_text}")
        elif result["status"] == "auth_error":
            print(f"{Colors.RED}✗ Auth failed{Colors.RESET}")
        elif result["status"] == "timeout":
            print(f"{Colors.YELLOW}✗ Timeout{Colors.RESET}")
        elif result["status"] == "param_error":
            print(f"{Colors.RED}✗ Param error{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ {result.get('notes', 'Failed')}{Colors.RESET}")

        tested_models.append((model, result))

    # Display test results summary
    print(f"\n{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Model Test Results Summary{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")
    print(f"\n{Colors.CYAN}┌────┬────────────────────────────────────────┬────────┬──────────┐{Colors.RESET}")
    print(f"  {Colors.CYAN}│ #  │ Model                                  │ Status │ Content  │{Colors.RESET}")
    print(f"  {Colors.CYAN}├────┼────────────────────────────────────────┼────────┼──────────┤{Colors.RESET}")

    for i, (model, result) in enumerate(tested_models, 1):
        status = result.get("status", "unknown")
        content = result.get("content", "")
        if content and len(content) > 15:
            content = content[:15] + "..."

        if status == 200:
            status_str = f"{Colors.GREEN}✓ Pass{Colors.RESET}"
        elif status == "timeout":
            status_str = f"{Colors.YELLOW}Timeout{Colors.RESET}"
        elif status == "auth_error":
            status_str = f"{Colors.RED}Auth failed{Colors.RESET}"
        elif status == "param_error":
            status_str = f"{Colors.RED}Param error{Colors.RESET}"
        else:
            status_str = f"{Colors.RED}Failed{Colors.RESET}"

        print(f"  {Colors.CYAN}│{Colors.RESET} {i:>2} {Colors.CYAN}│{Colors.RESET} {model:<40} {Colors.CYAN}│{Colors.RESET} {status_str:<10} {Colors.CYAN}│{Colors.RESET} {(content or '-'):<10} {Colors.CYAN}│{Colors.RESET}")

    print(f"  {Colors.CYAN}└────┴────────────────────────────────────────┴────────┴──────────┘{Colors.RESET}")

    # Filter passing models
    passed_models = [model for model, result in tested_models if result["status"] == 200]

    if not passed_models:
        print(f"\n  {Colors.RED}[Error] All model tests failed!{Colors.RESET}")
        print(f"  {Colors.YELLOW}Please check API Key and network connection and retry{Colors.RESET}")
        retry = questionary.confirm("\n  Reconfigure this provider", default=False).ask()
        if retry:
            return None
        return None

    print(f"\n  {Colors.GREEN}✓ {len(passed_models)}/{len(selected_models)} models passed{Colors.RESET}")

    # Step 6b: Test each model's max_tokens capability
    print(f"\n{Colors.BRIGHT_YELLOW}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}  Step 5b: Test Model Output Capability (max_tokens){Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}{'='*60}{Colors.RESET}")

    model_max_tokens = {}
    print(f"\n{Colors.CYAN}Testing each model's maximum output capability...{Colors.RESET}")
    print(f"{Colors.YELLOW}Test order: 8192 → 4096 → 2048 → 1024 → 512{Colors.RESET}\n")

    for model in passed_models:
        print(f"  {Colors.CYAN}Testing {model}...{Colors.RESET}", end=" ", flush=True)
        max_tokens = test_model_max_tokens(base_url, api_key, model, template["adapter"])
        model_max_tokens[model] = max_tokens
        label, color = get_max_tokens_label(max_tokens)
        print(f"{color}{max_tokens} tokens{Colors.RESET} | {color}{label}{Colors.RESET}")

    # Display summary
    print(f"\n{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Model Output Capability Summary{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")
    print(f"\n{Colors.CYAN}┌────┬────────────────────────────────────────┬──────────┬────────────┐{Colors.RESET}")
    print(f"  {Colors.CYAN}│ #  │ Model                                  │ max_tokens │ Label      │{Colors.RESET}")
    print(f"  {Colors.CYAN}├────┼────────────────────────────────────────┼──────────┼────────────┤{Colors.RESET}")

    for i, model in enumerate(passed_models, 1):
        max_tokens = model_max_tokens.get(model, 0)
        label, color = get_max_tokens_label(max_tokens)
        print(f"  {Colors.CYAN}│{Colors.RESET} {i:>2} {Colors.CYAN}│{Colors.RESET} {model:<40} {Colors.CYAN}│{Colors.RESET} {max_tokens:<10} {Colors.CYAN}│{color}{label:<12}{Colors.RESET} {Colors.CYAN}│{Colors.RESET}")

    print(f"  {Colors.CYAN}└────┴────────────────────────────────────────┴──────────┴────────────┘{Colors.RESET}")

    # Step 7: Select default model
    print(f"\n{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Step 6: Select Default Model{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")

    print(f"\n{Colors.YELLOW}Select default model from passing models:{Colors.RESET}")
    for i, m in enumerate(passed_models, 1):
        marker = " *" if i == 1 else ""
        print(f"  {i}. {m}{marker}")

    default_model = questionary.select(
        "Select default model",
        choices=passed_models,
    ).ask()
    if default_model is None:
        print(f"  {Colors.YELLOW}[Cancelled] Using first model as default{Colors.RESET}")
        default_model = passed_models[0] if passed_models else ""
    print(f"  {Colors.GREEN}✓ Default model: {default_model}{Colors.RESET}")

    # Create Provider
    provider = Provider(
        key=provider_key,
        name=template["name"],
        adapter=template["adapter"],
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
        models=passed_models,  # Only save models that passed testing
        model_capabilities=model_max_tokens,  # Save max output capability for each model
    )

    print(f"\n{Colors.GREEN}{Colors.BOLD}  ✓ {provider.name} configuration complete!{Colors.RESET}")
    print(f"  {Colors.CYAN}Enabled models: {len(passed_models)}{Colors.RESET}")
    print(f"  {Colors.CYAN}Default model: {default_model}{Colors.RESET}")

    # Display output capability summary
    suitable = [m for m, t in model_max_tokens.items() if t >= 2048]
    print(f"  {Colors.CYAN}Suitable for deep interviews: {len(suitable)}{Colors.RESET}")

    return provider


def remove_provider(providers: Dict[str, Provider]) -> Dict[str, Provider]:
    """Remove provider"""
    if not providers:
        print(f"\n  {Colors.YELLOW}[Info] No providers configured yet{Colors.RESET}")
        return providers

    print(f"\n{Colors.RED}Select provider to remove:{Colors.RESET}")
    provider_names = [providers[key].name for key in providers.keys()]
    removed_name = questionary.select(
        "Select provider to remove",
        choices=provider_names,
    ).ask()
    if removed_name:
        removed_key = [k for k, v in providers.items() if v.name == removed_name][0]
        del providers[removed_key]
        print(f"  {Colors.RED}✓ Removed: {removed_name}{Colors.RESET}")
    return providers


def quick_adjust_models(providers: Dict[str, Provider]) -> Dict[str, Provider]:
    """
    Quickly adjust provider's model configuration.

    Allows user to:
    1. Select a provider
    2. View current models and default model
    3. Change the default model
    4. Add or remove models from the enabled list
    """
    if not providers:
        print(f"\n  {Colors.YELLOW}[Info] No providers configured yet{Colors.RESET}")
        return providers

    print(f"\n{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Quick Model Adjustment{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")

    # Step 1: Select provider to adjust
    print(f"\n{Colors.YELLOW}Select provider to adjust:{Colors.RESET}")
    provider_names = [p.name for p in providers.values()]
    selected_name = questionary.select(
        "Select provider",
        choices=provider_names,
    ).ask()
    if not selected_name:
        print(f"  {Colors.YELLOW}[Cancelled]{Colors.RESET}")
        return providers

    # Find the corresponding Provider object
    selected_key = None
    selected_provider = None
    for k, p in providers.items():
        if p.name == selected_name:
            selected_key = k
            selected_provider = p
            break

    if not selected_provider:
        print(f"  {Colors.RED}[Error] Provider not found{Colors.RESET}")
        return providers

    print(f"\n{Colors.BRIGHT_GREEN}Selected: {selected_provider.name}{Colors.RESET}")
    print(f"  Current default model: {Colors.CYAN}{selected_provider.default_model}{Colors.RESET}")
    print(f"  Current enabled models: {len(selected_provider.models)}{Colors.RESET}")

    # Step 2: Select action
    print(f"\n{Colors.BOLD}Select action:{Colors.RESET}")
    action = questionary.select(
        "Select action",
        choices=[
            "Change default model",
            "Add models to enabled list",
            "Remove models from enabled list",
            "Return"
        ],
    ).ask()

    if action == "Change default model":
        if not selected_provider.models:
            print(f"  {Colors.YELLOW}[Info] No available models, please add models first{Colors.RESET}")
            return providers

        print(f"\n{Colors.CYAN}Select new default model:{Colors.RESET}")
        new_default = questionary.select(
            "Select default model",
            choices=selected_provider.models,
        ).ask()
        if new_default:
            selected_provider.default_model = new_default
            print(f"  {Colors.GREEN}✓ Default model changed to: {new_default}{Colors.RESET}")

    elif action == "Add models to enabled list":
        print(f"\n{Colors.CYAN}Enter model names to add (comma separated for multiple):{Colors.RESET}")
        print(f"{Colors.YELLOW}Hint: Enter full model name, e.g., deepseek-chat{Colors.RESET}")
        user_input = ask("  Enter model names")
        if user_input.strip():
            new_models = [m.strip() for m in user_input.split(",") if m.strip()]
            added_count = 0
            for m in new_models:
                if m not in selected_provider.models:
                    selected_provider.models.append(m)
                    added_count += 1
            print(f"  {Colors.GREEN}✓ Added {added_count} models{Colors.RESET}")
            # If no default model set, automatically set to first
            if not selected_provider.default_model and selected_provider.models:
                selected_provider.default_model = selected_provider.models[0]
                print(f"  {Colors.CYAN}Auto set default model to: {selected_provider.default_model}{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}[Cancelled]{Colors.RESET}")

    elif action == "Remove models from enabled list":
        if len(selected_provider.models) <= 1:
            print(f"  {Colors.YELLOW}[Info] At least 1 model must be kept, cannot remove{Colors.RESET}")
            return providers

        print(f"\n{Colors.RED}Select model to remove:{Colors.RESET}")
        model_to_remove = questionary.select(
            "Select model to remove",
            choices=selected_provider.models,
        ).ask()
        if model_to_remove:
            if model_to_remove == selected_provider.default_model:
                print(f"  {Colors.YELLOW}[Info] Cannot remove default model, please change default model first{Colors.RESET}")
            else:
                selected_provider.models.remove(model_to_remove)
                print(f"  {Colors.GREEN}✓ Removed: {model_to_remove}{Colors.RESET}")

    else:
        print(f"  {Colors.YELLOW}[Cancelled]{Colors.RESET}")
        return providers

    # Update providers dict
    providers[selected_key] = selected_provider

    print(f"\n{Colors.BRIGHT_GREEN}Updated configuration:{Colors.RESET}")
    print(f"  Provider: {selected_provider.name}")
    print(f"  Default model: {Colors.CYAN}{selected_provider.default_model}{Colors.RESET}")
    print(f"  Enabled models ({len(selected_provider.models)}): {', '.join(selected_provider.models[:5])}")
    if len(selected_provider.models) > 5:
        print(f"    ... and {len(selected_provider.models) - 5} more models")

    return providers


# ============================================================
# Main Flow
# ============================================================

def run_step2(state: dict) -> dict:
    """
    Run step 2: API configuration.
    """
    print_step_header()

    print(f"{Colors.WHITE}Please configure available LLM providers (at least 1 required):{Colors.RESET}")
    print(f"{Colors.YELLOW}Hint: One provider can enable multiple models, model lists are fetched dynamically via API{Colors.RESET}")
    print()

    providers: Dict[str, Provider] = {}

    while True:
        display_provider_overview(providers)

        print(f"\n{Colors.BOLD}Action Options:{Colors.RESET}")
        if providers:
            print(f"  {Colors.GREEN}1{Colors.RESET}. {Colors.GREEN}Add Provider{Colors.RESET}")
            print(f"  {Colors.YELLOW}2{Colors.RESET}. {Colors.YELLOW}Quick Model Adjustment{Colors.RESET}")
            print(f"  {Colors.RED}3{Colors.RESET}. {Colors.RED}Remove Existing Provider{Colors.RESET}")
            print(f"  {Colors.BRIGHT_CYAN}4{Colors.RESET}. {Colors.BRIGHT_CYAN}Continue to Next Step (at least 1 required){Colors.RESET}")
            menu_options = ["Add Provider", "Quick Model Adjustment", "Remove Existing Provider", "Continue to Next Step (at least 1 required)"]
        else:
            print(f"  {Colors.GREEN}1{Colors.RESET}. {Colors.GREEN}Add Provider{Colors.RESET}")
            print(f"  {Colors.BRIGHT_CYAN}2{Colors.RESET}. {Colors.BRIGHT_CYAN}Continue to Next Step (at least 1 required){Colors.RESET}")
            menu_options = ["Add Provider", "Continue to Next Step (at least 1 required)"]

        selected = questionary.select(
            "Select Action",
            choices=menu_options,
        ).ask()

        if selected == "Add Provider" or selected is None:
            provider = add_provider()
            if provider is not None:
                providers[provider.key] = provider
            else:
                print(f"\n  {Colors.YELLOW}[Cancelled] Please reconfigure{Colors.RESET}")

        elif selected == "Quick Model Adjustment":
            providers = quick_adjust_models(providers)

        elif selected == "Remove Existing Provider":
            providers = remove_provider(providers)

        elif selected == "Continue to Next Step (at least 1 required)":
            if not providers:
                print(f"\n{Colors.RED}No providers configured, please add at least one provider first{Colors.RESET}")
                continue
            break

    # Review and confirmation section (yellow box)
    while True:
        if not providers:
            print(f"\n{Colors.RED}No providers configured, cannot continue{Colors.RESET}")
            return run_step2(state)
        content_lines = []
        provider_keys = list(providers.keys())
        for i, key in enumerate(provider_keys, 1):
            p = providers[key]
            content_lines.append(f"{Colors.BRIGHT_YELLOW}{i}. {p.name}{Colors.RESET}")
            content_lines.append(f"   Address: {Colors.CYAN}{p.base_url}{Colors.RESET}")
            models_preview = ', '.join(p.models[:5]) if len(p.models) <= 5 else ', '.join(p.models[:5]) + "..."
            content_lines.append(f"   Enabled Models ({len(p.models)}): {Colors.GREEN}{models_preview}{Colors.RESET}")
            content_lines.append(f"   Default Model: {Colors.BRIGHT_GREEN}{p.default_model}{Colors.RESET}")
            content_lines.append("")  # Empty line separator

        # Print yellow box
        box_width = 70
        print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}       Please Review Your API Configuration       {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")

        for line in content_lines:
            if line == "":
                print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}   {Colors.BRIGHT_YELLOW}║{Colors.RESET}")
                continue
            padding = box_width - len(line) - 4
            if padding < 0:
                padding = 0
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}  Select Action:{Colors.RESET}{' ' * (box_width - 18)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")

        if providers:
            # With providers: 4 options
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm and continue{Colors.RESET}{' ' * (box_width - 30)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.YELLOW}  2{Colors.RESET} - {Colors.YELLOW}Add more providers{Colors.RESET}{' ' * (box_width - 28)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BLUE}  3{Colors.RESET} - {Colors.BLUE}Edit existing provider{Colors.RESET}{' ' * (box_width - 30)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.RED}  4{Colors.RESET} - {Colors.RED}Delete existing provider{Colors.RESET}{' ' * (box_width - 32)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
            print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")
            max_choice = 4
        else:
            # Without providers: only 2 options
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm and continue{Colors.RESET}{' ' * (box_width - 30)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.YELLOW}  2{Colors.RESET} - {Colors.YELLOW}Add more providers{Colors.RESET}{' ' * (box_width - 28)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
            print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")
            max_choice = 2

        if providers:
            confirm_choice_list = interactive_select("Select Action:", [
                "Confirm and continue",
                "Add more providers",
                "Edit existing provider",
                "Delete existing provider"
            ])
        else:
            confirm_choice_list = interactive_select("Select Action:", [
                "Confirm and continue",
                "Add more providers"
            ])
        confirm_choice = confirm_choice_list[0] + 1 if confirm_choice_list else 1

        if confirm_choice == 1:
            print(f"\n{Colors.GREEN}{Colors.BOLD}  ✓ Configuration confirmed, continuing...{Colors.RESET}")
            break

        elif confirm_choice == 2:
            # Add more providers
            provider = add_provider()
            if provider is not None:
                providers[provider.key] = provider
            else:
                print(f"\n  {Colors.YELLOW}[Cancelled]{Colors.RESET}")
            # Continue loop to show updated list

        elif confirm_choice == 3:
            # Edit existing provider
            if not providers:
                print(f"\n  {Colors.YELLOW}[Info] No providers configured yet{Colors.RESET}")
                continue
            provider_names = [p.name for p in providers.values()]
            print(f"\n{Colors.BLUE}Select provider to edit:{Colors.RESET}")
            selected = interactive_select("Select provider to edit:", provider_names, multi_select=False)
            if not selected:
                continue
            edit_name = provider_names[selected[0]]
            edit_key = list(providers.keys())[selected[0]]
            print(f"\n{Colors.BLUE}Reconfiguring: {edit_name}{Colors.RESET}")
            provider = add_provider(existing=providers[edit_key])
            if provider is not None:
                # Delete old key, add new (if key changed)
                if provider.key != edit_key:
                    del providers[edit_key]
                providers[provider.key] = provider
            # Continue loop to show updated list

        elif confirm_choice == 4:
            # Delete existing provider
            if not providers:
                print(f"\n  {Colors.YELLOW}[Info] No providers configured yet{Colors.RESET}")
                continue
            provider_names = [p.name for p in providers.values()]
            print(f"\n{Colors.RED}Select provider to delete:{Colors.RESET}")
            selected = interactive_select("Select provider to delete:", provider_names, multi_select=False)
            if not selected:
                continue
            del_name = provider_names[selected[0]]
            del_key = list(providers.keys())[selected[0]]
            del providers[del_key]
            print(f"  {Colors.RED}✓ Deleted: {del_name}{Colors.RESET}")
            # Continue loop to show updated list
            if not providers:
                print(f"  {Colors.YELLOW}[Info] No providers left, please add at least 1{Colors.RESET}")

    state["providers"] = providers

    # Save to run directory
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / state.get("run_id", "")))
    save_json(run_dir / "providers.json", {k: v.to_dict() for k, v in providers.items()})

    print(f"\n{Colors.BRIGHT_GREEN}API Configuration Saved!{Colors.RESET}")

    return state
