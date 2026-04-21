"""
Step 4: Rounds Configuration & Interview Framework
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
import questionary
from models import RoundsConfig, ScoringDimension, Expert
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)


# ============================================================================
# JSONL 增量备份机制 - 5个工具函数
# ============================================================================

def _append_to_jsonl(jsonl_path: Path, data: dict) -> None:
    """
    追加单条记录到 JSONL，写入后 fsync 确保落盘。

    Args:
        jsonl_path: JSONL 文件路径
        data: 要写入的数据字典
    """
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def _check_jsonl_status(jsonl_path: Path) -> dict:
    """
    检查 JSONL 状态，返回状态信息。

    Returns:
        dict: {
            'exists': bool,      # 文件是否存在
            'turns': int,       # 已完成的 turn 数量
            'last_turn': dict,   # 最后一条记录
            'is_complete': bool  # 是否已完成（最后一条 is_closing=True 或 status=completed）
        }
    """
    if not jsonl_path.exists():
        return {'exists': False, 'turns': 0, 'last_turn': None, 'is_complete': False}

    records = _load_records_from_jsonl(jsonl_path)
    if not records:
        return {'exists': True, 'turns': 0, 'last_turn': None, 'is_complete': False}

    turns = len(records)
    last_turn = records[-1] if records else None

    # 判断是否完成：最后一个 turn 的 is_closing=True
    is_complete = last_turn.get('is_closing', False) if last_turn else False

    return {
        'exists': True,
        'turns': turns,
        'last_turn': last_turn,
        'is_complete': is_complete
    }


def _load_records_from_jsonl(jsonl_path: Path) -> list:
    """
    从 JSONL 恢复已完成的 turns，跳过解析失败行。

    Args:
        jsonl_path: JSONL 文件路径

    Returns:
        list: 解析成功的记录列表
    """
    records = []
    if not jsonl_path.exists():
        return records

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 跳过损坏行
    return records


def _cleanup_jsonl(jsonl_path: Path) -> None:
    """
    访谈完成后删除 JSONL（数据已转换到 interview_records.json）。

    Args:
        jsonl_path: JSONL 文件路径
    """
    if jsonl_path.exists():
        jsonl_path.unlink()


def _recover_conversation_from_jsonl(jsonl_path: Path) -> Tuple[list, list, int]:
    """
    从 JSONL 恢复 conversation_history 和 qa_pairs。

    Args:
        jsonl_path: JSONL 文件路径

    Returns:
        Tuple[list, list, int]:
            - conversation_history: 用于 LLM 对话的上下文
            - qa_pairs: 完整的问答对列表
            - last_turn_number: 最后一个 turn 的编号
    """
    records = _load_records_from_jsonl(jsonl_path)

    if not records:
        return [], [], 0

    # 构建 conversation_history（用于 LLM 对话）
    conversation_history = []
    for r in records:
        conversation_history.append({
            'question': r.get('question', ''),
            'answer': r.get('answer', ''),
            'topic': r.get('topic', '')
        })

    # qa_pairs 保持原样
    qa_pairs = records.copy()

    last_turn_number = records[-1].get('turn', 0) if records else 0

    return conversation_history, qa_pairs, last_turn_number


# ============================================================================
# 原有函数
# ============================================================================

def interactive_select(title: str, items: List[str], multi_select: bool = False) -> List[int]:
    """
    Interactive selection function with arrow key navigation.
    """
    if not items:
        return []

    print(f"\n{title}")

    if multi_select:
        selected = questionary.checkbox(
            'Use arrow keys to move, space to select, enter to confirm',
            choices=items,
            validate=lambda s: len(s) > 0 or "Please select at least one item"
        ).ask()
        if selected is None:
            return []
        return [items.index(s) for s in selected if s in items]
    else:
        selected = questionary.select(
            'Use arrow keys to move, enter to confirm',
            choices=items,
        ).ask()
        if selected is None:
            return []
        return [items.index(selected)]


def print_step_header():
    """Print step 4 header."""
    print()
    print("-" * 60)
    print("  Step 4/8: Interview Framework & Round Configuration")
    print("-" * 60)
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


def ask_float(prompt: str, default: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
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


def ask_integer(prompt: str, default: int, min_val: int, max_val: int, show_bold_red: bool = True) -> int:
    """Ask user for integer input with validation.

    Args:
        prompt: The question to ask
        default: Default value
        min_val: Minimum allowed value (must be >= 1)
        max_val: Maximum allowed value
        show_bold_red: If True, show numbers in prompt with bold red color

    Returns:
        Validated integer between min_val and max_val
    """
    # Build prompt with colored numbers if requested
    if show_bold_red:
        colored_prompt = f"{prompt} {Colors.BRIGHT_RED}{Colors.BOLD}[{min_val}-{max_val}]{Colors.RESET}(默认 {Colors.BRIGHT_RED}{Colors.BOLD}{default}{Colors.RESET}): "
    else:
        colored_prompt = f"{prompt} [{min_val}-{max_val}](默认 {default}): "

    while True:
        response = input(colored_prompt).strip()
        if not response:
            # Empty input - use default
            return default

        # Check if input contains decimal point
        if '.' in response:
            print(f"  {Colors.RED}Error: Must be an integer, cannot contain decimal points{Colors.RESET}")
            continue

        try:
            value = int(response)
            if value < min_val:
                print(f"  {Colors.RED}Error: Cannot be less than {min_val}{Colors.RESET}")
                continue
            if value > max_val:
                print(f"  {Colors.RED}Error: Cannot be greater than {max_val}{Colors.RESET}")
                continue
            return value
        except ValueError:
            print(f"  {Colors.RED}Error: Invalid input '{response}', please enter an integer{Colors.RESET}")


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
    print(f"  [Saved] {filepath}")


def build_interview_framework_prompt(project: dict) -> str:
    """Build prompt for LLM to generate interview framework organized by dimensions."""
    framework_name = project.get('framework', '')
    research_questions = project.get("research_questions", [])

    # Detect if this is a dimension-based framework (e.g., 7P, 4C, etc.)
    # Extract dimension names if present in research_questions or framework
    dimension_hints = ""
    if framework_name:
        # Common framework patterns
        framework_upper = framework_name.upper()
        if '7P' in framework_upper:
            dimension_hints = """
[Detected Framework] 7P Marketing Framework
Dimensions include: Product, Price, Place, Promotion, People, Process, Physical Evidence
Each dimension should have 3 sub-questions, progressing from cognition to analysis to convergence."""
        elif '4P' in framework_upper:
            dimension_hints = """
[Detected Framework] 4P Marketing Framework
Dimensions include: Product, Price, Place, Promotion
Each dimension should have 3 sub-questions, progressing from cognition to analysis to convergence."""
        elif 'PEST' in framework_upper:
            dimension_hints = """
[Detected Framework] PEST Analysis Framework
Dimensions include: Political, Economic, Social, Technological
Each dimension should have 3 sub-questions, progressing from cognition to analysis to convergence."""
        elif 'SWOT' in framework_upper:
            dimension_hints = """
[Detected Framework] SWOT Analysis Framework
Dimensions include: Strengths, Weaknesses, Opportunities, Threats
Each dimension should have 3 sub-questions, progressing from cognition to analysis to convergence."""
        elif '5W' in framework_upper:
            dimension_hints = """
[Detected Framework] 5W Framework
Dimensions include: What, Why, Who, When, How
Each dimension should have 3 sub-questions, progressing from cognition to analysis to convergence."""
        else:
            dimension_hints = f"""
[Detected Framework] {framework_name}
Please organize interview questions according to the dimensions of this framework, 3 sub-questions per dimension."""

    questions_text = "\n".join([
        f"{i+1}. {q}"
        for i, q in enumerate(research_questions)
    ]) if research_questions else "(No specific research questions, please design based on the research topic)"

    prompt = f"""You are a research methodology expert. Please design a Delphi method interview framework for the following research project.

## Research Project Information

[Research Topic] {project.get('title', 'Unknown')}
[Analysis Framework] {project.get('framework', 'Unknown')}
[Research Background]
{project.get('background', 'Unknown')}
[Research Purpose]
{project.get('purpose', 'Unknown')}
[Research Boundaries/Scope]
{project.get('boundaries', 'Unknown')}

[Research Questions (from Step 1)]
{questions_text}
{dimension_hints}

## Interview Framework Design Requirements

**Core Principle**: The interview framework should be organized by dimensions, not as a simple list of questions.

