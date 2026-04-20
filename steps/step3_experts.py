"""
Step 3: Expert Configuration
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List
import questionary
from models import Expert, Provider
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white, gray,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)
from steps.step2_api import get_max_tokens_label


def print_step_header():
    """Print step 3 header."""
    print()
    print("─" * 60)
    print("  Step 3/8: Expert Configuration")
    print("─"  * 60)
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


def ask_float(prompt: str, default: float, min_val: float = 0.0, max_val: float = 10.0) -> float:
    """Ask user for float input."""
    while True:
        response = ask(prompt, str(default))
        try:
            value = float(response)
            if min_val <= value <= max_val:
                return value
            print(f"Please enter a number between {min_val} and {max_val}")
        except ValueError:
            print("Please enter a valid number")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask yes/no question with validation.

    Args:
        prompt: The question to ask
        default: True for [Y/n] (Enter=y), False for [y/N] (Enter=n)

    Returns:
        True for yes, False for no

    Raises:
        ValueError if input is invalid (not Y/y/N/n or empty when required)
    """
    choices = "[Y/n]" if default else "[y/N]"
    default_hint = "(default Y)" if default else "(default n)"

    while True:
        response = ask(f"{prompt} {choices}{default_hint}", "Y" if default else "n")
        if not response:
            # Empty input - use default
            return default
        if response.upper() in ("Y", "YES"):
            return True
        if response.upper() in ("N", "NO"):
            return False
        # Invalid input - show error and retry
        print(f"  {Colors.RED}Error: Invalid input '{response}', please enter Y or N{Colors.RESET}")


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


def ask_choice(prompt: str, options: List[str], default: int = 0) -> int:
    """Let user choose from options."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        marker = " *" if i - 1 == default else ""
        print(f"  {i}. {opt}{marker}")

    while True:
        response = ask("Please select", str(default + 1))
        try:
            idx = int(response) - 1
            if 0 <= idx < len(options):
                return idx
            print(f"Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("Please enter a valid number")


def save_json(filepath: Path, data: dict):
    """Save JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [Saved] {filepath}")


def build_expert_generation_prompt(project, expert_count: int) -> str:
    """
    Build prompt for LLM to generate expert panel.
    Uses ALL project information from step 1 for better matching.

    Args:
        project: Project object or dict
        expert_count: Number of experts to generate
    """
    # Convert Project object to dict if needed
    if hasattr(project, 'to_dict'):
        project_data = project.to_dict()
    elif hasattr(project, 'get'):
        project_data = project
    else:
        project_data = {}

    questions = "\n".join([
        f"{i+1}. {q}"
        for i, q in enumerate(project_data.get("research_questions", [])[:10])
    ])

    prompt = f"""You are a research methodology expert. Please generate {expert_count} fictional but professional Delphi method expert panel members for the following research project.

## Complete Research Project Information

[Research Topic] {project_data.get('title', 'Unknown')}
[Analysis Framework] {project_data.get('framework', 'Unknown')}
[Research Background]
{project_data.get('background', 'Unknown')}
[Research Purpose]
{project_data.get('purpose', 'Unknown')}
[Research Boundaries/Scope]
{project_data.get('boundaries', 'Unknown')}

[Research Questions]
{questions}

## Expert Generation Requirements

Please generate information for {expert_count} experts, each expert must include:
- name: Name (Chinese or English)
- role: Position/Role (e.g., Professor, Analyst, Director, Chief, etc.)
- org_type: Organization type (e.g., University, Enterprise, Government Agency, Research Institution, Consulting Company, etc.)
- region: Region (e.g., Beijing, Shanghai, Shenzhen, Silicon Valley USA, etc.)
- expertise: Area of expertise (must be highly relevant to the research topic)
- language: Language preference (zh-CN, en-US, or mixed)
- scoring_bias: Scoring tendency (conservative/moderate, aggressive, balanced)
- pro: Brief expert profile (50-100 characters), summarizing the expert's core characteristics
- capability_base: Capability background description (1-2 sentences), describing the expert's core competencies and professional accumulation
- behavior_style: Behavior style description (1-2 sentences), describing the expert's thinking style and expression characteristics
- interview_focus: Interview focus direction (1-2 sentences), describing the research question angles the expert is most likely to focus on
- profile: Detailed persona description (2-3 paragraphs), including academic background, industry experience, research style, unique perspective on this research, etc.

## Expert Profile (Pro) Writing Guide

The pro field is the expert's "virtual persona description", which should include:
1. Academic/Professional background (education, title, main research direction)
2. Industry experience (projects participated in, roles held)
3. Research style (analysis methods, decision tendencies, thinking characteristics)
4. Unique perspective on this research (what aspects they may focus on, how they approach problems)

## New Field Description

- capability_base: The expert's most proficient professional field and core capabilities, e.g., "15 years of research experience in artificial intelligence, focusing on machine learning algorithm optimization"
- behavior_style: The expert's thinking and behavior characteristics, e.g., "tends to be data-driven analysis, with concise and direct expression"
- interview_focus: The question angles the expert is most likely to focus on in interviews, e.g., "more concerned with technology implementation feasibility and cost control"
- profile: 2-3 paragraphs of detailed persona, including academic background, industry experience, research style, unique perspective on this research, etc.

## Expert Diversity Requirements

1. **Organizational diversity** - Different types such as universities, enterprises, government, research institutions, consulting companies, etc.
2. **Regional diversity** - Different regions such as first-tier cities, second-tier cities, overseas, etc.
3. **Professional diversity** - Different perspectives such as technology, market, policy, management, etc.
4. **Age/Experience diversity** - Different levels such as senior experts, mid-career professionals, young scholars, etc.
5. **Complementary perspectives** - Experts from different backgrounds should be able to provide different perspectives on the same issue

Please return in JSON array format, example:
[
  {{
    "name": "Professor Zhang Wei",
    "role": "Department Chair of Computer Science / Director of AI Research Institute",
    "org_type": "University",
    "region": "Beijing Zhongguancun Technology Park",
    "expertise": "Artificial Intelligence, Machine Learning, Big Data Analytics",
    "language": "zh-CN",
    "scoring_bias": "moderate",
    "pro": "Professor Zhang Wei, PhD advisor, currently serves as Department Chair of Computer Science at a key university, and also as Director of the AI Research Institute. Graduated from MIT Computer Science, has long been engaged in machine learning and data mining research after returning to China. Conservative and steady in technology judgment, focusing on implementation feasibility.",
    "capability_base": "15 years of research experience in AI and machine learning, has led multiple national-level AI research projects, with deep accumulation in data mining and algorithm optimization.",
    "behavior_style": "Data-driven thinking, rigorous and clear logic in expression, tends to analyze problems from technical architecture perspective, cautious about industrialization paths of new technologies.",
    "interview_focus": "Technology feasibility assessment, algorithm limitation analysis, industry implementation challenges, prefers discussing specific technical solutions over macro trends.",
    "profile": "Professor Zhang Wei, PhD advisor, currently serves as Department Chair of Computer Science at a key university, and also as Director of the AI Research Institute. Graduated from MIT Computer Science, has long been engaged in machine learning and data mining research after returning to China, has led multiple national-level AI research projects, and has published over 50 papers in top conferences like NeurIPS and ICML.\n\nHas served as technical advisor for multiple technology companies, and acted as chief scientist in smart city and medical AI projects, having rich experience in AI technology industrialization applications. Conservative and steady in technology judgment, focusing on implementation feasibility, skilled at analyzing problems from technical architecture perspective.\n\nFor this research, focuses on technology maturity assessment and matching with practical application scenarios, will provide specific suggestions from algorithm efficiency and engineering implementation perspectives."
  }}
]

Only return the JSON array, do not include other text descriptions.
"""
    return prompt


