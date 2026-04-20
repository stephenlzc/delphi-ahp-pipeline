"""
Checkpoint validation system for Delphi-AHP pipeline.

Each step validates the prerequisites from previous steps before execution.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)


class CheckpointError(Exception):
    """Raised when checkpoint validation fails."""
    pass


def load_state(run_dir: Path) -> dict:
    """Load pipeline state from run directory."""
    state_file = run_dir / "state.json"
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(run_dir: Path, state: dict):
    """Save pipeline state to run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)
    state_file = run_dir / "state.json"
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def validate_project_config(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate project configuration exists and is valid.

    Returns:
        Tuple of (is_valid, error_message)
    """
    project_file = run_dir / "project.json"
    if not project_file.exists():
        return False, "Project configuration file does not exist, please complete Step 1 first"

    try:
        with open(project_file, 'r', encoding='utf-8') as f:
            project = json.load(f)

        required_fields = ['title', 'framework', 'background', 'purpose']
        missing = [f for f in required_fields if not project.get(f)]
        if missing:
            return False, f"Project configuration missing required fields: {', '.join(missing)}"

        # Validate research_questions
        rq = project.get("research_questions", [])
        if not rq or len(rq) == 0:
            return False, "Research questions list cannot be empty, please complete Step 1 first"
        if len(rq) > 20:
            return False, f"Too many research questions ({len(rq)}), please reduce (recommended <=20)"

        return True, "OK"
    except json.JSONDecodeError as e:
        return False, f"Project configuration file format error: {e}"
    except Exception as e:
        return False, f"Failed to read project configuration: {e}"


def validate_api_providers(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate API providers are configured.

    Returns:
        Tuple of (is_valid, error_message)
    """
    providers_file = run_dir / "providers.json"
    if not providers_file.exists():
        return False, "API provider configuration does not exist, please complete Step 2 first"

    try:
        with open(providers_file, 'r', encoding='utf-8') as f:
            providers = json.load(f)

        # Check if at least one provider is configured
        if not providers or len(providers) == 0:
            return False, "No API providers configured, please complete Step 2 first"

        # Check each provider has required fields
        for key, p in providers.items():
            if not p.get("api_key"):
                return False, f"Provider {p.get('name', 'unknown')} missing API key"
            if not p.get("base_url"):
                return False, f"Provider {p.get('name', 'unknown')} missing API address"

        return True, "OK"
    except json.JSONDecodeError as e:
        return False, f"API provider configuration format error: {e}"
    except Exception as e:
        return False, f"Failed to read API configuration: {e}"


def validate_experts(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate experts are configured.

    Returns:
        Tuple of (is_valid, error_message)
    """
    experts_file = run_dir / "experts.json"
    if not experts_file.exists():
        return False, "Expert configuration does not exist, please complete Step 3 first"

    try:
        with open(experts_file, 'r', encoding='utf-8') as f:
            experts_data = json.load(f)

        # Handle both list format and dict format ({"experts": [...]})
        if isinstance(experts_data, list):
            experts_list = experts_data
        elif isinstance(experts_data, dict):
            experts_list = experts_data.get("experts", [])
        else:
            return False, "Expert configuration file format error"

        if not experts_list or len(experts_list) == 0:
            return False, "No experts configured, please complete Step 3 first"

        # Check for enabled experts
        enabled_experts = [e for e in experts_list if e.get("enabled", True)]
        if not enabled_experts:
            return False, "All experts have been disabled, please enable at least one expert"

        # Check for duplicate IDs
        expert_ids = [e.get("id") for e in experts_list if e.get("id")]
        if len(expert_ids) != len(set(expert_ids)):
            return False, "Duplicate expert IDs exist, please check configuration"

        # Check each expert has required fields
        for e in experts_list:
            if not e.get("name"):
                return False, f"Expert {e.get('id', 'unknown')} missing name"
            if not e.get("model"):
                return False, f"Expert {e.get('name', 'unknown')} did not select model"

        return True, f"OK ({len(enabled_experts)} experts)"
    except json.JSONDecodeError as e:
        return False, f"Expert configuration file format error: {e}"
    except Exception as e:
        return False, f"Failed to read expert configuration: {e}"


def validate_interview_framework(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate interview framework exists and has valid structure.

    Returns:
        Tuple of (is_valid, error_message)
    """
    framework_file = run_dir / "interview_framework.json"
    if not framework_file.exists():
        return False, "Interview framework does not exist, please complete Step 4 Part 1 first"

    try:
        with open(framework_file, 'r', encoding='utf-8') as f:
            framework = json.load(f)

        questions = framework.get("questions", [])
        if not questions or len(questions) == 0:
            return False, "Interview framework does not contain any questions"

        # Check for dimensions (dimension-based framework)
        dimensions = framework.get("dimensions", [])
        has_dimensions = dimensions and len(dimensions) > 0

        if has_dimensions:
            # Validate dimension structure
            for dim in dimensions:
                if not dim.get("name"):
                    return False, "Dimension missing name field"
                dim_questions = dim.get("questions", [])
                if not dim_questions or len(dim_questions) == 0:
                    return False, f"Dimension '{dim.get('name', 'unknown')}' does not contain any questions"
            return True, f"OK ({len(questions)} questions, {len(dimensions)} dimensions)"
        else:
            # No dimensions - old flat format, still valid
            return True, f"OK ({len(questions)} questions)"
    except json.JSONDecodeError as e:
        return False, f"Interview framework format error: {e}"
    except Exception as e:
        return False, f"Failed to read interview framework: {e}"


def validate_interview_records(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate interview records exist.

    Returns:
        Tuple of (is_valid, error_message)
    """
    records_file = run_dir / "interview_records.json"
    if not records_file.exists():
        return False, "Interview records do not exist, please complete Step 4 Part 2 first"

    try:
        with open(records_file, 'r', encoding='utf-8') as f:
            records = json.load(f)

        record_list = records.get("records", [])
        if not record_list:
            return False, "No interview records found"

        return True, f"OK ({len(record_list)} records)"
    except json.JSONDecodeError as e:
        return False, f"Interview records format error: {e}"
    except Exception as e:
        return False, f"Failed to read interview records: {e}"


def validate_ahp_hierarchy(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate AHP hierarchy exists.

    Returns:
        Tuple of (is_valid, error_message)
    """
    hierarchy_file = run_dir / "ahp_hierarchy.json"
    if not hierarchy_file.exists():
        return False, "AHP hierarchy does not exist, please complete Step 5 Part 2 first"

    try:
        with open(hierarchy_file, 'r', encoding='utf-8') as f:
            hierarchy = json.load(f)

        if not hierarchy.get("criteria_layer"):
            return False, "AHP hierarchy missing criteria layer"
        if not hierarchy.get("alternative_layer"):
            return False, "AHP hierarchy missing alternative layer"

        return True, "OK"
    except json.JSONDecodeError as e:
        return False, f"AHP hierarchy format error: {e}"
    except Exception as e:
        return False, f"Failed to read AHP hierarchy: {e}"


def validate_step5_outputs(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate all outputs from step 5 exist and have valid content.

    Returns:
        Tuple of (is_valid, error_message)
    """
    import json

    required_files = {
        "ahp_hierarchy.json": ["criteria", "alternatives"],
        "criteria_comparisons.json": None,  # Only check existence
        "alternative_scores.json": None,  # Only check existence
        "ahp_results.json": ["criteria", "weights"],
    }

    missing = []
    invalid = []
    for f, required_fields in required_files.items():
        file_path = run_dir / f
        if not file_path.exists():
            missing.append(f)
            continue
        # Validate content if required fields specified
        if required_fields:
            try:
                with open(file_path, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                for field in required_fields:
                    if field not in data:
                        invalid.append(f"{f} (missing {field})")
                        break
            except json.JSONDecodeError:
                invalid.append(f"{f} (JSON format error)")
            except Exception as e:
                invalid.append(f"{f} (read failed)")

    if missing:
        return False, f"Step 5 missing required files: {', '.join(missing)}"
    if invalid:
        return False, f"Step 5 file content invalid: {', '.join(invalid)}"

    return True, "OK"


def validate_rounds(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate rounds configuration exists.

    Returns:
        Tuple of (is_valid, error_message)
    """
    rounds_file = run_dir / "rounds.json"
    if not rounds_file.exists():
        return False, "Rounds configuration file does not exist, please complete Step 4 first"

    try:
        with open(rounds_file, 'r', encoding='utf-8') as f:
            rounds_data = json.load(f)
        if not isinstance(rounds_data, dict):
            return False, "Rounds configuration file format error"
        # Check for essential fields
        if "round_1" not in rounds_data:
            return False, "Rounds configuration missing round_1 field"
        return True, "OK"
    except json.JSONDecodeError:
        return False, "Rounds configuration file JSON format error"
    except Exception as e:
        return False, f"Failed to read rounds configuration: {e}"


def validate_convergence_check(run_dir: Path) -> Tuple[bool, str]:
    """
    Validate convergence check results exist and have valid content.

    Returns:
        Tuple of (is_valid, error_message)
    """
    convergence_file = run_dir / "convergence_check.json"
    if not convergence_file.exists():
        return False, "Convergence check results do not exist, please complete Step 6 first"

    # Validate content structure
    try:
        import json
        with open(convergence_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False, "Convergence check results format error"
        # Check for required fields
        if "convergence_results" not in data:
            return False, "Convergence check results missing convergence_results field"
        return True, "OK"
    except json.JSONDecodeError:
        return False, "Convergence check results JSON format error"
    except Exception as e:
        return False, f"Failed to read convergence check results: {e}"


STEP_PREREQUISITES: Dict[int, List[str]] = {
    # step: [required_check_functions]
    2: ["validate_project_config"],
    3: ["validate_project_config", "validate_api_providers"],
    4: ["validate_project_config", "validate_api_providers", "validate_experts"],
    5: ["validate_project_config", "validate_api_providers", "validate_experts", "validate_interview_framework", "validate_interview_records", "validate_rounds"],
    6: ["validate_project_config", "validate_api_providers", "validate_experts", "validate_interview_framework", "validate_interview_records", "validate_ahp_hierarchy", "validate_step5_outputs"],
    7: ["validate_convergence_check"],
    8: ["validate_step5_outputs"],
}


def validate_step_prerequisites(step: int, run_dir: Path) -> Tuple[bool, str]:
    """
    Validate all prerequisites for a given step.

    Args:
        step: The step number to validate prerequisites for
        run_dir: The run directory path

    Returns:
        Tuple of (all_valid, error_message)
    """
    prereqs = STEP_PREREQUISITES.get(step, [])

    if not prereqs:
        return True, "OK"

    error_messages = []
    for check_func_name in prereqs:
        check_func = globals().get(check_func_name)
        if check_func is None:
            error_messages.append(f"  - Check function does not exist: {check_func_name}")
            continue
        try:
            is_valid, msg = check_func(run_dir)
            if not is_valid:
                error_messages.append(f"  - {msg}")
        except Exception as e:
            error_messages.append(f"  - Check function execution failed: {check_func_name}: {e}")

    if error_messages:
        return False, "\n".join(error_messages)

    return True, "OK"


def print_checkpoint_status(step: int, run_dir: Path):
    """
    Print checkpoint status for a step.

    Args:
        step: The step number
        run_dir: The run directory path
    """
    print()
    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  [Checkpoint Validation] Step {step} Prerequisites Check{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")

    is_valid, msg = validate_step_prerequisites(step, run_dir)

    if is_valid:
        print(f"{Colors.GREEN}  ✓ Prerequisites validation passed{Colors.RESET}")
        print(f"  {msg}")
    else:
        print(f"{Colors.RED}  ✗ Prerequisites validation failed{Colors.RESET}")
        print(msg)
        print()
        print(f"{Colors.YELLOW}  Please return to the previous step to complete the required configuration.{Colors.RESET}")

    print()
    return is_valid


def interactive_checkpoint(step: int, run_dir: Path, resume_mode: bool = False) -> bool:
    """
    Interactive checkpoint that asks user to confirm before proceeding.

    Args:
        step: The step number
        run_dir: The run directory path
        resume_mode: If True, skip validation if files already exist (for resume)

    Returns:
        True if user wants to proceed, False otherwise
    """
    is_valid = print_checkpoint_status(step, run_dir)

    if not is_valid:
        print(f"{Colors.YELLOW}  Press Enter to return to previous step...{Colors.RESET}")
        input()
        return False

    # In resume mode, if validation passed, just proceed
    if resume_mode:
        print(f"  {Colors.GREEN}✓ Resume mode: prerequisites satisfied{Colors.RESET}")
        return True

    # Ask for confirmation
    print(f"  Confirm to start Step {step}?")
    response = input(f"  [{Colors.GREEN}Y{Colors.RESET}/{Colors.RED}n{Colors.RESET}](default Y): ").strip().upper()
    if response and response != 'Y' and response != 'YES':
        print(f"{Colors.YELLOW}  Cancelled{Colors.RESET}")
        return False

    return True