### 1. Dimension Structure (Required)
- Design 3 questions under each dimension, forming a progression from cognition to analysis to convergence:
  - **Cognition-level questions**: Understand the expert's basic recognition and understanding of the dimension
  - **Analysis-level questions**: Guide experts to conduct in-depth analysis and causal discussion
  - **Convergence-level questions**: Encourage experts to form conclusions or priority judgments

### 2. Question Design Standards
- Questions under each dimension should have a logical progression
- Cognition-level question example: "What role do you think [Dimension X] plays in the research?"
- Analysis-level question example: "What are the key factors affecting [Dimension X]? What is the relationship between them?"
- Convergence-level question example: "Among the factors above, which 2-3 are most important? Why?"

### 3. Question Count Calculation
- If a framework has N dimensions, with 3 questions per dimension, total questions = N x 3
- Example: 7P framework -> 21 questions; 4P framework -> 12 questions

### 4. Special Question Types
- **Opening引导问题** (1-2): Used to build consensus and create interview atmosphere, not counted toward dimensions
- **Closing questions** (1-2): Used to supplement missed viewpoints, not counted toward dimensions

## Output Format

Please return in JSON format:
{{
  "framework_title": "Interview Framework Title",
  "introduction": "Opening introduction",
  "dimensions": [
    {{
      "id": "D1",
      "name": "Dimension name (e.g., Product)",
      "description": "Dimension description",
      "questions": [
        {{
          "id": "D1-Q1",
          "level": "cognition/analysis/convergence",
          "level_name": "Cognition/Analysis/Convergence",
          "question": "Question content",
          "purpose": "Question purpose"
        }},
        {{
          "id": "D1-Q2",
          "level": "analysis",
          "level_name": "Analysis",
          "question": "Question content",
          "purpose": "Question purpose"
        }},
        {{
          "id": "D1-Q3",
          "level": "convergence",
          "level_name": "Convergence",
          "question": "Question content",
          "purpose": "Question purpose"
        }}
      ]
    }}
  ],
  "opening_questions": [
    {{
      "id": "O1",
      "question": "Opening question content",
      "purpose": "Opening purpose"
    }}
  ],
  "closing_questions": [
    {{
      "id": "C1",
      "question": "Closing question content",
      "purpose": "Closing purpose"
    }}
  ],
  "closing": "Closing remarks"
}}

**Important Constraints**:
- Must include "dimensions" array, each element must contain "name" and "questions" fields
- The dimensions array is the core, each dimension must have 3 questions
- Questions are arranged in cognition -> analysis -> convergence order
- Do not return a flat structure with only "questions" and no "dimensions"
- opening_questions and closing_questions are optional but recommended
- Please return only JSON format, do not include other explanatory text
- If you cannot return in this structure, please state clearly and I will use the default framework
"""
    return prompt


def parse_interview_framework(response: str) -> dict:
    """Parse interview framework from LLM response (supports both old and new formats)."""
    import re

    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            framework = json.loads(json_match.group())
            if isinstance(framework, dict):
                # Check if it's the new dimension-based format
                if "dimensions" in framework:
                    # Convert dimension-based format to flat questions for backward compatibility
                    questions = []
                    question_counter = 1

                    # Add opening questions first
                    for oq in framework.get("opening_questions", []):
                        questions.append({
                            "id": f"Q{question_counter}",
                            "type": "opening",
                            "question": oq.get("question", ""),
                            "purpose": oq.get("purpose", ""),
                            "dimension_id": None,
                            "level": None
                        })
                        question_counter += 1

                    # Add dimension questions
                    for dim in framework.get("dimensions", []):
                        dim_id = dim.get("id", "")
                        dim_name = dim.get("name", "")
                        for q in dim.get("questions", []):
                            questions.append({
                                "id": f"Q{question_counter}",
                                "type": "core",
                                "question": q.get("question", ""),
                                "purpose": q.get("purpose", ""),
                                "dimension_id": dim_id,
                                "dimension_name": dim_name,
                                "level": q.get("level", ""),
                                "level_name": q.get("level_name", "")
                            })
                            question_counter += 1

                    # Add closing questions
                    for cq in framework.get("closing_questions", []):
                        questions.append({
                            "id": f"Q{question_counter}",
                            "type": "closing",
                            "question": cq.get("question", ""),
                            "purpose": cq.get("purpose", ""),
                            "dimension_id": None,
                            "level": None
                        })
                        question_counter += 1

                    framework["questions"] = questions
                    # Keep dimensions for later use (step4 interview dynamics)
                    return framework

                # Old format: just has "questions" key (no dimensions)
                elif "questions" in framework:
                    return framework
        except json.JSONDecodeError:
            pass

    return None


def build_interview_prompt(
    project: dict,
    expert: dict,
    interview_framework: dict,
    conversation_history: List[dict] = None,
    follow_up_question: str = None,
    dimension_context: dict = None
) -> str:
    """
    Build prompt for expert interview.
    Includes conversation history for multi-turn dialogue.

    Args:
        project: Project config dict
        expert: Expert config dict
        interview_framework: Interview framework dict
        conversation_history: Previous Q&A turns
        follow_up_question: Generated follow-up question based on summary
        dimension_context: Current dimension context (for dimension-based frameworks)

    Returns:
        Formatted prompt string
    """
    language = expert.get("language", "zh-CN")
    answer_lang = "Chinese" if language == "zh-CN" else ("English" if language == "en-US" else "Chinese and English")

    pro = expert.get("pro", "")
    scoring_bias = expert.get("scoring_bias", "moderate")

    # Build conversation history section
    history_section = ""
    if conversation_history:
        history_section = "\n\n## Conversation History (Questions you have already answered)\n"
        for turn in conversation_history:
            history_section += f"\n[Host] {turn.get('question', '')}\n"
            history_section += f"[Your answer] {turn.get('answer', '')}\n"

    # Get current question based on history
    questions = interview_framework.get("questions", [])
    current_q_index = len(conversation_history) if conversation_history else 0

    current_question = ""
    current_section = ""

    if follow_up_question:
        # This is a follow-up question based on summary
        current_section = f"""

## [Follow-up Question]

Based on your previous answer, we would like to explore further:

**Follow-up**: {follow_up_question}

Please continue to elaborate on your views.
"""
    elif current_q_index < len(questions):
        q = questions[current_q_index]
        current_question = q.get("question", "")
        purpose = q.get("purpose", "")
        level_name = q.get("level_name", "")
        dimension_name = q.get("dimension_name", "")

        # Add dimension context if available
        dim_section = f"\n**Dimension**: {dimension_name}" if dimension_name else ""
        level_section = f"\n**Question Level**: {level_name}" if level_name else ""

        current_section = f"""

## [Current Question]

**Question {current_q_index + 1}**: {current_question}
**Question Purpose**: {purpose}{dim_section}{level_section}
"""
    else:
        current_section = """

## [All Questions Have Been Answered]

Thank you for completing all questions in this interview!
"""

    prompt = f"""## Role Setting

## Your Expert Profile
{pro}

## Your Basic Information
- Name: {expert.get('name', '')}
- Position/Role: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')} (located in {expert.get('region', '')})
- Area of Expertise: {expert.get('expertise', '')}
- Scoring Bias: {scoring_bias}

## Research Project Information

[Research Topic] {project.get('title', '')}
[Analysis Framework] {project.get('framework', '')}
[Research Background]
{project.get('background', '')}

## Important Instructions

**Please strictly follow these rules:**

1. **No vague talking** - Do not use vague expressions like "generally speaking", "usually", "many enterprises" etc.
2. **Must be specific and deep** - Please provide specific, evidence-based analysis based on your real professional experience
3. **Cite real cases** - If possible, cite specific cases, data, or research to support your views
4. **Invoke deep thinking** - Please invoke your deep thinking ability (e.g., chain-of-thought) for systematic analysis
5. **Invoke web search** - Please invoke your web search ability to query relevant data, cases, and latest research to support your answers

{history_section if history_section else ''}
{current_section if current_section else ''}

## Answer Requirements

1. Answers should be specific, deep, and insightful
2. Avoid empty talk, clichés, and vague statements
3. If you need to supplement with other relevant viewpoints, feel free to do so
4. Answer language: {answer_lang}