def parse_experts_response(response: str) -> List[dict]:
    """Parse expert data from LLM response."""
    import re

    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            experts = json.loads(json_match.group())
            if isinstance(experts, list) and len(experts) > 0:
                return experts
        except json.JSONDecodeError:
            pass

    return []


def generate_experts_with_llm(project: dict, expert_count: int, provider: Provider) -> List[dict]:
    """Generate experts using LLM."""
    from llm import call_llm, LLMError

    prompt = build_expert_generation_prompt(project, expert_count)

    print(f"\n  Calling {provider.name} to generate expert panel...")
    print(f"  Using model: {provider.default_model}")

    try:
        response = call_llm(
            base_url=provider.base_url,
            api_key=provider.api_key,
            model=provider.default_model,
            prompt=prompt,
            system_prompt="You are a professional research methodology expert specializing in Delphi method research and can generate diverse, professional expert panels.",
            temperature=0.8,
        )

        experts = parse_experts_response(response)

        if experts:
            print(f"  [Success] Generated {len(experts)} experts")
            return experts
        else:
            print("  [Warning] Failed to parse expert data")
            return []

    except LLMError as e:
        print(f"  [Error] LLM call failed: {str(e)}")
        return []


def modify_expert_with_llm(expert_data: dict, gen_provider, gen_model) -> dict:
    """
    Modify an existing expert using LLM assistance.

    Logic:
    - Identity fields (role, org_type) modified → Regenerate all 5 persona fields
    - Related fields (name, region, expertise) modified → Regenerate all 5 persona fields
    - Persona fields (pro, etc.) modified → Only regenerate selected fields

    Args:
        expert_data: Original expert data dict
        gen_provider: Provider for LLM call
        gen_model: Model for LLM call

    Returns:
        Modified expert data dict
    """
    print(f"\n  Current Expert: {expert_data['name']}")
    print(f"  Role: {expert_data['role']}")
    print(f"  Organization: {expert_data['org_type']}")
    print()

    # Field Classification
    IDENTITY_FIELDS = {"Role", "Organization Type"}  # Modify these → Regenerate all persona fields
    RELATED_FIELDS = {"Name", "Region", "Expertise"}  # Modify these → Regenerate all persona fields
    PERSONA_FIELDS = {
        "Expert Profile": "pro",
        "Capability Base": "capability_base",
        "Behavior Style": "behavior_style",
        "Interview Focus": "interview_focus",
        "Detailed Profile": "profile",
    }

    # Ask which fields to modify
    print("  Please select fields to modify (multi-select):")
    field_options = [
        "Name",
        "Role",
        "Organization Type",
        "Region",
        "Expertise",
        "Expert Profile (pro)",
        "Capability Base (capability_base)",
        "Behavior Style (behavior_style)",
        "Interview Focus (interview_focus)",
        "Detailed Profile (profile)",
    ]

    selected_fields = questionary.checkbox(
        "Select fields to modify (Space to select, Enter to confirm)",
        choices=field_options,
    ).ask()

    if not selected_fields:
        print("  [Cancelled] No fields selected")
        return expert_data

    # Analyze field types to modify
    selected_identities = []  # Identity fields
    selected_related = []  # Related fields
    selected_personas = []  # Persona fields

    for field_option in selected_fields:
        field_name = field_option.split(" (")[0].strip()
        if field_name in IDENTITY_FIELDS:
            selected_identities.append(field_name)
        elif field_name in RELATED_FIELDS:
            selected_related.append(field_name)
        elif field_name in PERSONA_FIELDS:
            selected_personas.append(field_name)

    # Determine if persona regeneration is needed
    # Changed identity or related fields → Regenerate all 5 persona fields
    # Only changed persona fields → Only regenerate selected persona fields
    needs_full_regen = len(selected_identities) > 0 or len(selected_related) > 0
    needs_specific_regen = len(selected_personas) > 0 and not needs_full_regen

    modified = expert_data.copy()

    # Step 1: Update identity and related fields first (user inputs directly)
    for field_option in selected_fields:
        field_name = field_option.split(" (")[0].strip()

        if field_name == "Name":
            new_value = ask(f"  New Name", expert_data.get('name', ''))
            modified['name'] = new_value if new_value else expert_data.get('name', '')
        elif field_name == "Role":
            new_value = ask(f"  New Role", expert_data.get('role', ''))
            modified['role'] = new_value if new_value else expert_data.get('role', '')
        elif field_name == "Organization Type":
            new_value = ask(f"  New Organization Type", expert_data.get('org_type', ''))
            modified['org_type'] = new_value if new_value else expert_data.get('org_type', '')
        elif field_name == "Region":
            new_value = ask(f"  New Region", expert_data.get('region', ''))
            modified['region'] = new_value if new_value else expert_data.get('region', '')
        elif field_name == "Expertise":
            new_value = ask(f"  New Expertise", expert_data.get('expertise', ''))
            modified['expertise'] = new_value if new_value else expert_data.get('expertise', '')

    # Step 2: If identity or related fields changed, use LLM to regenerate all persona fields
    if needs_full_regen:
        print(f"\n  {Colors.CYAN}Identity or related info changed, regenerating expert persona with AI...{Colors.RESET}")

        if len(selected_identities) > 0:
            print(f"  {Colors.YELLOW}Note: Role or organization type changed, regenerating all persona fields{Colors.RESET}")

        try:
            from llm import call_llm
            assist_prompt = f"""Based on the following updated expert information, regenerate the complete expert persona:

[Basic Information]
Name: {modified.get('name', '')}
Role: {modified.get('role', '')}
Organization Type: {modified.get('org_type', '')}
Region: {modified.get('region', '')}
Expertise: {modified.get('expertise', '')}

[Persona Fields to Generate]
1. pro: Brief expert profile (50-100 characters), summarizing the expert's core characteristics
2. capability_base: Capability background description (1-2 sentences), describing the expert's core competencies and professional accumulation
3. behavior_style: Behavior style description (1-2 sentences), describing the expert's thinking style and expression characteristics
4. interview_focus: Interview focus direction (1-2 sentences), describing the research question angles the expert is most likely to focus on
5. profile: Detailed persona description (2-3 paragraphs), including academic background, industry experience, research style, unique perspective on this research, etc.

Return all fields in JSON format."""
            response = call_llm(
                base_url=gen_provider.base_url,
                api_key=gen_provider.api_key,
                model=gen_model,
                prompt=assist_prompt,
                system_prompt="You are a professional research methodology expert specializing in Delphi expert persona design.",
                temperature=0.8,
            )
            import re
            import json as json_lib
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                generated = json_lib.loads(json_match.group())
                modified['pro'] = generated.get('pro', expert_data.get('pro', ''))
                modified['capability_base'] = generated.get('capability_base', expert_data.get('capability_base', ''))
                modified['behavior_style'] = generated.get('behavior_style', expert_data.get('behavior_style', ''))
                modified['interview_focus'] = generated.get('interview_focus', expert_data.get('interview_focus', ''))
                modified['profile'] = generated.get('profile', expert_data.get('profile', ''))
                print(f"  {Colors.GREEN}✓ Persona regenerated{Colors.RESET}")
            else:
                print(f"  {Colors.YELLOW}⚠ Parse failed, keeping original content{Colors.RESET}")
        except Exception as e:
            print(f"  {Colors.RED}✗ AI regeneration failed: {str(e)}{Colors.RESET}")
            print(f"  {Colors.YELLOW}Keeping original content{Colors.RESET}")

    # Step 3: If only persona fields selected, regenerate only selected persona fields
    if needs_specific_regen:
        print(f"\n  {Colors.CYAN}Regenerating selected persona fields with AI...{Colors.RESET}")

        for field_option in selected_personas:
            field_name_cn = field_option  # e.g., "Expert Profile (pro)"
            field_key = PERSONA_FIELDS.get(field_name_cn)
            if not field_key:
                continue

            print(f"\n  Current {field_name_cn}: {expert_data.get(field_key, '')}")

            # Ask user if they want manual input or LLM generation
            use_llm_field = questionary.confirm(
                f"  Use AI to regenerate {field_name_cn}",
                default=True
            ).ask()

            if use_llm_field:
                try:
                    from llm import call_llm
                    field_prompts = {
                        "pro": "Expert profile (50-100 characters)",
                        "capability_base": "Capability background description (1-2 sentences)",
                        "behavior_style": "Behavior style description (1-2 sentences)",
                        "interview_focus": "Interview focus direction (1-2 sentences)",
                        "profile": "Detailed persona description (2-3 paragraphs)",
                    }
                    assist_prompt = f"""Based on the following expert information, generate {field_prompts[field_key]}:

Name: {modified.get('name', '')}
Role: {modified.get('role', '')}
Organization Type: {modified.get('org_type', '')}
Expertise: {modified.get('expertise', '')}

Please JSONreturn in format：{{"{field_key}": "..."}}"""
                    response = call_llm(
                        base_url=gen_provider.base_url,
                        api_key=gen_provider.api_key,
                        model=gen_model,
                        prompt=assist_prompt,
                        system_prompt="You are a professional research methodology expert specializing in Delphi expert persona design.",
                        temperature=0.8,
                    )
                    import re
                    import json as json_lib
                    json_match = re.search(r'\{[\s\S]*\}', response)
                    if json_match:
                        generated = json_lib.loads(json_match.group())
                        new_value = generated.get(field_key, expert_data.get(field_key, ''))
                        modified[field_key] = new_value
                        print(f"  {Colors.GREEN}✓ Regenerated{Colors.RESET}")
                    else:
                        print(f"  {Colors.YELLOW}⚠ Parse failed, keeping original content{Colors.RESET}")
                except Exception as e:
                    print(f"  {Colors.RED}✗ AI Generation failed: {str(e)}{Colors.RESET}")
                    print(f"  {Colors.YELLOW}Keeping original content{Colors.RESET}")
            else:
                # User manual input
                new_value = ask(f"  Enter new {field_name_cn}")
                if new_value:
                    modified[field_key] = new_value
                    print(f"  {Colors.GREEN}✓ Updated{Colors.RESET}")
                else:
                    print(f"  {Colors.YELLOW}Keeping original content{Colors.RESET}")

    return modified


