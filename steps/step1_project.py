"""
Step 1: Project Setup
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List
import questionary
from models import Project
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan,
    bold_red, bold_green, bold_yellow, bold_blue, bold_magenta, bold_cyan,
    error_text, success_text, warning_text, info_text,
    CONFIRM_COLORS
)


def interactive_select(title: str, items: List[str], multi_select: bool = False) -> List[int]:
    """Interactive selection function with arrow key navigation."""
    if not items:
        return []

    print(f"\n{title}")

    if multi_select:
        selected = questionary.checkbox(
            'Use arrow keys to move, Space to select, Enter to confirm',
            choices=items,
            validate=lambda s: len(s) > 0 or "Please select at least one item"
        ).ask()
        if selected is None:
            return []
        return [items.index(s) for s in selected if s in items]
    else:
        selected = questionary.select(
            'Use arrow keys to move, Enter to confirm',
            choices=items,
        ).ask()
        if selected is None:
            return []
        return [items.index(selected)]


def save_json(filepath: Path, data: dict):
    """Save JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{Colors.GREEN}  ✓ Saved: {filepath}{Colors.RESET}")


def print_step_header():
    """Print step 1 header."""
    print()
    print("─" * 60)
    print("  Step 1/8: Project Setup")
    print("─" * 60)
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
            print(f"Please enter a number between {min_val} and {max_val}")
        except ValueError:
            print("Please enter a valid number")