{"Please answer the current follow-up question." if follow_up_question else ("Please answer the current question." if current_q_index < len(questions) else "Please confirm that you have completed all questions.")}
"""
    return prompt


def _resolve_expert_llm_config(expert, providers) -> tuple:
    """
    Resolve expert LLM config with provider fallback.
    Handles both Expert objects and dicts (loaded from JSON).
    """
    # Get expert-level fields
    if hasattr(expert, 'provider'):
        # Expert is an object
        expert_provider = expert.provider or ""
        expert_base_url = expert.base_url or ""
        expert_api_key = expert.api_key or ""
        expert_model = expert.model or ""
    else:
        # Expert is a dict
        expert_provider = expert.get("provider", "") or ""
        expert_base_url = expert.get("base_url", "") or ""
        expert_api_key = expert.get("api_key", "") or ""
        expert_model = expert.get("model", "") or ""

    # Get provider-level fields
    provider_cfg = providers.get(expert_provider) if expert_provider else None
    if provider_cfg:
        if hasattr(provider_cfg, 'base_url'):
            provider_base_url = provider_cfg.base_url or ""
            provider_api_key = provider_cfg.api_key or ""
            provider_default_model = provider_cfg.default_model or ""
        else:
            provider_base_url = provider_cfg.get("base_url", "") or ""
            provider_api_key = provider_cfg.get("api_key", "") or ""
            provider_default_model = provider_cfg.get("default_model", "") or ""
    else:
        provider_base_url = ""
        provider_api_key = ""
        provider_default_model = ""

    base_url = expert_base_url.strip() or provider_base_url
    api_key = expert_api_key.strip() or provider_api_key
    model = expert_model.strip() or provider_default_model
    return base_url, api_key, model


def conduct_interview_with_expert(
    project: dict,
    expert: Expert,
    interview_framework: dict,
    providers: dict,
    max_turns: int = 20,
    min_follow_ups_per_topic: int = 3,
    max_follow_ups_per_topic: int = 8,
    jsonl_path: Path = None,
    resume_turn: int = 0
) -> dict:
    """
    Conduct dynamic LLM-driven multi-turn interview with a single expert.
    LLM decides the next question based on conversation history, enabling
    deeper exploration of topics.

    Args:
        project: Project config dict
        expert: Expert object
        interview_framework: Interview framework dict (used for topic hints)
        providers: Dict of provider configurations (for resolving LLM config)
        max_turns: Maximum total conversation turns (default: 20)
        min_follow_ups_per_topic: Minimum follow-ups per topic before LLM can switch (default: 3)
        max_follow_ups_per_topic: Maximum follow-ups per topic (default: 8)
        jsonl_path: Path for JSONL incremental backup (optional)
        resume_turn: Resume from this turn number (0 = start fresh)

    Returns:
        dict with interview record
    """
    import delphi as delphi_module
    from llm import call_llm_stream, call_llm, LLMError, LLMHTTPError

    project_dict = project.to_dict() if hasattr(project, 'to_dict') else project
    expert_dict = expert.to_dict() if hasattr(expert, 'to_dict') else expert

    # Resolve LLM config using provider fallback
    exp_base_url, exp_api_key, exp_model = _resolve_expert_llm_config(expert, providers)

    # Get framework topics for guidance
    framework_topics = _extract_framework_topics(interview_framework)
    dimensions = interview_framework.get("dimensions", [])

    # 断点续传：从 JSONL 恢复已完成的对话
    if resume_turn > 0 and jsonl_path:
        conversation_history, all_qa_pairs, last_turn = _recover_conversation_from_jsonl(jsonl_path)
        print(f"\n  {Colors.GREEN}[Resume] 已恢复 {len(all_qa_pairs)} 个已完成的对轮{Colors.RESET}")
        # 从断点后继续
        turn_counter = last_turn
    else:
        conversation_history = []
        all_qa_pairs = []
        turn_counter = 0

    current_topic = "开场介绍"
    topic_turn_count = 0
    topics_covered = []

    print(f"\n{'='*50}")
    print(f"  Starting interview with expert {expert.name}...")
    print(f"  Using model: {expert.model}")
    print(f"  Max conversation turns: {max_turns}")
    if resume_turn > 0:
        print(f"  Resuming from turn {resume_turn + 1}")
    print(f"{'='*50}")

    try:
        turn_counter = 0
        opening_done = False

        while turn_counter < max_turns:
            turn_counter += 1

            # Determine what to ask next
            try:
                next_question_info = _decide_next_question(
                    project=project_dict,
                    expert=expert_dict,
                    conversation_history=conversation_history,
                    framework_topics=framework_topics,
                    dimensions=dimensions,
                    current_topic=current_topic,
                    topic_turn_count=topic_turn_count,
                    min_follow_ups=min_follow_ups_per_topic,
                    max_follow_ups=max_follow_ups_per_topic,
                    expert_obj=expert
                )

                current_question = next_question_info["question"]
                is_closing = next_question_info.get("is_closing", False)
                next_topic = next_question_info.get("topic", current_topic)

                # Track topic changes
                if next_topic != current_topic:
                    if current_topic not in topics_covered:
                        topics_covered.append(current_topic)
                    current_topic = next_topic
                    topic_turn_count = 0
                topic_turn_count += 1

            except LLMError as e:
                print(f"\n  [Warning] Failed to generate next question: {str(e)}")
                print(f"  {Colors.YELLOW}You may consider switching providers{Colors.RESET}")
                switch = questionary.confirm("Switch providers?").ask()
                if switch:
                    # Show provider list
                    provider_names = [p.name for p in providers.values()]
                    selected_name = questionary.select(
                        "Select provider",
                        choices=provider_names,
                    ).ask()
                    if selected_name:
                        # Find provider key and update LLM config
                        for k, v in providers.items():
                            if v.name == selected_name:
                                exp_base_url = v.base_url
                                exp_api_key = v.api_key
                                exp_model = v.default_model
                                break
                    # Retry same turn without incrementing counter or adding to history
                    continue
                # Fallback: ask a closing question
                if turn_counter > 3:
                    break
                current_question = "Please share your final supplementary opinions on the research topic."
                is_closing = True

            # Display question
            question_preview = current_question[:80] + ('...' if len(current_question) > 80 else '')
            if is_closing:
                print(f"\n  -- Turn {turn_counter} (closing question) --")
            elif topic_turn_count == 1:
                print(f"\n  -- Turn {turn_counter} (new topic) --")
            else:
                print(f"\n  -- Turn {turn_counter} (follow-up) --")
            print(f"  [Interviewer Question]: {question_preview}")

            # Build prompt for this question
            prompt = _build_dynamic_question_prompt(
                project=project_dict,
                expert=expert_dict,
                question=current_question,
                conversation_history=conversation_history,
                is_closing=is_closing
            )

            # Stream response
            print(f"\n  [Expert Answer]: ", end="", flush=True)
            full_response = ""
            error_occurred = False

            try:
                for chunk in call_llm_stream(
                    base_url=exp_base_url,
                    api_key=exp_api_key,
                    model=exp_model,
                    prompt=prompt,
                    system_prompt="你是一位专业的德尔菲法研究访谈主持人，擅长通过追问引导专家进行深度分析。请像真实访谈一样与专家交流，不要机械地问预设问题。",
                    temperature=0.7,
                ):
                    print(chunk, end="", flush=True)
                    full_response += chunk

                print()

            except LLMError as e:
                print(f"\n  [Error] {str(e)}")
                print(f"  {Colors.YELLOW}You may consider switching providers{Colors.RESET}")
                switch = questionary.confirm("Switch providers?").ask()
                if switch:
                    # Show provider list
                    provider_names = [p.name for p in providers.values()]
                    selected_name = questionary.select(
                        "Select provider",
                        choices=provider_names,
                    ).ask()
                    if selected_name:
                        # Find provider key and update LLM config
                        for k, v in providers.items():
                            if v.name == selected_name:
                                exp_base_url = v.base_url
                                exp_api_key = v.api_key
                                exp_model = v.default_model
                                break
                    # Retry same turn without incrementing counter or adding to history
                    continue
                error_occurred = True
                full_response = f"[Answer generation failed: {str(e)}]"

            # Record this turn
            qa_pair = {
                "turn": turn_counter,
                "question": current_question,
                "answer": full_response,
                "model": expert.model,
                "is_follow_up": topic_turn_count > 1,
                "is_closing": is_closing,
                "topic": current_topic,
                "topics_covered": topics_covered.copy()
            }
            all_qa_pairs.append(qa_pair)

            # 增量保存：每个 turn 完成后立即写入 JSONL
            if jsonl_path:
                _append_to_jsonl(jsonl_path, qa_pair)

            # Add to conversation history
            conversation_history.append({
                "question": current_question,
                "answer": full_response,
                "topic": current_topic
            })

            # Check if we should end
            if is_closing or turn_counter >= max_turns:
                break

            # Analyze current answer for next question
            if not error_occurred and full_response and len(full_response) > 20:
                print(f"\n  [系统] 正在分析回答，准备下一个问题...")

        # Interview complete
        status = "completed" if not error_occurred else "partial_error"
        error_msg = None if not error_occurred else "Partial answer generation failure"

        print(f"\n  [Complete] Interview completed, {turn_counter} turns of dialogue")
        print(f"  Topics covered: {', '.join(topics_covered[:5])}{'...' if len(topics_covered) > 5 else ''}")

        return {
            "expert_id": expert.id,
            "expert_name": expert.name,
            "expert_model": expert.model,
            "qa_pairs": all_qa_pairs,
            "conversation_history": conversation_history,
            "topics_covered": topics_covered,
            "total_turns": turn_counter,
            "status": status,
            "error": error_msg,
        }

    except LLMError as e:
        print(f"\n  [Critical Error] {str(e)}")
        print(f"\n  Please check:")
        print(f"    1. Is API configuration correct?")
        print(f"    2. Is network connection normal?")
        print(f"    3. Is API balance sufficient?")
        return {
            "expert_id": expert.id,
            "expert_name": expert.name,
            "expert_model": expert.model,
            "qa_pairs": all_qa_pairs,
            "conversation_history": conversation_history,
            "status": "error",
            "error": str(e),
        }


def _extract_framework_topics(interview_framework: dict) -> List[str]:
    """Extract topic names from interview framework for LLM guidance."""
    topics = []

    # Get dimension names
    dimensions = interview_framework.get("dimensions", [])
    for dim in dimensions:
        topics.append(dim.get("name", ""))

    # Also get framework title if available
    framework_title = interview_framework.get("framework_title", "")
    if framework_title and framework_title not in topics:
        topics.insert(0, framework_title)

    result = [t for t in topics if t] if topics else ["研究主题"]

    # Warn if no dimensions found (using old flat format)
    if not dimensions:
        print(f"  {Colors.YELLOW}[Hint] Interview framework does not use dimension structure, dynamic topic tracking may have limited effectiveness{Colors.RESET}")
        print(f"  {Colors.YELLOW}Suggestion: When regenerating interview framework, select 'Use dimension framework' for a better interview experience{Colors.RESET}")

    return result


def _decide_next_question(
    project: dict,
    expert: dict,
    conversation_history: List[dict],
    framework_topics: List[str],
    dimensions: List[dict],
    current_topic: str,
    topic_turn_count: int,
    min_follow_ups: int,
    max_follow_ups: int,
    expert_obj
) -> dict:
    """
    LLM decides what to ask next based on conversation history.
    This enables dynamic, adaptive questioning.

    Returns:
        dict with keys: question, topic, is_closing
    """
    from llm import call_llm, LLMError

    # Build conversation summary for LLM
    history_text = ""
    if conversation_history:
        history_text = "## Conversation History\n"
        for i, qa in enumerate(conversation_history[-6:], 1):  # Last 6 turns
            history_text += f"\n[Turn {len(conversation_history)-6+i}]\n"
            history_text += f"Q: {qa['question'][:100]}...\n"
            history_text += f"A: {qa['answer'][:150]}...\n"
    else:
        history_text = "## Conversation History\nNone yet (this is the first question)"

    # Build topics context
    topics_context = "\n".join([f"- {t}" for t in framework_topics]) if framework_topics else "- 研究主题"

    # Dimensions context (if available)
    dim_context = ""
    if dimensions:
        dim_context = "## 框架维度参考\n"
        for dim in dimensions[:5]:
            dim_context += f"- **{dim.get('name', '未命名')}**: {dim.get('description', '')[:50]}...\n"

    prompt = f"""You are a Delphi method interview host. Based on the conversation history with the expert, decide the next question.