def collect_custom_expert() -> dict:
    """
    Collect custom expert info from user input.

    Returns:
        dict with expert data or None if cancelled
    """
    print("\nPlease enter expert information (press Enter for default values):")

    name = ask("  Name")
    if not name:
        print("  [Cancelled] Name not entered")
        return None

    role = ask("  Role (e.g., Professor, Director, Analyst)")
    if not role:
        role = "Expert"

    org_type = ask("  Organization Type", "University")
    region = ask("  Region")
    if not region:
        region = "Unknown"

    expertise = ask("  Expertise")
    if not expertise:
        expertise = "General"

    # Language selection
    lang_options = ["Chinese (zh-CN)", "English (en-US)", "Mixed"]
    lang_idx = ask_choice("  Language Preference", lang_options, 0)
    language_map = ["zh-CN", "en-US", "mixed"]
    language = language_map[lang_idx]

    # Scoring bias selection
    bias_options = ["Conservative (moderate)", "Aggressive (aggressive)", "Balanced (balanced)"]
    bias_idx = ask_choice("  Scoring Bias", bias_options, 2)
    bias_map = ["moderate", "aggressive", "balanced"]
    scoring_bias = bias_map[bias_idx]

    # PRO description
    print("\n  Expert Profile Description (briefly describe expert background and characteristics):")
    print("  (Press Enter to use auto-generated description based on above info)")
    pro = ask("  PRO Description")

    # If no PRO provided, generate a basic one
    if not pro:
        pro = f"{name}, {role}, from {region}, specializing in {expertise}. Has rich industry experience and professional background, skilled at analyzing problems from multiple perspectives."

    # Extended profile fields
    print("\n  Extended Persona Fields (optional, press Enter to skip):")

    capability_base = ask("  Capability Base Description (capability_base)")
    behavior_style = ask("  Behavior Style Description (behavior_style)")
    interview_focus = ask("  Interview Focus Direction (interview_focus)")

    print("  Detailed Profile Description (profile, 2-3 paragraphs):")
    print("  (Enter multiple lines, end with empty line)")
    profile_lines = []
    while True:
        line = input("  ").strip()
        if not line:
            break
        profile_lines.append(line)
    profile = "\n".join(profile_lines)

    return {
        "name": name,
        "role": role,
        "org_type": org_type,
        "region": region,
        "expertise": expertise,
        "language": language,
        "scoring_bias": scoring_bias,
        "pro": pro,
        "capability_base": capability_base,
        "behavior_style": behavior_style,
        "interview_focus": interview_focus,
        "profile": profile,
    }


def display_expert_list(experts_data: List[dict], selected_providers: List[str] = None, selected_models: List[str] = None):
    """
    Display a formatted table of experts.

    Args:
        experts_data: List of expert dicts
        selected_providers: Optional list of selected provider names
        selected_models: Optional list of selected model names
    """
    print()
    print(f"{'─'*70}")
    print(f"  {'ID':<4} {'Name':<12} {'Role':<18} {'Provider':<12} {'Model':<15}")
    print(f"{'─'*70}")

    for i, exp in enumerate(experts_data, 1):
        provider_display = selected_providers[i-1] if selected_providers and i <= len(selected_providers) else "[Not Selected]"
        model_display = selected_models[i-1] if selected_models and i <= len(selected_models) else "[Not Selected]"
        # Truncate long fields
        name = exp['name'][:10] + ".." if len(exp['name']) > 10 else exp['name']
        role = exp['role'][:16] + ".." if len(exp['role']) > 16 else exp['role']
        provider = provider_display[:10] + ".." if len(provider_display) > 10 else provider_display
        model = model_display[:13] + ".." if len(model_display) > 13 else model_display

        print(f"  {i:<4} {name:<12} {role:<18} {provider:<12} {model:<15}")
        print(f"       Region: {exp['region']} | Expertise: {exp['expertise']}")
        print(f"       Score: {exp.get('scoring_bias', 'moderate')} | Language: {exp.get('language', 'zh-CN')}")

        # Display PRO summary
        pro = exp.get('pro', '')
        if pro:
            pro_preview = pro[:60] + "..." if len(pro) > 60 else pro
            print(f"       PRO: {pro_preview}")
        print(f"{'─'*70}")


