#!/usr/bin/env python3
"""
Delphi-AHP Pipeline - Step-by-step CLI Application

This program guides users through 8 steps of the Delphi-AHP research process:
1. Project Setup - Enter research topic and background
2. API Configuration - Set up LLM provider
3. Expert Configuration - Define expert panel
4. Round Configuration - Set Delphi rounds
5. Execute Pipeline - Run the complete Delphi-AHP process
6. Delphi Results - View convergence results
7. AHP Results - View weights and consistency
8. Generate Report - Output final report

Usage:
    python3 app.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Import steps
from steps import (
    run_step1,
    run_step2,
    run_step3,
    run_step4,
    run_step5,
    run_step6,
    run_step7,
    run_step8,
)

# Import checkpoint system
from checkpoints import interactive_checkpoint, validate_step_prerequisites

# Import colors
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)

import questionary


# ============================================================
# Helper Functions
# ============================================================

def clear_screen():
    """Clear screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Print header"""
    clear_screen()
    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print()


def wait_enter():
    """Wait for user to press Enter to continue"""
    input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")


def save_state(state: dict, filepath: Path):
    """Save run state"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)


def load_state(filepath: Path) -> dict:
    """Load run state"""
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_run_dir(state: dict) -> Path:
    """
    Get the run directory path based on state.
    Directory format: run_result/run_<timestamp>_<title>/
    """
    base_dir = Path(__file__).parent / "run_result"
    run_id = state.get("run_id", "unknown")
    return base_dir / run_id