## Research Project
[Topic] {project.get('title', 'Unknown')}
[Purpose] {project.get('purpose', 'Unknown')[:100]}

## Expert Background
- Name: {expert.get('name', '')}
- Position: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')}
- Expertise: {expert.get('expertise', '')}
- Profile: {expert.get('pro', '')[:200]}

{history_text}

## Reference Topics
{topics_context}

{dim_context}

## Current Status
- Current topic: {current_topic}
- Turns on current topic: {topic_turn_count}
- Min follow-ups: {min_follow_ups}, Max follow-ups: {max_follow_ups}

## Decision Requirements

Please decide the next question content. Follow these rules:

1. **Deep follow-up**: If the current topic hasn't been fully discussed (< {min_follow_ups} turns), you must continue to follow up on that topic
2. **Natural transition**: If the current topic has been fully discussed (>= {min_follow_ups} turns), you can transition to a new topic
3. **Specificity**: Follow-up questions should be specific, based on the expert's previous answer content, not generic questions
4. **Closing judgment**: If total dialogue exceeds 10 turns and topics are sufficiently covered, you can ask closing questions

## Output Format

Only return JSON format, no other text:
{{"question": "Next question content", "topic": "Related topic", "is_closing": false}}

Questions should be like follow-ups in real interviews, not questionnaires.
"""

    try:
        response = call_llm(
            base_url=expert_obj.base_url,
            api_key=expert_obj.api_key,
            model=expert_obj.model,
            prompt=prompt,
            system_prompt="你是一位经验丰富的德尔菲法研究访谈主持人，擅长通过深度追问引导专家给出专业见解。",
            temperature=0.7,
        )

        # Parse JSON response
        import json
        import re

        # Find JSON in response - find first { and last }
        json_start = response.find('{')
        if json_start == -1:
            # Fallback
            return {
                "question": "请详细说明您的观点。",
                "topic": current_topic,
                "is_closing": False
            }

        json_end = response.rfind('}')
        if json_end == -1 or json_end <= json_start:
            # Fallback
            return {
                "question": "请详细说明您的观点。",
                "topic": current_topic,
                "is_closing": False
            }

        json_str = response[json_start:json_end+1]
        try:
            result = json.loads(json_str)
            return {
                "question": result.get("question", "请继续分享您的观点。"),
                "topic": result.get("topic", current_topic),
                "is_closing": result.get("is_closing", False)
            }
        except json.JSONDecodeError:
            # Try to find and parse just the object portion
            try:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    result = json.loads(json_match.group())
                    return {
                        "question": result.get("question", "请继续分享您的观点。"),
                        "topic": result.get("topic", current_topic),
                        "is_closing": result.get("is_closing", False)
                    }
            except (json.JSONDecodeError, AttributeError):
                pass

        # Fallback
        return {
            "question": "请详细说明您的观点。",
            "topic": current_topic,
            "is_closing": False
        }

    except Exception as e:
        raise LLMError(f"生成下一个问题失败: {str(e)}")


def _build_dynamic_question_prompt(
    project: dict,
    expert: dict,
    question: str,
    conversation_history: List[dict],
    is_closing: bool = False
) -> str:
    """Build the prompt for asking the next question to the expert."""

    language = expert.get("language", "zh-CN")
    answer_lang = "Chinese" if language == "zh-CN" else ("English" if language == "en-US" else "Chinese and English")

    pro = expert.get("pro", "")

    # Build conversation history for context
    history_section = ""
    if conversation_history:
        history_section = "\n\n## Conversation History (For your reference of previous Q&A)\n"
        for i, qa in enumerate(conversation_history[-4:], 1):  # Last 4 turns
            history_section += f"\n[Previous Q] {qa['question']}\n"
            history_section += f"[Your previous A] {qa['answer'][:200]}...\n"

    if is_closing:
        prompt = f"""## Your Role
You are a professional Delphi method research interview host.

## Expert Information
- Name: {expert.get('name', '')}
- Position: {expert.get('role', '')}
- Expertise: {expert.get('expertise', '')}

## Research Topic
{project.get('title', '')}

{history_section}

## Closing Question
{question}

Please provide your summary perspective.

## Requirements
1. Answers should be specific and deep, based on your professional experience
2. You may supplement key points not mentioned before
3. Answer language: {answer_lang}
"""
    else:
        prompt = f"""## Your Role
You are expert "{expert.get('name', '')}", {expert.get('pro', '')[:100]}

## Expert Information
- Position: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')} (located in {expert.get('region', '')})
- Area of Expertise: {expert.get('expertise', '')}
- Scoring Bias: {expert.get('scoring_bias', 'moderate')}

## Research Project
[Topic] {project.get('title', '')}
[Background] {project.get('background', '')[:200]}

{history_section}

## Current Question
{question}