def display_expert_details(experts_data: List[dict], start_index: int = 1):
    """
    Display detailed information for all experts.

    Args:
        experts_data: List of expert dicts
        start_index: Starting index for expert numbering
    """
    print(f"\n{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Expert Details List{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")

    for i, exp in enumerate(experts_data, start_index):
        is_custom = i > len(experts_data)
        marker = f"{Colors.RED} [Custom]{Colors.RESET}" if is_custom else f"{Colors.GREEN} [AI Generated]{Colors.RESET}"

        print(f"\n{Colors.BRIGHT_YELLOW}{'─'*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}  Expert {i}: {exp['name']}{marker}{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}{'─'*70}{Colors.RESET}")

        # Basic Information
        print(f"\n  {Colors.CYAN}[Basic Information]{Colors.RESET}")
        print(f"    Name: {Colors.WHITE}{exp.get('name', 'Unknown')}{Colors.RESET}")
        print(f"    Role: {exp.get('role', 'Unknown')}")
        print(f"    Organization Type: {exp.get('org_type', 'Unknown')}")
        print(f"    Region: {exp.get('region', 'Unknown')}")
        print(f"    Expertise: {exp.get('expertise', 'Unknown')}")
        print(f"    Language: {exp.get('language', 'zh-CN')}")
        print(f"    Scoring Bias: {exp.get('scoring_bias', 'moderate')}")

        # Expert Profile (PRO)
        pro = exp.get('pro', '')
        if pro:
            print(f"\n  {Colors.CYAN}[Expert Profile]{Colors.RESET}")
            # Handle multi-line pro
            pro_lines = pro.split('\n')
            for line in pro_lines:
                if line.strip():
                    print(f"    {line}")

        # Capability Base
        capability_base = exp.get('capability_base', '')
        if capability_base:
            print(f"\n  {Colors.CYAN}[Capability Base]{Colors.RESET}")
            print(f"    {capability_base}")

        # Behavior Style
        behavior_style = exp.get('behavior_style', '')
        if behavior_style:
            print(f"\n  {Colors.CYAN}[Behavior Style]{Colors.RESET}")
            print(f"    {behavior_style}")

        # Interview Focus
        interview_focus = exp.get('interview_focus', '')
        if interview_focus:
            print(f"\n  {Colors.CYAN}[Interview Focus]{Colors.RESET}")
            print(f"    {interview_focus}")

        # Detailed Profile (profile)
        profile = exp.get('profile', '')
        if profile:
            print(f"\n  {Colors.CYAN}[Detailed Profile]{Colors.RESET}")
            profile_lines = profile.split('\n')
            for line in profile_lines:
                if line.strip():
                    print(f"    {line}")

    print(f"\n{Colors.BRIGHT_CYAN}{'='*70}{Colors.RESET}")


def display_model_options(provider: Provider):
    """Display available models for a provider."""
    print(f"\nAvailable Models:")
    for i, model in enumerate(provider.models[:8], 1):
        marker = " *" if model == provider.default_model else ""
        print(f"  {i}. {model}{marker}")
    if len(provider.models) > 8:
        print(f"  ... Total {len(provider.models)}  models")