def get_timestamp() -> str:
    """Get local timezone timestamp"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def detect_run_progress(run_dir: Path) -> dict:
    """
    Detect run progress with Part-level granular resume support.

    Finds the first incomplete Part and returns (step, part), indicating
    that execution should restart from step.part.

    Returns:
        dict: {
            "step": int,        # Last completed step
            "part": int,        # First incomplete Part number (1-based); 0 if all complete
            "next_step": int,   # Next step to execute
            "next_part": int,   # Next Part to start from
            "completed": list,
            "dialogue_files": list,
            "total_dialogue_count": int,
        }
    """
    STEP_PART_FILES = {
        1: [["project.json"]],
        2: [["providers.json"]],
        3: [["experts.json"]],
        # Step 4: Actual file output order
        #   Part 1 (code Part 3): interview_framework.json
        #   Part 2 (code Part 4): interview_records.json + E*_dialogue_*.md
        #   Part 3 (code Part 5): rounds.json
        4: [
            ["interview_framework.json"],
            ["interview_records.json"],
            ["rounds.json"],
        ],
        5: [
            ["factor_coding.json"],
            ["ahp_hierarchy.json"],
            ["criteria_comparisons.json"],
            ["alternative_scores.json"],
            ["ahp_results.json"],
        ],
        6: [["convergence_check.json", "convergence_summary.md"]],
        7: [["sensitivity_analysis.json", "sensitivity_summary.md"]],
        8: [["final_report.md", "executive_summary.md", "interactive_report.html", "report_summary.json"]],
    }

    total_dialogue_count = 0
    experts_file = run_dir / "experts.json"
    if experts_file.exists():
        try:
            with open(experts_file, 'r', encoding='utf-8') as f:
                experts_data = json.load(f)
            if "experts" in experts_data:
                total_dialogue_count = len(experts_data["experts"])
        except Exception:
            pass

    dialogue_files = sorted(run_dir.glob("E*_dialogue_*.md"))
    dialogue_count = len(dialogue_files)

    for step, parts in STEP_PART_FILES.items():
        for part_idx, part_files in enumerate(parts, start=1):
            # Step 4 Part 2: dialogue files >= expert count means complete
            if step == 4 and part_idx == 2:
                if not (dialogue_count >= total_dialogue_count and total_dialogue_count > 0):
                    # Part 2 incomplete (insufficient dialogue files)
                    return _build_result(step, part_idx, STEP_PART_FILES, dialogue_files, dialogue_count, total_dialogue_count)
                # Part 2 complete, continue to next Part
                continue

            # Regular Part: all files must exist to be complete
            # As long as one file doesn't exist, this Part is the first incomplete, return immediately
            if not all((run_dir / f).exists() for f in part_files):
                return _build_result(step, part_idx, STEP_PART_FILES, dialogue_files, dialogue_count, total_dialogue_count)
            # Current Part complete, check next Part

    # All complete
    return _build_result(8, 0, STEP_PART_FILES, dialogue_files, dialogue_count, total_dialogue_count)


def _build_result(step, part, step_part_files, dialogue_files, dialogue_count, total_dialogue_count) -> dict:
    """Build progress result dictionary."""
    completed = []
    for s, parts in step_part_files.items():
        if s < step:
            completed.append(s)
    return {
        "step": step,
        "part": part,
        # part > 0 means this step has an incomplete part; next_step stays on current step, start at that part
        # part == 0 means all parts of this step are done; next_step is the following step
        "next_step": step if part > 0 else (step + 1 if step < 8 else None),
        "next_part": part if part > 0 else 1,
        "completed": sorted(set(completed)),
        "dialogue_files": dialogue_files,
        "dialogue_count": dialogue_count,
        "total_dialogue_count": total_dialogue_count,
    }


def list_incomplete_runs() -> list:
    """
    List all incomplete runs.

    Returns:
        list of dict: [{
            "run_id": str,
            "run_dir": Path,
            "title": str,  # Research topic
            "progress": dict,  # detect_run_progress() return value
            "created": datetime,
        }]
    """
    base_dir = Path(__file__).parent / "run_result"

    if not base_dir.exists():
        return []

    incomplete_runs = []

    for run_path in sorted(base_dir.iterdir(), reverse=True):
        if not run_path.is_dir():
            continue

        # Skip temporary or backup directories
        if run_path.name.startswith(".") or run_path.name.startswith("test_"):
            continue

        # Detect progress
        progress = detect_run_progress(run_path)

        # If step 8 is complete, skip
        if progress["step"] >= 8 and progress.get("next_step") is None:
            continue

        # Get title
        title = "Untitled Research"
        project_file = run_path / "project.json"
        if project_file.exists():
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                title = project_data.get("title", "Untitled Research")
            except:
                pass

        # 获取创建时间
        created = None
        state_file = run_path / "state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                # state.json 中的 run_id 包含时间戳
            except:
                pass

        incomplete_runs.append({
            "run_id": run_path.name,
            "run_dir": run_path,
            "title": title,
            "progress": progress,
            "created": created,
        })

    return incomplete_runs


def load_run_state(run_dir: Path) -> dict:
    """
    Load complete state from run directory.

    Returns:
        dict: Restored state
    """
    from models import Provider, Expert

    state = {"run_dir": str(run_dir), "run_id": run_dir.name}

    # Load project.json
    project_file = run_dir / "project.json"
    if project_file.exists():
        with open(project_file, 'r', encoding='utf-8') as f:
            state["project"] = json.load(f)

    # Load providers.json (convert to Provider objects)
    providers_file = run_dir / "providers.json"
    if providers_file.exists():
        with open(providers_file, 'r', encoding='utf-8') as f:
            providers_data = json.load(f)
        providers = {}
        for k, v in providers_data.items():
            # Convert to Provider object
            providers[k] = Provider(
                key=v.get("key", k),
                name=v.get("name", ""),
                adapter=v.get("adapter", ""),
                base_url=v.get("base_url", ""),
                api_key=v.get("api_key", ""),
                default_model=v.get("default_model", ""),
                models=v.get("models", []),
                model_capabilities=v.get("model_capabilities", {}),
            )
        state["providers"] = providers

    # Load experts.json (convert to Expert object list)
    experts_file = run_dir / "experts.json"
    if experts_file.exists():
        with open(experts_file, 'r', encoding='utf-8') as f:
            experts_data = json.load(f)
        experts_list = experts_data.get("experts", [])
        state["experts"] = [Expert(**e) for e in experts_list]
        state["experts_count"] = experts_data.get("experts_count", 0)

    # Load interview_framework.json
    framework_file = run_dir / "interview_framework.json"
    if framework_file.exists():
        with open(framework_file, 'r', encoding='utf-8') as f:
            state["interview_framework"] = json.load(f)

    # Load rounds config (convert to RoundsConfig object)
    from models import RoundsConfig
    rounds_file = run_dir / "rounds.json"
    if rounds_file.exists():
        with open(rounds_file, 'r', encoding='utf-8') as f:
            rounds_data = json.load(f)
        # scoring_dimensions computed by AHP in Step 5 Part 2, no longer read from rounds.json
        state["rounds"] = RoundsConfig(
            round_1_turns=rounds_data.get("round_1", {}).get("turns", 5),
            round_2_dimensions=[],  # Computed by AHP in Step 5
            convergence_threshold=rounds_data.get("convergence_threshold", 0.5),
            max_rounds=rounds_data.get("max_rounds", 3),
            max_turns_per_expert=rounds_data.get("interview_dynamics", {}).get("max_turns_per_expert", 20),
            min_follow_ups_per_topic=rounds_data.get("interview_dynamics", {}).get("min_follow_ups_per_topic", 3),
            max_follow_ups_per_topic=rounds_data.get("interview_dynamics", {}).get("max_follow_ups_per_topic", 8),
        )

    return state


def display_run_progress_bar(progress: dict, width: int = 50) -> str:
    """
    Display progress bar.

    Args:
        progress: detect_run_progress() return value
        width: Progress bar width

    Returns:
        str: Progress bar string
    """
    step = progress["step"]
    total = 8
    percentage = int((step / total) * 100)

    filled = int((step / total) * width)
    empty = width - filled

    bar = f"{Colors.GREEN}{'█' * filled}{Colors.BRIGHT_BLACK}{'░' * empty}{Colors.RESET}"
    percentage_str = f"{percentage}%"

    return f"{bar} {percentage_str}"


def show_resume_menu(runs: list) -> str:
    """
    Show resume run menu.

    Returns:
        str: "new" or run_id
    """
    print_header("Continue Previous Run")

    if not runs:
        print(f"\n  {Colors.YELLOW}No incomplete runs found{Colors.RESET}")
        print(f"\n  {Colors.CYAN}Please select to start a new run{Colors.RESET}")
        return "new"

    print(f"\n  {Colors.CYAN}Detected {len(runs)} incomplete runs:{Colors.RESET}\n")

    for i, run in enumerate(runs, 1):
        progress = run["progress"]
        step = progress["step"]
        next_step = progress.get("next_step")

        # Get step names
        step_names = {
            0: "Not Started",
            1: "Project Setup",
            2: "API Config",
            3: "Expert Config",
            4: "Round Config",
            5: "Execute Pipeline",
            6: "Delphi Results",
            7: "AHP Results",
            8: "Complete",
        }
        current_name = step_names.get(step, f"Step {step}")
        next_name = step_names.get(next_step, f"Step {next_step}") if next_step else "Complete"

        print(f"  {Colors.CYAN}{i}. {run['run_id']}{Colors.RESET}")
        print(f"     Research: {run['title']}")
        print(f"     Progress: {display_run_progress_bar(progress)}")
        print(f"     Status: {Colors.GREEN}[Step {step} {current_name}]{Colors.RESET} → Next: {Colors.YELLOW}[Step {next_step} {next_name}]{Colors.RESET}" if next_step else f"     Status: {Colors.GREEN}[Complete]{Colors.RESET}")

        # Show dialogue progress
        if progress["total_dialogue_count"] > 0:
            dc = progress["dialogue_count"]
            tc = progress["total_dialogue_count"]
            print(f"     Dialogues: {dc}/{tc} generated")

        print()

    print(f"  {Colors.CYAN}0. Return to upper menu{Colors.RESET}")

    choices = [str(i) for i in range(1, len(runs) + 1)] + ["0"]
    selected = questionary.select(
        "Select run to continue",
        choices=choices,
    ).ask()

    if selected == "0":
        return "back"

    idx = int(selected) - 1
    return runs[idx]["run_id"]


def ask_continue_or_back(current_step: int, state: dict, run_dir: Path) -> str:
    """
    After completing a step, ask user whether to continue to next or go back.

    Args:
        current_step: Current completed step number (1-8)
        state: Current state
        run_dir: Run directory

    Returns:
        "next" - Continue to next step
        "back" - Return to previous step
        "quit" - Exit program
    """
    # First step cannot go back
    if current_step <= 1:
        response = questionary.select(
            "Select action",
            choices=["Continue to next", "Exit"],
        ).ask()
        return "next" if response == "Continue to next" else "quit"

    # Determine previous and next step numbers
    prev_step = current_step - 1
    next_step = current_step + 1 if current_step < 8 else None

    # Build options
    choices = []
    if next_step:
        choices.append(f"Continue to next (Step {next_step})")
    choices.append(f"Go back (Step {prev_step})")
    choices.append("Exit program")

    response = questionary.select(
        "Select action",
        choices=choices,
    ).ask()

    if "Continue to next" in str(response):
        return "next"
    elif "Go back" in str(response):
        return "back"
    else:
        return "quit"


def show_step_summary(step_num: int, state: dict):
    """
    Show summary of saved content for a step, helping user decide whether to modify.

    Args:
        step_num: Step number (1-8)
        state: Current state
    """
    print(f"\n{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Step {step_num} Currently Saved Content{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")

    if step_num == 1:
        project = state.get("project", {})
        if project:
            print(f"\n  {Colors.GREEN}✓ Project Title: {Colors.CYAN}{project.get('title', 'Not Set')}{Colors.RESET}")
            print(f"  {Colors.GREEN}✓ Analysis Framework: {Colors.CYAN}{project.get('framework', 'Not Set')}{Colors.RESET}")
        else:
            print(f"\n  {Colors.YELLOW}No project information saved yet{Colors.RESET}")

    elif step_num == 2:
        providers = state.get("providers", {})
        if providers:
            print(f"\n  {Colors.GREEN}✓ Configured {len(providers)} provider(s):{Colors.RESET}")
            for k, p in providers.items():
                if isinstance(p, dict):
                    print(f"    - {k}: {len(p.get('models', []))} models, default: {p.get('default_model', '')}")
                else:
                    print(f"    - {k}: {len(p.models)} models, default: {p.default_model}")
        else:
            print(f"\n  {Colors.YELLOW}No providers configured yet{Colors.RESET}")

    elif step_num == 3:
        experts = state.get("experts", [])
        if experts:
            print(f"\n  {Colors.GREEN}✓ Configured {len(experts)} expert(s):{Colors.RESET}")
            for e in experts[:5]:  # Show only first 5
                if isinstance(e, dict):
                    print(f"    - {e.get('name', 'unknown')} ({e.get('role', '')}) - {e.get('provider_name', '')}/{e.get('model', '')}")
                else:
                    print(f"    - {e.name} ({e.role}) - {e.provider_name}/{e.model}")
            if len(experts) > 5:
                print(f"    ... and {len(experts) - 5} more expert(s)")
        else:
            print(f"\n  {Colors.YELLOW}No experts configured yet{Colors.RESET}")

    elif step_num == 4:
        rounds = state.get("rounds", {})
        if rounds:
            print(f"\n  {Colors.GREEN}✓ Round configuration saved{Colors.RESET}")
        else:
            print(f"\n  {Colors.YELLOW}No rounds configured yet{Colors.RESET}")

    elif step_num == 5:
        print(f"\n  {Colors.GREEN}✓ Pipeline execution results saved{Colors.RESET}")

    elif step_num == 6:
        print(f"\n  {Colors.GREEN}✓ Delphi results saved{Colors.RESET}")

    elif step_num == 7:
        print(f"\n  {Colors.GREEN}✓ AHP results saved{Colors.RESET}")

    elif step_num == 8:
        print(f"\n  {Colors.GREEN}✓ Final report generated{Colors.RESET}")

    print(f"{Colors.BRIGHT_CYAN}{'='*60}{Colors.RESET}")


def ask_confirm_or_modify(step_num: int, state: dict) -> str:
    """
    Ask user to confirm current content or modify it.

    Args:
        step_num: Step number
        state: Current state

    Returns:
        "confirm" - Confirm and continue
        "modify" - Modify again
    """
    show_step_summary(step_num, state)

    response = questionary.select(
        "Please select",
        choices=["Confirm, continue to next", "Modify this step"],
    ).ask()

    return "confirm" if response == "Confirm, continue to next" else "modify"


# ============================================================
# 主程序
# ============================================================

def main():
    """Main program"""
    state = {}

    print_header("Delphi-AHP Research Pipeline")

    # Check for incomplete runs
    incomplete_runs = list_incomplete_runs()

    # Start menu
    print(f"""
{Colors.CYAN}This program will guide you through 8 steps of Delphi-AHP research:{Colors.RESET}

  {Colors.YELLOW}1.{Colors.RESET} {Colors.BRIGHT_YELLOW}Project Setup{Colors.RESET}     - Enter research topic and background
  {Colors.YELLOW}2.{Colors.RESET} {Colors.BRIGHT_CYAN}API Config{Colors.RESET}      - Set LLM provider (required)
  {Colors.YELLOW}3.{Colors.RESET} {Colors.BRIGHT_GREEN}Expert Config{Colors.RESET}    - Define expert panel
  {Colors.YELLOW}4.{Colors.RESET} {Colors.BRIGHT_MAGENTA}Round Config{Colors.RESET}    - Set Delphi rounds
  {Colors.YELLOW}5.{Colors.RESET} {Colors.BRIGHT_BLUE}Execute Pipeline{Colors.RESET} - Run complete process
  {Colors.YELLOW}6.{Colors.RESET} {Colors.BRIGHT_RED}Delphi Results{Colors.RESET}  - View convergence results
  {Colors.YELLOW}7.{Colors.RESET} {Colors.BRIGHT_RED}AHP Results{Colors.RESET}     - View weights and consistency
  {Colors.YELLOW}8.{Colors.RESET} {Colors.BRIGHT_WHITE}Generate Report{Colors.RESET}   - Output final report