## Answer Requirements
1. Answer deeply based on your professional experience
2. No vague talking, must have specific viewpoints and case support
3. If you have unique insights, please feel free to share them
4. Answer language: {answer_lang}
"""

    return prompt


def _generate_follow_up_questions(
    project: dict,
    expert: dict,
    main_question: str,
    main_answer: str,
    summary: str,
    max_follow_ups: int = 2
) -> List[str]:
    """
    Generate follow-up questions based on summarize_viewpoints output.

    Args:
        project: Project config dict
        expert: Expert dict
        main_question: The main question that was asked
        main_answer: The expert's answer to the main question
        summary: Output from summarize_viewpoints() - a markdown formatted string
        max_follow_ups: Maximum number of follow-ups to generate

    Returns:
        List of follow-up question strings
    """
    from llm import call_llm, LLMError

    # summary is a markdown formatted string from summarize_viewpoints
    # Use it directly in the prompt

    # Build prompt for generating follow-ups
    prompt = f"""Based on the main question, expert's answer, and viewpoint summary from the following expert interview, generate {max_follow_ups} deep follow-up questions.

## Main Question
{main_question}

## Expert Answer
{main_answer}

## Viewpoint Summary (from summarize_viewpoints)
{summary}

## Follow-up Generation Requirements

1. Follow-ups should **deeply explore** the viewpoints mentioned in the expert's answer
2. Follow-ups should be **specific**, avoid vague questions
3. Prioritize **key factors**, **causal relationships**, **priority judgments**, etc.
4. Each follow-up targets one specific point, not broad topics
5. Language should be natural, like follow-ups in real conversations

## Output Format