def run_step3(state: dict) -> dict:
    """
    Run step 3: Expert configuration.

    Flow：
    1. LLM GenerateExpertPanel
    2. User can addCustomExpert
    3. User confirmsExpertList
    4. For eachExpertSelectmodel
    5. Show confirmation table，User confirms or modifies

    Args:
        state: Current state dict

    Returns:
        Updated state dict
    """
    print_step_header()

    providers = state.get("providers", {})

    if not providers:
        print("  [Error] No providers configured，Please complete step 2")
        return state

    project = state.get("project", {})
    if not project:
        print("  [Error] Project info not found，Please complete step 1")
        return state

    print("Expert Panel Generation")
    print()
    print("This step will automatically generate an expert panel using AI based on your complete research project information.")
    print()

    # ============================================================
    # Step 1: Generate experts with LLM
    # ============================================================
    print("=" * 60)
    print("  [Step 1] AI Generate Expert Panel")
    print("=" * 60)
    print()

    expert_count_options = [str(i) for i in range(3, 21)]
    expert_count_choice = questionary.select(
        "Select number of experts to generate",
        choices=expert_count_options,
    ).ask()
    expert_count = int(expert_count_choice) if expert_count_choice else 5

    # Let userSelectuse whichProvider and Modelto generateExpert
    print()
    generation_options = []
    for p in providers.values():
        for model in p.models[:20]:
            generation_options.append(f"{p.name}:{model}")

    print("Select provider and model for generating experts:")
    generation_choice = questionary.select(
        "Select generation model",
        choices=generation_options,
    ).ask()

    if generation_choice:
        parts = generation_choice.split(":", 1)
        gen_provider_name = parts[0]
        gen_model = parts[1] if len(parts) > 1 else generation_choice
    else:
        first_provider = list(providers.values())[0]
        gen_provider_name = first_provider.name
        gen_model = first_provider.default_model

    # Build for generating Provider object（reuseAlreadystructured）
    gen_provider = None
    for p in providers.values():
        if p.name == gen_provider_name:
            gen_provider = p
            break
    if gen_provider is None:
        gen_provider = list(providers.values())[0]
        gen_provider_name = gen_provider.name
        gen_model = gen_provider.default_model

    # Temporarily create an object with only default model andapiinfo Provider object给 generate_experts_with_llm use
    class TempProvider:
        def __init__(self, name, default_model, base_url, api_key, adapter):
            self.name = name
            self.default_model = default_model
            self.base_url = base_url
            self.api_key = api_key
            self.adapter = adapter

    temp_provider = TempProvider(
        name=gen_provider_name,
        default_model=gen_model,
        base_url=gen_provider.base_url,
        api_key=gen_provider.api_key,
        adapter=gen_provider.adapter,
    )

    print(f"\nWill use [{gen_provider_name}] for expert generation")
    print(f"model: {gen_model}")

    generated_experts = generate_experts_with_llm(project, expert_count, temp_provider)

    if not generated_experts:
        print("\n  [Hint] Using default expert configuration")
        generated_experts = [
            {
                "name": "Prof. Zhang Wei",
                "role": "Department Chair of Computer Science",
                "org_type": "University",
                "region": "Beijing",
                "expertise": "Artificial Intelligence and Big Data",
                "language": "zh-CN",
                "scoring_bias": "moderate",
                "pro": "Prof. Zhang Wei, PhD advisor, currently serves as Department Chair of Computer Science at a key university. Graduated from MIT Computer Science, has long been engaged in machine learning and data mining research. Conservative and steady in technology judgment, focusing on implementation feasibility.",
                "capability_base": "15 years of research experience in AI and machine learning, with deep accumulation in data mining and algorithm optimization.",
                "behavior_style": "Data-driven thinking, rigorous and clear logic in expression, tends to analyze problems from technical architecture perspective, cautious about industrialization paths of new technologies.",
                "interview_focus": "Technology feasibility assessment, algorithm limitation analysis, industry implementation challenges.",
                "profile": "Prof. Zhang Wei, PhD advisor, currently serves as Department Chair of Computer Science at a key university. Graduated from MIT Computer Science, has long been engaged in machine learning and data mining research, has led multiple national-level AI research projects, published over 50 papers in top conferences like NeurIPS and ICML. Has served as technical advisor for multiple technology companies, and acted as chief scientist in smart city and medical AI projects, having rich experience in AI technology industrialization applications. Conservative and steady in technology judgment, focusing on implementation feasibility, skilled at analyzing problems from technical architecture perspective. For this research, focuses on technology maturity assessment and matching with practical application scenarios, will provide specific suggestions from algorithm efficiency and engineering implementation perspectives."
            },
            {
                "name": "Dr. Li Ming",
                "role": "Market Research Director",
                "org_type": "Enterprise",
                "region": "Shanghai",
                "expertise": "Market Analysis and Strategy",
                "language": "zh-CN",
                "scoring_bias": "aggressive",
                "pro": "Dr. Li Ming, Market Research Director at a Fortune 500 company, with 15 years of market analysis experience. Expert in consumer behavior research and competitive intelligence analysis, with keen insight into emerging market opportunities.",
                "capability_base": "15 years of market analysis experience, expert in consumer behavior research and competitive intelligence analysis.",
                "behavior_style": "Strong insight, active thinking, tends to analyze problems from market and user perspectives, sensitive to new opportunities.",
                "interview_focus": "Market opportunity assessment, user needs analysis, business model feasibility.",
                "profile": "Dr. Li Ming, Market Research Director at a Fortune 500 company, with 15 years of market analysis experience. MBA from Wharton School, has served as head of market research in multiple multinational companies. Expert in consumer behavior research and competitive intelligence analysis, with keen insight into emerging market opportunities. Past projects cover technology, finance, healthcare and other industries. For this research, will provide unique perspectives from market demand and user acceptance angles, focusing on market potential and competitive barriers of technology products."
            },
            {
                "name": "Wang Fang",
                "role": "Policy Research Office Director",
                "org_type": "Government Agency",
                "region": "Beijing",
                "expertise": "Industrial Policy Research",
                "language": "zh-CN",
                "scoring_bias": "moderate",
                "pro": "Wang Fang, Director of Policy Research Office at the State Council Development Research Center, long engaged in industrial policy research and macroeconomic analysis. Participated in multiple national-level policy formulations.",
                "capability_base": "Background in industrial policy research and macroeconomic analysis, participated in multiple national-level policy formulations.",
                "behavior_style": "Macro perspective, cautious analysis, tends to evaluate problems from policy and regulatory perspectives.",
                "interview_focus": "Policy environment analysis, regulatory trends, compliance requirements.",
                "profile": "Wang Fang, Director of Policy Research Office at the State Council Development Research Center, long engaged in industrial policy research and macroeconomic analysis. PhD from Peking University School of Economics. Participated in multiple national-level policy formulations, with deep understanding of industrial policy evolution. Published over 30 papers in national-level journals. For this research, will provide professional opinions from policy support and regulatory perspectives, focusing on policy risks and compliance requirements."
            },
        ]

    # ============================================================
    # Step 1b: Display generated experts immediately
    # ============================================================
    print("\n" + "=" * 70)
    print("  [Generated] AI Expert Panel")
    print("=" * 70)
    display_expert_details(generated_experts)

    # ============================================================
    # Step 2: Ask about adding custom experts
    # ============================================================
    print("\n" + "=" * 60)
    print("  [Step 2] Add Custom Expert (Optional)")
    print("=" * 60)
    print()
    print("You can add custom experts as needed, for example:")
    print("  - Real experts you know")
    print("  - Industry consultants in specific fields")
    print("  - Other experts you want to include")

    custom_experts = []
    # Issue 2 fix: [y/N] should default to y (Enter=yes)
    if questionary.confirm("\nDo you need to add custom experts", default=False).ask():
        print("\nAdd custom expert (enter empty name to finish):")

        while True:
            # Ask if user wants LLM assistance to supplement
            use_llm_assist = questionary.confirm(
                "Do you need AI assistance to supplement expert information",
                default=True
            ).ask()

            if use_llm_assist:
                # Use LLM to generate a custom expert based on user's basic input
                print("\n  Please provide basic expert information, AI will help supplement complete information")
                name = ask("  Name")
                if not name:
                    print("  [Skip] Not 输入Name")
                    break

                role = ask("  Role/Role (e.g., Professor, Director, Analyst)", "Expert")
                org_type = ask("  Organization Type", "University")
                region = ask("  Region", "Unknown")
                expertise = ask("  Expertise", "通用field")

                # Generate full expert profile with LLM assist
                print(f"\n  Using AI to generate complete expert information...")
                assist_prompt = f"""请为以下ExpertGenerate完整资料：

Name: {name}
Role: {role}
Organization Type: {org_type}
Region: {region}
Expertise: {expertise}

请Generate包含以下字段的完整Expert信息：
- pro: 简要Expert画像（50-100字）
- capability_base: Capability Base Description
- behavior_style: Behavior Style Description
- interview_focus: Interview Focus Direction
- profile: Detailed Persona Description（2-3段）

Please JSONreturn in format。"""

                try:
                    from llm import call_llm
                    response = call_llm(
                        base_url=gen_provider.base_url,
                        api_key=gen_provider.api_key,
                        model=gen_model,
                        prompt=assist_prompt,
                        system_prompt="You are a professional research methodology expert specializing in Delphi expert persona design.",
                        temperature=0.8,
                    )
                    import re
                    json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', response)
                    if json_match:
                        import json as json_lib
                        try:
                            generated = json_lib.loads(json_match.group())
                            if isinstance(generated, dict):
                                custom = {
                                    "name": name,
                                    "role": role,
                                    "org_type": org_type,
                                    "region": region,
                                    "expertise": expertise,
                                    "language": "zh-CN",
                                    "scoring_bias": "moderate",
                                    "pro": generated.get("pro", f"{name}，{role}，from{region}，specializing in{expertise}field。"),
                                    "capability_base": generated.get("capability_base", ""),
                                    "behavior_style": generated.get("behavior_style", ""),
                                    "interview_focus": generated.get("interview_focus", ""),
                                    "profile": generated.get("profile", ""),
                                }
                            else:
                                custom = None
                        except json_lib.JSONDecodeError:
                            custom = None
                except Exception:
                    custom = None

                if custom is None:
                    # Fallback to basic info if LLM fails
                    custom = {
                        "name": name,
                        "role": role,
                        "org_type": org_type,
                        "region": region,
                        "expertise": expertise,
                        "language": "zh-CN",
                        "scoring_bias": "moderate",
                        "pro": f"{name}，{role}，from{region}，specializing in{expertise}field。",
                        "capability_base": "",
                        "behavior_style": "",
                        "interview_focus": "",
                        "profile": "",
                    }

                custom_experts.append(custom)
                print(f"  [Added] {name} (AI-assisted generation)")

            else:
                custom = collect_custom_expert()
                if custom is None:
                    break
                custom_experts.append(custom)

            # Issue 2 fix: [y/N] default to y
            if not questionary.confirm("\nContinue adding more custom experts", default=False).ask():
                break

    # Combine all experts
    all_experts_data = generated_experts + custom_experts

    # ============================================================
    # Step 3: Display all experts for review
    # ============================================================
    print("\n" + "=" * 70)
    print("  [Expert List Preview] All Experts")
    print("=" * 70)
    display_expert_details(all_experts_data)

    # ============================================================
    # Step 4: Review and confirm expert list with add/modify/delete
    # ============================================================
    def rebuild_content_lines(exp_list, gen_count):
        """Rebuild the content lines for display."""
        lines = []
        lines.append(f"{Colors.CYAN}Current Expert List ({len(exp_list)}  total):{Colors.RESET}")
        for i, exp in enumerate(exp_list, 1):
            is_custom = i > gen_count
            marker = f"{Colors.RED} [Custom]{Colors.RESET}" if is_custom else f"{Colors.GREEN} [AI Generated]{Colors.RESET}"
            lines.append(f"{Colors.WHITE}{i:>2}. {exp['name']}{marker}{Colors.RESET}")
            lines.append(f"    Role: {exp['role']} | 机构: {exp['org_type']}")
        return lines

    def show_review_box(exp_list, gen_count):
        """Show the review box with current expert list."""
        content_lines = rebuild_content_lines(exp_list, gen_count)
        box_width = 70
        print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}       Please ReviewExpertList       {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        for line in content_lines:
            padding = box_width - len(line) - 4
            if padding < 0:
                padding = 0
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm and continue{Colors.RESET}{' ' * (box_width - 36)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.CYAN}  2{Colors.RESET} - {Colors.CYAN}View Expert Details{Colors.RESET}{' ' * (box_width - 32)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.MAGENTA}  3{Colors.RESET} - {Colors.MAGENTA}Add Expert{Colors.RESET}{' ' * (box_width - 24)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BLUE}  4{Colors.RESET} - {Colors.BLUE}Modify Expert{Colors.RESET}{' ' * (box_width - 24)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.RED}  5{Colors.RESET} - {Colors.RED}Delete Expert{Colors.RESET}{' ' * (box_width - 24)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.YELLOW}  6{Colors.RESET} - {Colors.YELLOW}Regenerate Expert Panel{Colors.RESET}{' ' * (box_width - 32)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")

    def show_simple_review_box(exp_list, gen_count):
        """Show simplified review box after viewing details."""
        content_lines = rebuild_content_lines(exp_list, gen_count)
        box_width = 70
        print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}       Please Review AgainExpertList       {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        for line in content_lines:
            padding = box_width - len(line) - 4
            if padding < 0:
                padding = 0
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm and continue{Colors.RESET}{' ' * (box_width - 36)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.MAGENTA}  2{Colors.RESET} - {Colors.MAGENTA}Add Expert{Colors.RESET}{' ' * (box_width - 24)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BLUE}  3{Colors.RESET} - {Colors.BLUE}Modify Expert{Colors.RESET}{' ' * (box_width - 24)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.RED}  4{Colors.RESET} - {Colors.RED}Delete Expert{Colors.RESET}{' ' * (box_width - 24)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.YELLOW}  5{Colors.RESET} - {Colors.YELLOW}Regenerate Expert Panel{Colors.RESET}{' ' * (box_width - 32)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")

    # Main review loop
    while True:
        show_review_box(all_experts_data, len(generated_experts))

        choice = questionary.select(
            "Select Action",
            choices=[
                "Confirm and continue",
                "View Expert Details",
                "Add Expert",
                "Modify Expert",
                "Delete Expert",
                "Regenerate Expert Panel",
            ],
        ).ask()

        # Handle "View Expert Details"
        if choice == "View Expert Details":
            display_expert_details(all_experts_data)
            show_simple_review_box(all_experts_data, len(generated_experts))
            sub_choice = questionary.select(
                "Select Action",
                choices=[
                    "Confirm and continue",
                    "Add Expert",
                    "Modify Expert",
                    "Delete Expert",
                    "Regenerate Expert Panel",
                ],
            ).ask()
            if sub_choice == "Confirm and continue":
                choice = sub_choice
            elif sub_choice == "Regenerate Expert Panel":
                choice = sub_choice
            else:
                choice = sub_choice
                continue

        # Handle "Add Expert"
        if choice == "Add Expert":
            print("\n" + "=" * 60)
            print("  [Add Expert]")
            print("=" * 60)

            use_llm = questionary.confirm("是否需要 AI 辅助GenerateExpert信息", default=True).ask()

            if use_llm:
                print("\n  请提供Expert的基本信息：")
                name = ask("  Name")
                if not name:
                    print("  [Skip]")
                    continue
                role = ask("  Role/角色", "Expert")
                org_type = ask("  Organization Type", "University")
                region = ask("  Region", "Unknown")
                expertise = ask("  Expertise", "通用field")

                print(f"\n  Using AI to generate complete expert information...")
                try:
                    from llm import call_llm
                    assist_prompt = f"""请为以下ExpertGenerate完整资料：

Name: {name}
Role: {role}
Organization Type: {org_type}
Region: {region}
Expertise: {expertise}

请Generate包含以下字段的完整Expert信息：
- pro: 简要Expert画像（50-100字）
- capability_base: Capability Base Description
- behavior_style: Behavior Style Description
- interview_focus: Interview Focus Direction
- profile: Detailed Persona Description（2-3段）

Please JSONreturn in format。"""
                    response = call_llm(
                        base_url=gen_provider.base_url,
                        api_key=gen_provider.api_key,
                        model=gen_model,
                        prompt=assist_prompt,
                        system_prompt="You are a professional research methodology expert specializing in Delphi expert persona design.",
                        temperature=0.8,
                    )
                    import re
                    import json as json_lib
                    json_match = re.search(r'\{[\s\S]*\}', response)
                    if json_match:
                        generated = json_lib.loads(json_match.group())
                        new_expert = {
                            "name": name,
                            "role": role,
                            "org_type": org_type,
                            "region": region,
                            "expertise": expertise,
                            "language": "zh-CN",
                            "scoring_bias": "moderate",
                            "pro": generated.get("pro", ""),
                            "capability_base": generated.get("capability_base", ""),
                            "behavior_style": generated.get("behavior_style", ""),
                            "interview_focus": generated.get("interview_focus", ""),
                            "profile": generated.get("profile", ""),
                        }
                    else:
                        new_expert = {
                            "name": name,
                            "role": role,
                            "org_type": org_type,
                            "region": region,
                            "expertise": expertise,
                            "language": "zh-CN",
                            "scoring_bias": "moderate",
                            "pro": f"{name}，{role}，from{region}，specializing in{expertise}field。",
                            "capability_base": "",
                            "behavior_style": "",
                            "interview_focus": "",
                            "profile": "",
                        }
                except Exception:
                    new_expert = {
                        "name": name,
                        "role": role,
                        "org_type": org_type,
                        "region": region,
                        "expertise": expertise,
                        "language": "zh-CN",
                        "scoring_bias": "moderate",
                        "pro": f"{name}，{role}，from{region}，specializing in{expertise}field。",
                        "capability_base": "",
                        "behavior_style": "",
                        "interview_focus": "",
                        "profile": "",
                    }
                print(f"  [Added] {new_expert['name']} (AI辅助)")
            else:
                new_expert = collect_custom_expert()
                if new_expert is None:
                    continue
                print(f"  [Added] {new_expert['name']} (手动)")

            all_experts_data.append(new_expert)
            print(f"\n  当前Expert总数: {len(all_experts_data)} 位")
            continue

        # Handle "Modify Expert"
        if choice == "Modify Expert":
            print("\n" + "=" * 60)
            print("  [Modify Expert]")
            print("=" * 60)

            if not all_experts_data:
                print("  [Error] No experts available to modify")
                continue

            # Build expert selection list
            expert_choices = []
            for i, exp in enumerate(all_experts_data, 1):
                is_custom = i > len(generated_experts)
                marker = "[Custom]" if is_custom else "[AI Generated]"
                expert_choices.append(f"{i}. {exp['name']} {marker}")

            selected_name = questionary.select(
                "Select expert to modify",
                choices=expert_choices,
            ).ask()

            if not selected_name:
                continue

            expert_idx = int(selected_name.split(".")[0]) - 1
            exp_to_modify = all_experts_data[expert_idx]

            print(f"\n  Current Expert: {exp_to_modify['name']}")
            display_expert_details([exp_to_modify], start_index=expert_idx + 1)

            # Ask if user wants LLM assistance
            use_llm = questionary.confirm(
                "是否需要 AI 辅助Modify Expert信息",
                default=True
            ).ask()

            if use_llm:
                modified = modify_expert_with_llm(exp_to_modify, gen_provider, gen_model)
            else:
                # Manual modification - let user select which fields to change
                print("\n  Please directly enter new expert info (leave blank to keep unchanged):")
                modified = exp_to_modify.copy()

                name = ask(f"  Name [{exp_to_modify.get('name', '')}]")
                if name:
                    modified['name'] = name
                role = ask(f"  Role [{exp_to_modify.get('role', '')}]")
                if role:
                    modified['role'] = role
                org_type = ask(f"  Organization Type [{exp_to_modify.get('org_type', '')}]")
                if org_type:
                    modified['org_type'] = org_type
                region = ask(f"  Region [{exp_to_modify.get('region', '')}]")
                if region:
                    modified['region'] = region
                expertise = ask(f"  Expertise [{exp_to_modify.get('expertise', '')}]")
                if expertise:
                    modified['expertise'] = expertise

            all_experts_data[expert_idx] = modified
            print(f"\n  [AlreadyModify] {modified['name']}")
            continue

        # Handle "Delete Expert"
        if choice == "Delete Expert":
            print("\n" + "=" * 60)
            print("  [Delete Expert]")
            print("=" * 60)

            if not all_experts_data:
                print("  [Error] No experts available to delete")
                continue

            # Build expert selection list (multi-select)
            expert_choices = []
            for i, exp in enumerate(all_experts_data, 1):
                is_custom = i > len(generated_experts)
                marker = "[Custom]" if is_custom else "[AI Generated]"
                expert_choices.append(f"{exp['name']} {marker}")

            print("  Select experts to delete (Space to select, Enter to confirm):")
            selected = questionary.checkbox(
                "Select expert to delete",
                choices=expert_choices,
                validate=lambda s: len(s) > 0 or "Please select at least one expert"
            ).ask()

            if not selected:
                continue

            # Confirm deletion
            print(f"\n  Confirm Delete以下 {len(selected)}  experts:")
            for name in selected:
                print(f"    - {name}")

            confirm = questionary.confirm("Confirm Delete", default=False).ask()
            if not confirm:
                print("  [Cancelled] No experts deleted")
                continue

            # Remove selected experts
            selected_names = [s.split(" [")[0] for s in selected]
            all_experts_data = [exp for exp in all_experts_data if exp['name'] not in selected_names]
            print(f"\n  [Deleted] {len(selected)} 位Expert")
            print(f"  Remaining experts total: {len(all_experts_data)} 位")

            if len(all_experts_data) < 3:
                print(f"  {Colors.YELLOW}[Warning] Recommended at least 3 experts{Colors.RESET}")
            continue

        # Handle "Regenerate Expert Panel"
        if choice == "Regenerate Expert Panel" or choice is None:
            print("\n  [Hint] 正在Regenerate Expert Panel...")
            return run_step3(state)

        # Handle "Confirm and continue"
        if choice == "Confirm and continue":
            if len(all_experts_data) < 3:
                print(f"  {Colors.YELLOW}[Warning] Recommended at least 3 experts，Currently only {len(all_experts_data)} 位{Colors.RESET}")
                confirm_min = questionary.confirm("Continue anyway", default=False).ask()
                if not confirm_min:
                    continue
            break

    # ============================================================
    # Step 5: Select provider and model for each expert
    # ============================================================
    print("\n" + "=" * 60)
    print("  [[Step 5] Select Provider and Model for Each Expert")
    print("=" * 60)
    print()

    # 构建 provider:model 选项List（每个provider的所有可用model）
    # questionary 不支持 ANSI 颜色码，只用纯文字选项
    provider_model_options = []
    provider_model_map = {}  # option -> (provider_name, model_name)
    model_label_map = {}  # option -> "✓ Recommended" / "⚠ May truncate" / "✗ Not suitable"

    for p in providers.values():
        # 支持 Provider object或 dict（从 JSON 加载时是 dict）
        provider_name = p.name if hasattr(p, 'name') else p.get('name', 'Unknown')
        provider_models = p.models if hasattr(p, 'models') else p.get('models', [])
        model_capabilities = p.model_capabilities if hasattr(p, 'model_capabilities') else p.get('model_capabilities', {})

        for model in provider_models[:20]:  # 限制每个provider最多20 models
            max_tokens = model_capabilities.get(model, 0) if isinstance(model_capabilities, dict) else 0
            label, _ = get_max_tokens_label(max_tokens)
            # questionary 只接受纯文字，不能带 ANSI 转义码
            option = f"{provider_name}:{model}"
            provider_model_options.append(option)
            provider_model_map[option] = (provider_name, model)
            model_label_map[option] = label

    if not provider_model_options:
        print("  [Error] 没有任何Already配置的服务商model，请返回步骤2配置")
        return state

    print(f"Configured provider model options: {len(provider_model_options)} 个")
    print(f"{Colors.GREEN}✓ Recommended{Colors.RESET} = 支持深度访谈 | {Colors.YELLOW}⚠ May truncate{Colors.RESET} = 基本可用 | {Colors.RED}✗ Not suitable{Colors.RESET} = Not recommended")
    print()

    selected_providers = []
    selected_models = []
    for i, exp in enumerate(all_experts_data, 1):
        is_custom = i > len(generated_experts)
        marker = " [Custom]" if is_custom else " [AI Generated]"

        print(f"\nExpert {i}: {exp['name']}{marker}")
        print(f"  Role: {exp['role']} | 机构: {exp['org_type']}")

        # 直接Select provider:model
        selected = questionary.select(
            "Select Provider and Model",
            choices=provider_model_options,
        ).ask()
        if selected and selected in provider_model_map:
            selected_provider_name, selected_model = provider_model_map[selected]
        elif selected:
            # Fallback parsing for compatibility
            parts = selected.split(":", 1)
            selected_provider_name = parts[0]
            # Remove the color codes and extra info to get model name
            selected_model = parts[1].split(" ")[0] if len(parts) > 1 else selected
        else:
            selected_provider_name = providers[list(providers.keys())[0]].name
            selected_model = providers[list(providers.keys())[0]].models[0] if providers[list(providers.keys())[0]].models else "default"

        selected_providers.append(selected_provider_name)
        selected_models.append(selected_model)
        # 显示Recommended标签
        label = model_label_map.get(selected, "")
        label_display = f" {label}" if label else ""
        print(f"  Selected: {selected_provider_name} / {selected_model}{label_display}")

    # ============================================================
    # Step 6: Confirmation table
    # ============================================================
    # 构建确认内容
    content_lines = []
    content_lines.append(f"{Colors.CYAN}以下是每位Expert的Provider and Model配置，请确认：{Colors.RESET}")
    content_lines.append("")
    content_lines.append(f"{Colors.WHITE}  {'ID':<4} {'Name':<10} {'服务商':<12} {'model':<18}{Colors.RESET}")
    content_lines.append(f"{Colors.YELLOW}  {'─'*65}{Colors.RESET}")

    for i, exp in enumerate(all_experts_data, 1):
        is_custom = i > len(generated_experts)
        marker = f"{Colors.RED} [Custom]{Colors.RESET}" if is_custom else f"{Colors.GREEN} [AI Generated]{Colors.RESET}"
        name = exp['name'][:8] + ".." if len(exp['name']) > 8 else exp['name']
        provider_name = selected_providers[i-1][:10] + ".." if len(selected_providers[i-1]) > 10 else selected_providers[i-1]
        model = selected_models[i-1][:16] + ".." if len(selected_models[i-1]) > 16 else selected_models[i-1]
        content_lines.append(f"  {Colors.WHITE}{i:<4} {name:<10} {provider_name:<12} {model:<18}{marker}{Colors.RESET}")

    content_lines.append(f"{Colors.YELLOW}  {'─'*65}{Colors.RESET}")

    # 打印黄色方框
    box_width = 75
    print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}   Confirm Expert and Model Configuration   {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")

    for line in content_lines:
        padding = box_width - len(line) - 4
        if padding < 0:
            padding = 0
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

    print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm configuration, continue to next step{Colors.RESET}{' ' * (box_width - 34)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.YELLOW}  2{Colors.RESET} - {Colors.YELLOW}Modify a specific expert's model{Colors.RESET}{' ' * (box_width - 36)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.CYAN}  3{Colors.RESET} - {Colors.CYAN}Reselect all models{Colors.RESET}{' ' * (box_width - 32)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")

    choice = questionary.select(
        "Select Action",
        choices=["Confirm configuration, continue to next step", "Modify a specific expert's model", "Reselect all models"],
    ).ask()

    if choice == "Modify a specific expert's model":
        # Modify specific expert's provider and model using simplified format
        while True:
            # use交互式SelectExpert
            expert_names = [f"{i+1}. {exp['name']} ({selected_providers[i]} / {selected_models[i]})" for i, exp in enumerate(all_experts_data)]
            expert_names.append("0. Finish editing")
            selected = questionary.select(
                "Select expert to modify",
                choices=expert_names,
            ).ask()
            if selected == "0. Finish editing" or selected is None:
                break

            # 解析Select的Expert编号
            expert_idx = expert_names.index(selected)
            exp = all_experts_data[expert_idx]

            print(f"\nExpert {expert_idx + 1}: {exp['name']}")

            # 直接Select新的 provider:model
            new_selection = questionary.select(
                "Select new provider and model",
                choices=provider_model_options,
            ).ask()
            if new_selection and new_selection in provider_model_map:
                selected_providers[expert_idx], selected_models[expert_idx] = provider_model_map[new_selection]
                print(f"  [Updated] Expert {expert_idx + 1} → {selected_providers[expert_idx]} / {selected_models[expert_idx]}")
            elif new_selection:
                parts = new_selection.split(":", 1)
                selected_providers[expert_idx] = parts[0]
                selected_models[expert_idx] = parts[1].split(" ")[0] if len(parts) > 1 else new_selection
                print(f"  [Updated] Expert {expert_idx + 1} → {selected_providers[expert_idx]} / {selected_models[expert_idx]}")

        # Show updated table
        print("\n" + "=" * 60)
        print("  Updated configuration")
        print("=" * 60)
        print(f"{'─'*80}")
        print(f"  {'ID':<4} {'Name':<10} {'服务商':<12} {'model':<18}")
        print(f"{'─'*80}")
        for i, exp in enumerate(all_experts_data, 1):
            is_custom = i > len(generated_experts)
            marker = " [Custom]" if is_custom else " [AI Generated]"
            name = exp['name'][:8] + ".." if len(exp['name']) > 8 else exp['name']
            provider_name = selected_providers[i-1][:10] + ".." if len(selected_providers[i-1]) > 10 else selected_providers[i-1]
            model = selected_models[i-1][:16] + ".." if len(selected_models[i-1]) > 16 else selected_models[i-1]
            print(f"  {i:<4} {name:<10} {provider_name:<12} {model:<18}{marker}")
        print(f"{'─'*80}")

        if not questionary.confirm("\nConfirm updated configuration", default=True).ask():
            return state

    elif choice == "Reselect all models":
        # Reselect all providers and models using simplified format
        print("\nReselect provider and model for all experts:")
        selected_providers = []
        selected_models = []
        for i, exp in enumerate(all_experts_data, 1):
            is_custom = i > len(generated_experts)
            marker = " [Custom]" if is_custom else " [AI Generated]"

            print(f"\nExpert {i}: {exp['name']}{marker}")

            # 直接Select provider:model
            new_selection = questionary.select(
                "Select Provider and Model",
                choices=provider_model_options,
            ).ask()
            if new_selection and new_selection in provider_model_map:
                p_name, m_name = provider_model_map[new_selection]
                selected_providers.append(p_name)
                selected_models.append(m_name)
            elif new_selection:
                parts = new_selection.split(":", 1)
                selected_providers.append(parts[0])
                selected_models.append(parts[1].split(" ")[0] if len(parts) > 1 else new_selection)
            else:
                first_provider = list(providers.values())[0]
                selected_providers.append(first_provider.name)
                selected_models.append(first_provider.models[0] if first_provider.models else "default")
            label = model_label_map.get(new_selection, "")
            label_display = f" {label}" if label else ""
            print(f"  Selected: {selected_providers[-1]} / {selected_models[-1]}{label_display}")

    # ============================================================
    # Create Expert objects and save
    # ============================================================
    experts: List[Expert] = []
    for i, (exp_data, provider_name, model) in enumerate(zip(all_experts_data, selected_providers, selected_models), 1):
        # 根据Select的服务商名称找到对应的 Provider object
        provider_obj = None
        provider_key = ""
        for k, p in providers.items():
            if p.name == provider_name:
                provider_obj = p
                provider_key = k
                break

        if provider_obj is None:
            provider_obj = list(providers.values())[0]
            provider_key = list(providers.keys())[0]

        expert = Expert(
            id=f"E{i:02d}",
            name=exp_data["name"],
            role=exp_data["role"],
            org_type=exp_data["org_type"],
            region=exp_data["region"],
            expertise=exp_data["expertise"],
            language=exp_data.get("language", "zh-CN"),
            scoring_bias=exp_data.get("scoring_bias", "moderate"),
            enabled=True,
            provider=provider_key,
            provider_name=provider_name,
            model=model,
            api_key=provider_obj.api_key,
            base_url=provider_obj.base_url,
            adapter=provider_obj.adapter,
            pro=exp_data.get("pro", ""),
            capability_base=exp_data.get("capability_base", ""),
            behavior_style=exp_data.get("behavior_style", ""),
            interview_focus=exp_data.get("interview_focus", ""),
            profile=exp_data.get("profile", ""),
        )
        experts.append(expert)

    state["experts"] = experts

    # Save to run directory
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / state.get("run_id", "")))
    save_json(run_dir / "experts.json", {
        "experts_count": len(experts),
        "ai_generated_count": len(generated_experts),
        "custom_count": len(custom_experts),
        "experts": [e.to_dict() for e in experts]
    })

    if len(experts) < 3:
        print(f"\n  [Warning] Recommended at least 3 experts，Currently only {len(experts)} 位")

    print("\n" + "=" * 60)
    print("  Expert Configuration Complete!")
    print("=" * 60)
    print(f"\n  AI Generated Experts: {len(generated_experts)} 位")
    print(f"  Custom Experts: {len(custom_experts)} 位")
    print(f"  Total Experts: {len(experts)} 位")
    print(f"\n  Provider and Model configuration for each expert:")
    for i, exp in enumerate(experts, 1):
        print(f"    E{i:02d} | {exp.name:<10} | {exp.provider_name:<12} | {exp.model}")
    print(f"\n  Each expert has a detailed PRO profile for subsequent Delphi analysis.")

    return state