""")

    # Show options menu
    choices = ["Start New Run"]
    if incomplete_runs:
        choices.append("Continue Previous Run")

    print(f"{Colors.WHITE}Please select:{Colors.RESET}\n")

    selected = questionary.select(
        "Select action",
        choices=choices,
    ).ask()

    # Handle selection
    if selected == "Continue Previous Run":
        selected_run_id = show_resume_menu(incomplete_runs)
        if selected_run_id == "back":
            # User chose to go back, redisplay menu
            return main()
        elif selected_run_id and selected_run_id != "new":
            # Resume run
            run_dir = Path(__file__).parent / "run_result" / selected_run_id
            state = load_run_state(run_dir)
            state["resume_mode"] = True  # Mark as resume mode

            # Get current progress
            progress = detect_run_progress(run_dir)
            current_step = progress["step"]
            current_part = progress["part"]
            print(f"\n{Colors.GREEN}✓ Resumed run: {selected_run_id}{Colors.RESET}")
            part_hint = f" Part {current_part}" if current_part > 0 else ""
            print(f"  Current progress: Step {current_step}{part_hint}")
            print(f"  Research topic: {state.get('project', {}).get('title', 'Unknown')}")

            if current_step >= 8:
                print(f"\n{Colors.GREEN}This run is complete! Please select:{Colors.RESET}")
                view_choice = questionary.select(
                    "Select action",
                    choices=["View Report", "Start New Run"],
                ).ask()
                if view_choice == "Start New Run":
                    return main()
                elif view_choice == "View Report":
                    # Jump to Step 8
                    current_step = 7
            else:
                # Continue to next step
                current_step = current_step  # Keep current step, user can choose to continue or go back

            # Continue main loop
            run_dir = Path(state["run_dir"])
            state["resume_mode"] = True
            resume_step = progress.get("next_step", current_step)
            resume_part = progress.get("next_part", 1)
            completed_steps = progress.get("completed", [])
            completed_upto = max(completed_steps) if completed_steps else 0
            state["resume_part"] = resume_part

            # Show step summary (only show truly completed steps)
            if completed_upto >= 1:
                print(f"\n{Colors.CYAN}Current State:{Colors.RESET}")
                for step in range(1, completed_upto + 1):
                    show_step_summary(step, state)

            # Show resume target
            part_hint = f"(continue from Part {resume_part})" if resume_part > 1 else ""
            if completed_upto >= 1:
                print(f"\n{Colors.YELLOW}Completed steps: Step 1-{completed_upto}{Colors.RESET}")
            else:
                print(f"\n{Colors.YELLOW}Completed steps: None{Colors.RESET}")
            print(f"{Colors.YELLOW}Next: Step {resume_step}{part_hint}{Colors.RESET}")

            # resume_from_step's current_step represents "last completed step", so pass resume_step - 1
            return resume_from_step(state, max(0, resume_step - 1))

    # User chose "Start New Run"
    if selected == "Start New Run" or not selected:
        pass  # Continue normal flow

    try:
        # Initialize run_id format (tentative, only timestamp at start)
        state["run_id"] = f"run_{get_timestamp()}"
        state["run_base_dir"] = str(Path(__file__).parent / "run_result")
        state["resume_mode"] = False

        # 跟踪当前步骤
        current_step = 0
        run_dir = None

        # ============================================================
        # Steps 1-8 (with navigation)
        # ============================================================

        # Step 1: Project Setup
        # Step 1 has no checkpoint because it is the starting step
        state = run_step1(state)
        current_step = 1

        while True:
            action = ask_continue_or_back(current_step, state, run_dir)

            if action == "quit":
                # Save progress and exit
                if "run_dir" in state:
                    state_path = Path(state["run_dir"]) / "state.json"
                    save_state(state, state_path)
                    print(f"\n{Colors.YELLOW}Progress saved{Colors.RESET}")
                print(f"\n{Colors.YELLOW}Program exited.{Colors.RESET}")
                sys.exit(0)

            elif action == "back":
                # Go back to previous step
                prev_step = current_step - 1
                if prev_step < 1:
                    print(f"\n{Colors.YELLOW}Already at the first step{Colors.RESET}")
                    continue

                # Ask to confirm or modify
                confirm_action = ask_confirm_or_modify(prev_step, state)

                if confirm_action == "confirm":
                    # Confirm previous step content, but first validate prerequisites
                    is_valid, msg = validate_step_prerequisites(prev_step, run_dir)
                    if not is_valid:
                        print(f"\n{Colors.YELLOW}Step {prev_step} prerequisites not met, cannot continue:{Colors.RESET}")
                        print(msg)
                        print(f"{Colors.YELLOW}Please select 'Modify this step' to re-execute.{Colors.RESET}")
                        current_step = prev_step  # Go back to previous step
                        continue
                    current_step = prev_step + 1
                else:
                    # Re-modify previous step
                    print(f"\n{Colors.CYAN}Re-executing Step {prev_step}...{Colors.RESET}")

                    # Re-run the corresponding step
                    if prev_step == 1:
                        state = run_step1(state)
                    elif prev_step == 2:
                        run_dir = Path(state.get("run_dir", Path(__file__).parent / "run_result" / state.get("run_id")))
                        state = run_step2(state)
                    elif prev_step == 3:
                        state = run_step3(state)
                    elif prev_step == 4:
                        state = run_step4(state)
                    elif prev_step == 5:
                        state = run_step5(state)
                    elif prev_step == 6:
                        state = run_step6(state)
                    elif prev_step == 7:
                        state = run_step7(state)
                    elif prev_step == 8:
                        state = run_step8(state)

                    current_step = prev_step
                    print(f"\n{Colors.GREEN}Step {prev_step} re-completed{Colors.RESET}")

                continue

            # Continue to next step
            current_step += 1

            # Step 2: API Config - check step 1
            if current_step == 2:
                run_id = state.get("run_id", "default_run")
                run_dir = Path(state.get("run_dir", Path(__file__).parent / "run_result" / run_id))
                if not interactive_checkpoint(2, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete Step 1 prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step2(state)

            # Step 3: Expert Config - check steps 1-2
            elif current_step == 3:
                if not interactive_checkpoint(3, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete required prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step3(state)

            # Step 4: Round Config - check steps 1-3
            elif current_step == 4:
                if not interactive_checkpoint(4, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete required prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step4(state)

            # Step 5: Execute Pipeline - check steps 1-4
            elif current_step == 5:
                if not interactive_checkpoint(5, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete required prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step5(state)

            # Step 6: Delphi Results - check steps 1-5
            elif current_step == 6:
                if not interactive_checkpoint(6, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete required prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step6(state)

            # Step 7: AHP Results - check convergence
            elif current_step == 7:
                if not interactive_checkpoint(7, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete required prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step7(state)

            # Step 8: Generate Report - check step 5 outputs
            elif current_step == 8:
                if not interactive_checkpoint(8, run_dir, state.get("resume_mode", False)):
                    print(f"\n{Colors.RED}Please complete required prerequisites first.{Colors.RESET}")
                    sys.exit(1)
                state = run_step8(state)

            # Check if all steps are complete
            if current_step >= 8:
                # Save final state
                run_dir = Path(state["run_dir"])
                state_path = run_dir / "state.json"
                save_state(state, state_path)

                print(f"\n{Colors.GREEN}{'=' * 60}{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.GREEN}  All Steps Complete!{Colors.RESET}")
                print(f"{Colors.GREEN}{'=' * 60}{Colors.RESET}")
                print(f"\nRun directory: {Colors.CYAN}{run_dir}{Colors.RESET}")
                print(f"\n{Colors.BRIGHT_GREEN}Thank you for using Delphi-AHP Pipeline!{Colors.RESET}")
                break

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Program interrupted by user.{Colors.RESET}")
        # Save current progress
        if "run_dir" in state:
            state_path = Path(state["run_dir"]) / "state.json"
            save_state(state, state_path)
            print(f"Progress saved to: {state_path}")
        print(f"\n{Colors.YELLOW}Program exited.{Colors.RESET}")
        sys.exit(0)

    except Exception as e:
        print(f"\n\n{Colors.RED}Error occurred: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        # Save error state
        if "run_dir" in state:
            state_path = Path(state["run_dir"]) / "error_state.json"
            save_state(state, state_path)
            print(f"{Colors.YELLOW}Error state saved to: {state_path}{Colors.RESET}")
        sys.exit(1)


def resume_from_step(state: dict, current_step: int):
    """
    Continue execution from resume point.

    Args:
        state: Resumed state
        current_step: Step completed before resume
    """
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / state.get("run_id", "")))

    try:
        while True:
            action = ask_continue_or_back(current_step, state, run_dir)

            if action == "quit":
                if "run_dir" in state:
                    state_path = Path(state["run_dir"]) / "state.json"
                    save_state(state, state_path)
                    print(f"\n{Colors.YELLOW}Progress saved{Colors.RESET}")
                print(f"\n{Colors.YELLOW}Program exited.{Colors.RESET}")
                sys.exit(0)

            elif action == "back":
                prev_step = current_step - 1
                if prev_step < 1:
                    print(f"\n{Colors.YELLOW}Already at the first step{Colors.RESET}")
                    continue

                confirm_action = ask_confirm_or_modify(prev_step, state)
                if confirm_action == "confirm":
                    # Confirm previous step content, but first validate prerequisites
                    is_valid, msg = validate_step_prerequisites(prev_step, run_dir)
                    if not is_valid:
                        print(f"\n{Colors.YELLOW}Step {prev_step} prerequisites not met, cannot continue:{Colors.RESET}")
                        print(msg)
                        print(f"\n{Colors.YELLOW}Please select 'Modify this step' to re-execute.{Colors.RESET}")
                        current_step = prev_step  # Go back to previous step
                        continue
                    current_step = prev_step + 1
                    state["resume_part"] = 1  # Enter new Step, start from Part 1
                else:
                    print(f"\n{Colors.CYAN}Re-executing Step {prev_step}...{Colors.RESET}")
                    state["resume_part"] = 1  # Re-run Step, start from Part 1
                    if prev_step == 1:
                        state = run_step1(state)
                    elif prev_step == 2:
                        state = run_step2(state)
                    elif prev_step == 3:
                        state = run_step3(state)
                    elif prev_step == 4:
                        state = run_step4(state)
                    elif prev_step == 5:
                        state = run_step5(state)
                    elif prev_step == 6:
                        state = run_step6(state)
                    elif prev_step == 7:
                        state = run_step7(state)
                    elif prev_step == 8:
                        state = run_step8(state)
                    current_step = prev_step
                    print(f"\n{Colors.GREEN}Step {prev_step} re-completed{Colors.RESET}")
                continue

            # Continue to next step
            current_step += 1

            # When entering new Step, start from Part 1; if continuing remaining Part of current Step, use resume_part
            resume_part = state.pop("resume_part", 1)
            state["resume_part"] = resume_part

            # 执行对应步骤
            if current_step == 2:
                state = run_step2(state)
            elif current_step == 3:
                state = run_step3(state)
            elif current_step == 4:
                state = run_step4(state)
            elif current_step == 5:
                state = run_step5(state)
            elif current_step == 6:
                state = run_step6(state)
            elif current_step == 7:
                state = run_step7(state)
            elif current_step == 8:
                state = run_step8(state)

            if current_step >= 8:
                run_dir = Path(state["run_dir"])
                state_path = run_dir / "state.json"
                save_state(state, state_path)
                print(f"\n{Colors.GREEN}{'=' * 60}{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.GREEN}  All Steps Complete!{Colors.RESET}")
                print(f"{Colors.GREEN}{'=' * 60}{Colors.RESET}")
                print(f"\nRun directory: {Colors.CYAN}{run_dir}{Colors.RESET}")
                print(f"\n{Colors.BRIGHT_GREEN}Thank you for using Delphi-AHP Pipeline!{Colors.RESET}")
                break

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Program interrupted by user.{Colors.RESET}")
        if "run_dir" in state:
            state_path = Path(state["run_dir"]) / "state.json"
            save_state(state, state_path)
            print(f"Progress saved to: {state_path}")
        print(f"\n{Colors.YELLOW}Program exited.{Colors.RESET}")
        sys.exit(0)

    except Exception as e:
        print(f"\n\n{Colors.RED}Error occurred: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        if "run_dir" in state:
            state_path = Path(state["run_dir"]) / "error_state.json"
            save_state(state, state_path)
            print(f"{Colors.YELLOW}Error state saved to: {state_path}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