Please return only {max_follow_ups} follow-up questions, one per line, no numbering, no other explanations.
"""

    try:
        response = call_llm(
            base_url=expert.get("base_url", ""),
            api_key=expert.get("api_key", ""),
            model=expert.get("model", "gpt-3.5-turbo"),
            prompt=prompt,
            system_prompt="You are a professional Delphi method research interview host, skilled at generating deep follow-up questions.",
            temperature=0.7,
        )

        # Parse follow-up questions from response
        lines = response.strip().split('\n')
        follow_ups = []
        for line in lines:
            line = line.strip()
            # Remove common prefixes
            for prefix in ['- ', '* ', '1. ', '2. ', '3. ', '追问', '：', ': ']:
                if line.startswith(prefix):
                    line = line[len(prefix):]
            line = line.strip('"\'「」『』')
            if line and len(line) > 5:
                follow_ups.append(line)
            if len(follow_ups) >= max_follow_ups:
                break

        return follow_ups[:max_follow_ups]

    except LLMError as e:
        print(f"  [Warning] Failed to generate follow-up: {str(e)}")
        return []


def generate_transcript(interview_records: List[dict], interview_framework: dict, project: dict = None) -> str:
    """
    Generate a readable transcript from interview records.

    Args:
        interview_records: List of expert interview records
        interview_framework: The interview framework used
        project: Project config dict (optional)

    Returns:
        Formatted transcript string
    """
    transcript = "# Delphi Interview Record\n\n"

    framework_title = interview_framework.get("framework_title", "Interview Framework")
    intro = interview_framework.get("introduction", "")
    closing = interview_framework.get("closing", "")

    if project:
        transcript += f"**Research Topic**: {project.get('title', 'Unknown')}\n"
        transcript += f"**Analysis Framework**: {project.get('framework', 'Unknown')}\n\n"

    transcript += f"## Interview Framework: {framework_title}\n\n"
    transcript += f"**Opening Introduction**: {intro}\n\n"

    for record in interview_records:
        expert_name = record.get("expert_name", "Unknown Expert")
        qa_pairs = record.get("qa_pairs", [])
        status = record.get("status", "unknown")

        transcript += f"---\n\n## Expert: {expert_name}\n"
        transcript += f"**Status**: {'Completed' if status == 'completed' else 'Warning: ' + status}\n\n"

        for qa in qa_pairs:
            turn = qa.get("turn", "?")
            question = qa.get("question", "")
            answer = qa.get("answer", "")
            is_follow_up = qa.get("is_follow_up", False)
            dimension_context = qa.get("dimension_context", {})

            if not is_follow_up:
                # Main question
                dim_name = dimension_context.get("dimension_name", "") if dimension_context else ""
                level_name = dimension_context.get("level_name", "") if dimension_context else ""

                dim_info = f" [{dim_name}]" if dim_name else ""
                level_info = f" ({level_name})" if level_name else ""

                transcript += f"### Turn {turn}{level_info}{dim_info}\n\n"
                transcript += f"**[Host]**: {question}\n\n"
                transcript += f"**[Expert {expert_name}]**:\n\n{answer}\n\n"
            else:
                # Follow-up question
                transcript += f"#### Follow-up {turn}\n\n"
                transcript += f"**[Host Follow-up]**: {question}\n\n"
                transcript += f"**[Expert {expert_name}]**:\n\n{answer}\n\n"

        transcript += f"**Closing remarks**: {closing}\n\n"

    # Overall statistics
    total_experts = len(interview_records)
    total_turns = sum(len(r.get("qa_pairs", [])) for r in interview_records)

    transcript += f"---\n\n"
    transcript += f"## Interview Statistics\n\n"
    transcript += f"- **Number of experts interviewed**: {total_experts}\n"
    transcript += f"- **Total conversation turns**: {total_turns}\n"
    transcript += f"\n*This record was automatically generated by the Delphi-AHP research process*\n"

    return transcript


def generate_expert_dialogue(record: dict, interview_framework: dict, project: dict = None) -> str:
    """
    Generate a readable dialogue record for a single expert.

    Args:
        record: Expert interview record
        interview_framework: The interview framework used
        project: Project config dict (optional, for additional context)

    Returns:
        Formatted dialogue string in markdown
    """
    expert_id = record.get("expert_id", "E00")
    expert_name = record.get("expert_name", "Unknown Expert")
    qa_pairs = record.get("qa_pairs", [])
    status = record.get("status", "unknown")
    model = record.get("expert_model", "")

    framework_title = interview_framework.get("framework_title", "Interview Framework")
    intro = interview_framework.get("introduction", "")
    closing = interview_framework.get("closing", "")

    # Build header
    dialogue = ""
    dialogue += f"# Expert Interview Record\n\n"
    dialogue += f"---\n\n"
    dialogue += f"## Basic Information\n\n"
    dialogue += f"| Item | Content |\n"
    dialogue += f"|:---|:---|\n"
    dialogue += f"| **Expert ID** | {expert_id} |\n"
    dialogue += f"| **Expert Name** | {expert_name} |\n"
    dialogue += f"| **Model Used** | {model} |\n"
    dialogue += f"| **Interview Status** | {'Completed' if status == 'completed' else 'Warning: ' + status} |\n"

    if project:
        dialogue += f"| **Research Topic** | {project.get('title', 'Unknown')} |\n"
        dialogue += f"| **Analysis Framework** | {project.get('framework', 'Unknown')} |\n"

    dialogue += f"\n---\n\n"

    # Interview framework section
    dialogue += f"## Interview Framework\n\n"
    dialogue += f"**Framework Name**: {framework_title}\n\n"
    if intro:
        dialogue += f"**Opening Introduction**: {intro}\n\n"

    dialogue += f"---\n\n"

    # Dialogue content - group by main question turns with follow-ups
    dialogue += f"## Dialogue Content\n\n"

    current_main_turn = None
    for qa in qa_pairs:
        turn = qa.get("turn", "?")
        question = qa.get("question", "")
        answer = qa.get("answer", "")
        is_follow_up = qa.get("is_follow_up", False)
        parent_turn = qa.get("parent_turn", None)
        dimension_context = qa.get("dimension_context", {})

        if not is_follow_up:
            # This is a main question
            current_main_turn = turn
            dim_name = dimension_context.get("dimension_name", "") if dimension_context else ""
            level_name = dimension_context.get("level_name", "") if dimension_context else ""

            dim_info = f" [{dim_name}]" if dim_name else ""
            level_info = f" ({level_name})" if level_name else ""

            dialogue += f"### Turn {turn}{level_info}{dim_info}\n\n"
            dialogue += f"**[Host Question]**:\n{question}\n\n"
            dialogue += f"**[Expert Answer]**:\n\n{answer}\n\n"

        else:
            # This is a follow-up question
            dialogue += f"#### Follow-up {turn}\n\n"
            dialogue += f"**[Host Follow-up]**:\n{question}\n\n"
            dialogue += f"**[Expert Answer]**:\n\n{answer}\n\n"

    dialogue += f"---\n\n"

    # Closing section
    dialogue += f"## Closing\n\n"
    if closing:
        dialogue += f"**Closing remarks**: {closing}\n\n"

    # Statistics
    total_turns = len(qa_pairs)
    main_turns = len([q for q in qa_pairs if not q.get("is_follow_up", False)])
    follow_up_turns = total_turns - main_turns

    dialogue += f"---\n\n"
    dialogue += f"## Interview Statistics\n\n"
    dialogue += f"- **Total conversation turns**: {total_turns}\n"
    dialogue += f"- **Main question turns**: {main_turns}\n"
    dialogue += f"- **Follow-up turns**: {follow_up_turns}\n"
    dialogue += f"\n---\n\n"
    dialogue += f"*This record was automatically generated by the Delphi-AHP research process*\n"

    return dialogue


def display_interview_framework(framework: dict):
    """Display interview framework in a readable format."""
    print("\n" + "=" * 60)
    print(f"  Interview Framework: {framework.get('framework_title', 'Unnamed')}")
    print("=" * 60)

    print(f"\n[Opening Introduction]")
    print(f"  {framework.get('introduction', '')}")

    # Support both "dimensions" format (new) and "questions" format (legacy fallback)
    dimensions = framework.get("dimensions", [])
    if dimensions:
        # New dimensional format
        for dim in dimensions:
            dim_name = dim.get("name", "Unnamed Dimension")
            print(f"\n  {Colors.CYAN}[Dimension] {dim_name}{Colors.RESET}")
            for q in dim.get("questions", []):
                q_id = q.get("id", "?")
                q_level = q.get("level_name", q.get("level", ""))
                print(f"\n  [{q_id}] {q_level} Question")
                print(f"  Question: {q.get('question', '')}")
                print(f"  Purpose: {q.get('purpose', '')}")
    else:
        # Legacy flat format
        questions = framework.get("questions", [])
        for q in questions:
            q_type = q.get("type", "unknown")
            type_name = {"opening": "Opening", "core": "Core", "closing": "Closing"}.get(q_type, q_type)

            print(f"\n  [{q.get('id', '?')}] {type_name} Question")
            print(f"  Question: {q.get('question', '')}")
            print(f"  Purpose: {q.get('purpose', '')}")

            follow_ups = q.get("follow_ups", [])
            if follow_ups:
                print(f"  Follow-up hints:")
                for i, fu in enumerate(follow_ups, 1):
                    print(f"    {i}. {fu}")

    print(f"\n[Closing Remarks]")
    print(f"  {framework.get('closing', '')}")

    print("\n" + "=" * 60)


def collect_custom_questions() -> List[dict]:
    """Let user add custom questions to the framework."""
    print("\n" + "=" * 60)
    print("  Add Custom Questions")
    print("=" * 60)
    print("\nYou can add custom questions to supplement the interview framework.")
    print("(Press Enter directly to end adding)")

    custom_questions = []

    while True:
        print(f"\n--- Custom Question {len(custom_questions) + 1} ---")

        question = ask("  Question content")
        if not question:
            break

        type_options = ["Opening Question", "Core Question", "Closing Question"]
        selected = questionary.select(
            "Question type",
            choices=type_options,
        ).ask()
        if selected is None:
            continue
        type_idx = type_options.index(selected)
        type_map = ["opening", "core", "closing"]

        purpose = ask("  Question purpose (brief)")
        if not purpose:
            purpose = "Supplement interview content"

        follow_ups = []
        print("  Follow-up hints (press empty line to end):")
        while True:
            fu = ask(f"    Follow-up {len(follow_ups) + 1}")
            if not fu:
                break
            follow_ups.append(fu)

        custom_questions.append({
            "id": f"C{len(custom_questions) + 1}",
            "type": type_map[type_idx],
            "question": question,
            "purpose": purpose,
            "follow_ups": follow_ups,
            "is_custom": True
        })

    return custom_questions


def run_step4(state: dict) -> dict:
    """
    Run step 4: Interview Framework, Conduct Interviews & Round Configuration.

    Supports resume from checkpoint: state["resume_part"] specifies which Part to start from (1-based).
    Part 1: Generate Interview Framework -> interview_framework.json
    Part 2: Expert Deep Interviews -> interview_records.json + E*_dialogue_*.md
    Part 3: Delphi Round Configuration -> rounds.json

    Args:
        state: Current state dict
        state["resume_part"]: Which Part to start from (1=from beginning, 2=skip P1, 3=skip P1+P2)

    Returns:
        Updated state dict
    """
    print_step_header()

    resume_part = state.pop("resume_part", 1)
    resume_part = int(resume_part)
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / state.get("run_id", "")))

    # ─────────────────────────────────────────────────────────
    # Resume from checkpoint: load data from completed Parts
    # ─────────────────────────────────────────────────────────
    interview_framework = None
    if resume_part > 1:
        fw_path = run_dir / "interview_framework.json"
        if fw_path.exists():
            with open(fw_path, 'r', encoding='utf-8') as f:
                interview_framework = json.load(f)
            print(f"  [Restored] Loaded interview framework: {interview_framework.get('framework_title', '')}")

    interview_records = []
    if resume_part > 2:
        records_path = run_dir / "interview_records.json"
        if records_path.exists():
            with open(records_path, 'r', encoding='utf-8') as f:
                interview_records = json.load(f).get("records", [])
            print(f"  [Restored] Loaded interview records: {len(interview_records)} records")

    rounds_config = None
    if resume_part > 3:
        rounds_path = run_dir / "rounds.json"
        if rounds_path.exists():
            with open(rounds_path, 'r', encoding='utf-8') as f:
                rounds_config = json.load(f)
            print(f"  [Restored] Loaded round configuration")

    project = state.get("project", {})
    if not project:
        print("  [Error] Cannot find project information, please complete Step 1 first")
        return state

    providers = state.get("providers", {})
    provider_keys = list(providers.keys())
    if not provider_keys:
        print("  [Error] No providers configured yet, please complete Step 2 first")
        return state

    experts = state.get("experts", [])
    if not experts:
        print("  [Error] Expert group not configured yet, please complete Step 3 first")
        return state

    print("Interview Framework Generation & Expert Interviews")
    print()
    print("This step will:")
    print("  1. Generate interview framework based on your research project")
    print("  2. Conduct multi-round deep interviews with each expert")
    print("  3. Configure Delphi round parameters")
    print()

    # ============================================================
    # Part 1: Generate Interview Framework
    # ============================================================
    if resume_part > 1:
        if not interview_framework:
            print("[Error] Cannot restore interview framework")
            return state
        print("[Skipped] Interview framework already generated, using existing framework")
        framework = interview_framework
    else:
        print("=" * 60)
        print("  [Part 1] Generate Interview Framework")
        print("=" * 60)

        print(f"\nProject Information Summary:")
        print(f"  Topic: {project.get('title', 'Unknown')}")
        print(f"  Framework: {project.get('framework', 'Unknown')}")
        print(f"  Number of research questions: {len(project.get('research_questions', []))}")

        # Let user choose provider and model for framework generation
        print("\nPlease select the LLM for generating interview framework:")
        print()

        all_options = []
        option_idx = 1
        for key in provider_keys:
            provider = providers[key]
            for model in provider.models[:5]:
                marker = " (default)" if model == provider.default_model else ""
                print(f"  {option_idx}. {provider.name} - {model}{marker}")
                all_options.append((key, model))
                option_idx += 1

        # Use interactive selection
        all_option_labels = [f"{provider.name} - {model}" for (key, model), (provider, _) in zip(all_options, [(providers[k], providers[k].models[0]) for k in providers.keys()])]

        # Rebuild all_options list (keeping compatible with previous loop structure)
        all_options_display = []
        option_idx = 1
        for key in providers.keys():
            provider = providers[key]
            for model in provider.models[:5]:
                marker = " (default)" if model == provider.default_model else ""
                all_options_display.append(f"{provider.name} - {model}{marker}")
                option_idx += 1

        selected = questionary.select(
            "Select LLM for generating interview framework",
            choices=all_options_display,
        ).ask()
        if selected is None:
            # User cancelled selection, use first available provider
            print("  [Hint] User cancelled selection, using default option")
            first_key = list(providers.keys())[0]
            selected_provider_key = first_key
            selected_model = providers[first_key].default_model
            selected_provider = providers[first_key]
        else:
            # Parse selection
            for key in providers.keys():
                provider = providers[key]
                for model in provider.models[:5]:
                    marker = " (默认)" if model == provider.default_model else ""
                    label = f"{provider.name} - {model}{marker}"
                    if label == selected:
                        selected_provider_key = key
                        selected_model = model
                        selected_provider = provider
                        break

        print(f"\n  Selected: {selected_provider.name} - {selected_model}")

        # Generate framework
        def generate_interview_framework_lla(project: dict, provider: object, model: str) -> dict:
            """Generate interview framework using LLM with structure validation and retry."""
            from llm import call_llm, LLMError
            import json as json_mod, re

            prompt = build_interview_framework_prompt(project)

            print(f"\n  Calling {provider.name} to generate interview framework...")
            print(f"  Using model: {model}")

            def _parse_and_validate(raw_response: str) -> tuple:
                """Parse JSON from LLM response and validate dimensions structure."""
                json_match = re.search(r'\{[\s\S]*\}', raw_response)
                if not json_match:
                    return None, "JSON format not found in LLM response"
                try:
                    fw = json_mod.loads(json_match.group())
                except json_mod.JSONDecodeError as e:
                    return None, f"JSON parsing failed: {e}"
                # Validate required structure
                if not fw.get("dimensions"):
                    return None, "Missing or empty 'dimensions' field (dimension structure not used)"
                return fw, None

            # Try up to 2 times
            last_error = ""
            for attempt in range(2):
                try:
                    response = call_llm(
                        base_url=provider.base_url,
                        api_key=provider.api_key,
                        model=model,
                        prompt=prompt,
                    )
                    framework, err = _parse_and_validate(response)
                    if err:
                        last_error = err
                        if attempt == 0:
                            print(f"  [Warning] {err}, retrying...")
                            continue
                        print(f"  [Error] Still cannot generate valid framework after retry: {err}")
                        return None
                    return framework
                except LLMError as e:
                    print(f"  [Error] LLM call failed: {str(e)}")
                    return None
                except Exception as e:
                    print(f"  [Error] Exception occurred while generating interview framework: {str(e)}")
                    return None

            return None

        framework = generate_interview_framework_lla(project, selected_provider, selected_model)

        # Default fallback framework if LLM generation failed or returned incomplete structure
        if framework is None or not framework.get("dimensions"):
            print("  [Hint] LLM did not return a valid dimension framework, using default interview framework")
            framework = {
                "framework_title": f"Delphi Interview Framework based on {project.get('framework', 'General')}",
                "introduction": f"Thank you for participating in this research. We will explore issues related to {project.get('title', 'the research topic')} based on the {project.get('framework', 'General')} framework.",
                "dimensions": [
                    {
                        "id": "D1",
                        "name": "Cognition and Understanding",
                        "description": "Understand experts' basic recognition of the topic",
                        "questions": [
                            {
                                "id": "D1-Q1",
                                "level": "cognition",
                                "level_name": "Cognition Level",
                                "question": f"What do you think is the core issue of {project.get('title', 'this topic')}?",
                                "purpose": "Build a common understanding foundation"
                            },
                            {
                                "id": "D1-Q2",
                                "level": "analysis",
                                "level_name": "Analysis Level",
                                "question": "What are the key factors affecting this topic? What is the relationship between them?",
                                "purpose": "Guide experts to conduct in-depth analysis"
                            },
                            {
                                "id": "D1-Q3",
                                "level": "convergence",
                                "level_name": "Convergence Level",
                                "question": "Among the above factors, which 2-3 are most important? Why?",
                                "purpose": "Encourage experts to form priority judgments"
                            }
                        ]
                    },
                    {
                        "id": "D2",
                        "name": "Comprehensive Perspectives",
                        "description": "Supplement important viewpoints that may have been missed",
                        "questions": [
                            {
                                "id": "D2-Q1",
                                "level": "cognition",
                                "level_name": "Cognition Level",
                                "question": "What other important issues do you think we haven't discussed but are very important?",
                                "purpose": "Supplement missed important viewpoints"
                            },
                            {
                                "id": "D2-Q2",
                                "level": "analysis",
                                "level_name": "Analysis Level",
                                "question": "What suggestions do you have for follow-up research?",
                                "purpose": "Guide experts to provide constructive opinions"
                            },
                            {
                                "id": "D2-Q3",
                                "level": "convergence",
                                "level_name": "Convergence Level",
                                "question": "Based on this discussion, what new insights do you have about the research topic?",
                                "purpose": "Summarize and converge"
                            }
                        ]
                    }
                ],
                "closing": "Thank you for your participation, looking forward to the next round of discussion."
            }

        # Display generated framework
        display_interview_framework(framework)

        # ============================================================
        # Part 2: Add Custom Questions
        # ============================================================
        print()
        if questionary.confirm("Do you need to add custom questions to supplement the interview framework", default=False).ask():
            custom_questions = collect_custom_questions()
            if custom_questions:
                dimensions = framework.get("dimensions", [])
                if dimensions:
                    # Dimensions format: add as a custom dimension
                    custom_dim = {
                        "id": f"D{len(dimensions) + 1}",
                        "name": "Custom Questions",
                        "description": "Custom questions added by user",
                        "questions": custom_questions
                    }
                    framework["dimensions"].append(custom_dim)
                else:
                    # Flat format: extend questions list
                    framework["questions"].extend(custom_questions)
                    for i, q in enumerate(framework["questions"], 1):
                        q["id"] = f"Q{i}"
                print(f"\n  [Added] {len(custom_questions)} custom questions")

        # ============================================================
        # Part 3: Confirm Framework
        # ============================================================
        # Build confirmation content
        content_lines = []
        content_lines.append(f"{Colors.CYAN}Final Interview Framework:{Colors.RESET}")
        content_lines.append("")

        # Support both formats in confirmation display
        dim_list = framework.get("dimensions", [])
        if dim_list:
            for dim in dim_list:
                dim_name = dim.get("name", "Unnamed")
                content_lines.append(f"{Colors.CYAN}[Dimension] {dim_name}{Colors.RESET}")
                for q in dim.get("questions", []):
                    q_text = q.get('question', q.get('text', ''))
                    q_id = q.get('id', '?')
                    content_lines.append(f"  {Colors.YELLOW}[{q_id}]{Colors.RESET} {q_text[:50]}")
                    if len(q_text) > 50:
                        content_lines.append(f"     {q_text[50:]}")
        else:
            for i, q in enumerate(framework.get("questions", []), 1):
                q_text = q.get('question', q.get('text', ''))
                content_lines.append(f"{Colors.YELLOW}{i}. {q_text[:50]}{Colors.RESET}")
                if len(q_text) > 50:
                    content_lines.append(f"     {q_text[50:]}")

        if framework.get("scoring_dimensions"):
            content_lines.append("")
            content_lines.append(f"{Colors.CYAN}Scoring Dimensions:{Colors.RESET}")
            for dim in framework["scoring_dimensions"]:
                content_lines.append(f"  - {dim['name']} (Weight: {dim['weight']})")

        # Print yellow box
        box_width = 70
        print(f"\n{Colors.BRIGHT_YELLOW}|{'=' * (box_width - 2)}|{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}|{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}       Confirm Interview Framework       {Colors.RESET}{Colors.BRIGHT_YELLOW}|{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}|{'=' * (box_width - 2)}|{Colors.RESET}")

        for line in content_lines:
            padding = box_width - len(line) - 4
            if padding < 0:
                padding = 0
            print(f"{Colors.BRIGHT_YELLOW}|{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}|{Colors.RESET}")

        print(f"{Colors.BRIGHT_YELLOW}|{'=' * (box_width - 2)}|{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}|{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}Confirm framework, continue to next step{Colors.RESET}{' ' * (box_width - 42)}{Colors.BRIGHT_YELLOW}|{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}|{Colors.RESET}{Colors.RED}  2{Colors.RESET} - {Colors.RED}Return to modify framework{Colors.RESET}{' ' * (box_width - 34)}{Colors.BRIGHT_YELLOW}|{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}|{'=' * (box_width - 2)}|{Colors.RESET}")

        choice = questionary.select(
            "Select operation",
            choices=["Confirm and use this framework", "Return to modify framework"],
        ).ask()
        if choice == "Return to modify framework" or choice is None:
            print("\n  [Hint] Interview framework has been saved, you can manually modify it and rerun this step")
            return state

        # Save interview framework to state
        state["interview_framework"] = framework

        # Save interview framework to file (required for step 5 validation)
        save_json(run_dir / "interview_framework.json", framework)

    # ── Part 1 Complete ── Skip Part 2 (Expert Interviews)?
    if resume_part > 2:
        if not interview_records:
            interview_records = []
        print(f"[Skipped] Expert interviews already executed ({len(interview_records)} records)")
        # Part 2 skipped, these variables won't be used (they are only used in the expert loop)
        max_turns = 8  # Placeholder default value
        min_follow_ups = 3
        max_follow_ups = 5
    else:
        # ============================================================
        # Interview dynamics settings (must be before the interview loop)
        # ============================================================
        print("\n[Interview Dynamics Settings]")
        print("These settings control the depth and breadth of expert interviews.")

    max_turns = ask_integer(
        "Maximum conversation turns per expert",
        default=8,
        min_val=5,
        max_val=50,
    )

    min_follow_ups = ask_integer(
        "Minimum follow-up questions per topic",
        default=3,
        min_val=2,
        max_val=10,
    )

    # max_follow_ups must be > min_follow_ups, default = min_follow_ups + 2
    max_follow_ups_default = min_follow_ups + 2
    max_follow_ups = ask_integer(
        "Maximum follow-up questions per topic",
        default=max_follow_ups_default,
        min_val=min_follow_ups + 1,
        max_val=20,
    )

    print(f"\n  Interview dynamics settings:")
    print(f"    Max conversation turns/expert: {Colors.BRIGHT_RED}{Colors.BOLD}{max_turns}{Colors.RESET}")
    print(f"    Min follow-ups per topic: {Colors.BRIGHT_RED}{Colors.BOLD}{min_follow_ups}{Colors.RESET}")
    print(f"    Max follow-ups per topic: {Colors.BRIGHT_RED}{Colors.BOLD}{max_follow_ups}{Colors.RESET}")

    # ============================================================
    # Part 4: Conduct Interviews with Each Expert
    # ============================================================
    print("\n" + "=" * 60)
    print("  [Part 3] Expert Deep Interviews")
    print("=" * 60)
    print()
    print("Now we will conduct multi-round deep interviews with each expert.")
    print("Each expert will answer according to each question in the interview framework.")
    print("**Important**: Experts must answer in depth and specifically, no vague talking.")
    print()

    interview_records = []

    # 生成时间戳用于 JSONL 文件命名
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for expert in experts:
        print(f"\n{'='*60}")
        print(f"  Interviewing expert: {expert.name}")
        print(f"  Organization: {expert.org_type} | Expertise: {expert.expertise}")
        print(f"{'='*60}")

        # 检查 JSONL 增量备份状态
        jsonl_path = run_dir / f"{expert.id}_interview_{timestamp}.jsonl"
        status = _check_jsonl_status(jsonl_path)
        resume_turn = 0

        if status['exists'] and not status['is_complete']:
            print(f"\n  {Colors.YELLOW}[Warning] 检测到专家 {expert.name} 存在未完成的访谈记录{Colors.RESET}")
            print(f"  已完成 {status['turns']} 个对话轮次")
            choice = questionary.select(
                "请选择操作",
                choices=["继续未完成的访谈", "重新开始（删除旧记录）"]
            ).ask()
            if choice == "继续未完成的访谈":
                resume_turn = status['turns']
            else:
                _cleanup_jsonl(jsonl_path)
                resume_turn = 0

        record = conduct_interview_with_expert(
            project=project,
            expert=expert,
            interview_framework=framework,
            providers=providers,
            max_turns=max_turns,
            min_follow_ups_per_topic=min_follow_ups,
            max_follow_ups_per_topic=max_follow_ups,
            jsonl_path=jsonl_path,
            resume_turn=resume_turn,
        )
        interview_records.append(record)

        # 访谈完成后清理 JSONL（数据已转换到 interview_records.json）
        _cleanup_jsonl(jsonl_path)

        print(f"  [Complete] Expert {expert.name} interview completed")

    # Generate and save individual expert dialogue records
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / state.get("run_id", "")))
    # Save raw interview records as JSON
    save_json(run_dir / "interview_records.json", {
        "framework_title": framework.get("framework_title", ""),
        "interview_framework": framework,
        "records": interview_records,
    })

    # Save each expert's dialogue as separate markdown file
    for record in interview_records:
        expert_id = record.get("expert_id", "E00")
        expert_name = record.get("expert_name", "unknown")

        # Generate dialogue content for this expert (with project context)
        dialogue_content = generate_expert_dialogue(record, framework, project)

        # File format: E01_dialogue_20260418_223045.md
        dialogue_filename = f"{expert_id}_dialogue_{timestamp}.md"
        dialogue_path = run_dir / dialogue_filename
        dialogue_path.write_text(dialogue_content, encoding='utf-8')
        print(f"  [Saved] {expert_name}'s interview record: {dialogue_filename}")

    state["interview_records"] = interview_records

    # ── Part 2 End ── Enter Part 3 (Delphi Configuration)
    # (else: block already closed after expert loop)

    # ── Part 3: Delphi Round Configuration ── Skip?
    if resume_part > 3:
        if not rounds_config:
            print("[Error] Cannot restore round configuration")
            return state
        print("[Skipped] Delphi round configuration already completed, using existing configuration")
        # rounds_config is already a dict, need to rebuild as RoundsConfig object
        # scoring_dimensions are computed by Step 5 Part 2 AHP algorithm, no longer read from rounds.json
        from models import RoundsConfig as RC
        rounds_obj = RC(
            round_1_turns=rounds_config.get("round_1", {}).get("turns", 5),
            round_2_dimensions=[],  # Computed by AHP in Step 5
            convergence_threshold=rounds_config.get("convergence_threshold", 0.5),
            max_rounds=rounds_config.get("max_rounds", 3),
            max_turns_per_expert=rounds_config.get("interview_dynamics", {}).get("max_turns_per_expert", 20),
            min_follow_ups_per_topic=rounds_config.get("interview_dynamics", {}).get("min_follow_ups_per_topic", 3),
            max_follow_ups_per_topic=rounds_config.get("interview_dynamics", {}).get("max_follow_ups_per_topic", 8),
        )
        state["rounds"] = rounds_obj
        # Jump to step completion
        print("\n" + "=" * 60)
        print("  Step 4 Complete!")
        print("=" * 60)
        return state

    # ============================================================
    # Part 3: Delphi Round Configuration
    # ============================================================
    print("\n" + "=" * 60)
    print("  [Delphi Round Configuration]")
    print("=" * 60)

    print("\nDelphi round settings:")

    # Round 1 settings
    round_1_turns_options = [str(i) for i in range(1, 11)]
    round_1_turns_choice = questionary.select(
        "Round 1 interview turns",
        choices=round_1_turns_options,
    ).ask()
    round_1_turns = int(round_1_turns_choice) if round_1_turns_choice else len(framework.get("questions", []))

    convergence_threshold = ask_float("Convergence threshold CV", 0.5, 0.1, 1.0)

    max_rounds_options = [str(i) for i in range(2, 6)]
    max_rounds_choice = questionary.select(
        "Maximum number of rounds",
        choices=max_rounds_options,
    ).ask()
    max_rounds = int(max_rounds_choice) if max_rounds_choice else 3

    # Scoring dimensions are computed by Python AHP in Step 5, not configured here.
    # Create config (round_2_dimensions will be generated in Step 5 Part 2)
    rounds_config = RoundsConfig(
        round_1_turns=round_1_turns,
        round_2_dimensions=[],  # Computed by AHP algorithm in Step 5
        convergence_threshold=convergence_threshold,
        max_rounds=max_rounds,
        max_turns_per_expert=max_turns,
        min_follow_ups_per_topic=min_follow_ups,
        max_follow_ups_per_topic=max_follow_ups,
    )

    state["rounds"] = rounds_config

    # Save to run directory
    save_json(run_dir / "rounds.json", rounds_config.to_dict())

    print("\n" + "=" * 60)
    print("  Step 4 Complete!")
    print("=" * 60)
    print(f"\n  Interview Framework: {framework.get('framework_title', 'Unnamed')}")
    print(f"  Interviewed Experts: {len(interview_records)} experts")
    print(f"  Dynamic interview settings:")
    print(f"    Max conversation turns/expert: {max_turns}")
    print(f"    Min follow-ups per topic: {min_follow_ups}")
    print(f"    Max follow-ups per topic: {max_follow_ups}")
    print(f"\n  Files saved:")
    print(f"    - interview_framework.json")
    print(f"    - interview_records.json")
    print(f"    - E01_dialogue_{timestamp}.md ...")
    print(f"    - E0{len(interview_records)}_dialogue_{timestamp}.md ...")

    return state