def get_timestamp() -> str:
    """Get local timezone timestamp, format: 20260418_223045"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def slugify(text: str, max_length: int = 20) -> str:
    """
    Convert text to a filename-friendly slug format.
    - Replace spaces with underscores
    - Remove non-alphanumeric characters
    - Truncate to max length
    """
    import re
    # Replace spaces with underscores
    slug = text.replace(" ", "_")
    # Remove non-alphanumeric characters (keep underscores)
    slug = re.sub(r'[^\w_]', '', slug)
    # Truncate
    slug = slug[:max_length]
    return slug


def run_step1(state: dict) -> dict:
    """
    Run step 1: Project setup.

    Args:
        state: Current state dict

    Returns:
        Updated state dict
    """
    print_step_header()

    print("Please enter your research project information (all fields are required):")
    print()

    # Collect project info - NO defaults
    title = ask("Research Title")
    while not title:
        print(f"  {Colors.RED}[Error] Research title cannot be empty{Colors.RESET}")
        title = ask("Research Title")

    framework = ask("Analysis Framework (e.g., PEST, SWOT, Porter's Five Forces, etc.)")
    while not framework:
        print(f"  {Colors.RED}[Error] Analysis framework cannot be empty{Colors.RESET}")
        framework = ask("Analysis Framework (e.g., PEST, SWOT, Porter's Five Forces, etc.)")

    background = ask("Research Background")
    while not background:
        print(f"  {Colors.RED}[Error] Research background cannot be empty{Colors.RESET}")
        background = ask("Research Background")

    purpose = ask("Research Purpose")
    while not purpose:
        print(f"  {Colors.RED}[Error] Research purpose cannot be empty{Colors.RESET}")
        purpose = ask("Research Purpose")

    boundaries = ask("Research Boundaries/Scope")
    while not boundaries:
        print(f"  {Colors.RED}[Error] Research boundaries cannot be empty{Colors.RESET}")
        boundaries = ask("Research Boundaries/Scope")

    # Collect research questions
    print("\nResearch Questions (enter empty line to finish):")
    research_questions = []
    while True:
        q = ask(f"  Question {len(research_questions) + 1}")
        if not q:
            if len(research_questions) == 0:
                print(f"  {Colors.RED}[Error] At least one research question is required{Colors.RESET}")
                continue
            break
        research_questions.append(q)

    if not research_questions:
        print(f"  {Colors.YELLOW}[Warning] No research questions added, the process may not execute properly{Colors.RESET}")

    # Delphi output language selection
    print()
    lang_choice = questionary.select(
        "Delphi Interview Language / 德尔菲访谈语言",
        choices=["Chinese (中文)", "English (英文)"],
    ).ask()
    delphi_lang = "zh" if lang_choice == "Chinese (中文)" else "en"
    print(f"  Selected: {lang_choice}")

    # ============================================================
    # Review and confirmation section (yellow box)
    # ============================================================
    while True:
        # Build confirmation content
        content_lines = []

        # 1. Research Title
        content_lines.append(f"{Colors.BRIGHT_YELLOW}1. Research Title:{Colors.RESET}")
        content_lines.append(f"   {title}")

        # 2. Analysis Framework
        content_lines.append(f"{Colors.BRIGHT_CYAN}2. Analysis Framework:{Colors.RESET}")
        content_lines.append(f"   {framework}")

        # 3. Research Background
        content_lines.append(f"{Colors.BRIGHT_GREEN}3. Research Background:{Colors.RESET}")
        bg_lines = [background[i:i+55] for i in range(0, min(len(background), 165), 55)]
        for line in bg_lines:
            content_lines.append(f"   {line}")

        # 4. Research Purpose
        content_lines.append(f"{Colors.BRIGHT_MAGENTA}4. Research Purpose:{Colors.RESET}")
        pur_lines = [purpose[i:i+55] for i in range(0, min(len(purpose), 165), 55)]
        for line in pur_lines:
            content_lines.append(f"   {line}")

        # 5. Research Boundaries
        content_lines.append(f"{Colors.BRIGHT_BLUE}5. Research Boundaries:{Colors.RESET}")
        bnd_lines = [boundaries[i:i+55] for i in range(0, min(len(boundaries), 165), 55)]
        for line in bnd_lines:
            content_lines.append(f"   {line}")

        # 6. Research Questions
        content_lines.append(f"{Colors.BRIGHT_RED}6. Research Questions:{Colors.RESET}")
        if research_questions:
            for i, q in enumerate(research_questions, 1):
                q_lines = [q[j:j+55] for j in range(0, min(len(q), 110), 55)]
                content_lines.append(f"   {Colors.BRIGHT_RED}Question {i}:{Colors.RESET} {q_lines[0]}")
                for line in q_lines[1:]:
                    content_lines.append(f"           {line}")
        else:
            content_lines.append(f"   {Colors.YELLOW}[Warning] No research questions added{Colors.RESET}")

        # 7. Delphi Language
        lang_display = "Chinese (中文)" if delphi_lang == "zh" else "English (英文)"
        content_lines.append(f"{Colors.BRIGHT_CYAN}7. Delphi Interview Language:{Colors.RESET}")
        content_lines.append(f"   {lang_display}")

        # Print yellow box
        box_width = 65
        print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}       Please Review Your Input       {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")

        for line in content_lines:
            padding = box_width - len(line) - 4
            if padding < 0:
                padding = 0
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}  Select Action:{Colors.RESET}{' ' * (box_width - 18)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm and continue{Colors.RESET}{' ' * (box_width - 30)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.YELLOW}  2{Colors.RESET} - {Colors.YELLOW}Modify an item{Colors.RESET}{' ' * (box_width - 28)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")

        # Use interactive selection
        confirm_options = ["Confirm and continue", "Modify an item"]
        selected = questionary.select(
            "Select Action",
            choices=confirm_options,
        ).ask()

        if selected is None:
            print(f"\n{Colors.YELLOW}  Action cancelled{Colors.RESET}")
            continue

        if selected == "Confirm and continue":
            print(f"\n{Colors.GREEN}{Colors.BOLD}  ✓ Information confirmed, continuing...{Colors.RESET}")
            break

        # User chose modify - show modification options menu
        field_options = ["Research Title", "Analysis Framework", "Research Background", "Research Purpose", "Research Boundaries", "Research Questions (re-enter all)", "Delphi Interview Language"]
        selected_field = questionary.select(
            "Select item to modify",
            choices=field_options,
        ).ask()

        if selected_field is None:
            continue

        field_choice = field_options.index(selected_field) + 1

        if field_choice == 1:
            print(f"\n{Colors.BRIGHT_YELLOW}Modify Research Title:{Colors.RESET}")
            title = ask("Research Title")
            while not title:
                print(f"  {Colors.RED}[Error] Research title cannot be empty{Colors.RESET}")
                title = ask("Research Title")
        elif field_choice == 2:
            print(f"\n{Colors.BRIGHT_CYAN}Modify Analysis Framework:{Colors.RESET}")
            framework = ask("Analysis Framework (e.g., PEST, SWOT, Porter's Five Forces, etc.)")
            while not framework:
                print(f"  {Colors.RED}[Error] Analysis framework cannot be empty{Colors.RESET}")
                framework = ask("Analysis Framework (e.g., PEST, SWOT, Porter's Five Forces, etc.)")
        elif field_choice == 3:
            print(f"\n{Colors.BRIGHT_GREEN}Modify Research Background:{Colors.RESET}")
            background = ask("Research Background")
            while not background:
                print(f"  {Colors.RED}[Error] Research background cannot be empty{Colors.RESET}")
                background = ask("Research Background")
        elif field_choice == 4:
            print(f"\n{Colors.BRIGHT_MAGENTA}Modify Research Purpose:{Colors.RESET}")
            purpose = ask("Research Purpose")
            while not purpose:
                print(f"  {Colors.RED}[Error] Research purpose cannot be empty{Colors.RESET}")
                purpose = ask("Research Purpose")
        elif field_choice == 5:
            print(f"\n{Colors.BRIGHT_BLUE}Modify Research Boundaries:{Colors.RESET}")
            boundaries = ask("Research Boundaries/Scope")
            while not boundaries:
                print(f"  {Colors.RED}[Error] Research boundaries cannot be empty{Colors.RESET}")
                boundaries = ask("Research Boundaries/Scope")
        elif field_choice == 6:
            print(f"\n{Colors.BRIGHT_RED}Re-enter Research Questions:{Colors.RESET}")
            print("\nResearch Questions (enter empty line to finish):")
            research_questions = []
            while True:
                q = ask(f"  Question {len(research_questions) + 1}")
                if not q:
                    if len(research_questions) == 0:
                        print(f"  {Colors.RED}[Error] At least one research question is required{Colors.RESET}")
                        continue
                    break
                research_questions.append(q)
            if not research_questions:
                print(f"  {Colors.YELLOW}[Warning] No research questions added, the process may not execute properly{Colors.RESET}")
        elif field_choice == 7:
            print(f"\n{Colors.BRIGHT_CYAN}Modify Delphi Interview Language:{Colors.RESET}")
            new_lang_choice = questionary.select(
                "Select Language / 选择语言",
                choices=["Chinese (中文)", "English (英文)"],
            ).ask()
            if new_lang_choice is not None:
                delphi_lang = "zh" if new_lang_choice == "Chinese (中文)" else "en"

    # Create project object
    project = Project(
        title=title,
        framework=framework,
        background=background,
        purpose=purpose,
        boundaries=boundaries,
        research_questions=research_questions,
        delphi_lang=delphi_lang,
    )

    # Generate run_id: run_<timestamp>_<title_slug>
    timestamp = get_timestamp()
    title_slug = slugify(title, max_length=20)
    run_id = f"run_{timestamp}_{title_slug}"

    # Create run directory
    base_dir = Path(__file__).parent.parent / "run_result"
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Update state - store dict version for consistency with other steps
    state["project"] = project.to_dict()
    state["run_id"] = run_id
    state["run_dir"] = str(run_dir)
    state["run_base_dir"] = str(base_dir)

    # Display result
    print("\nProject Configuration:")
    print(json.dumps(project.to_dict(), ensure_ascii=False, indent=2))

    print(f"\nRun Directory: {run_dir}")

    # Save project to run directory
    save_json(run_dir / "project.json", project.to_dict())

    return state
