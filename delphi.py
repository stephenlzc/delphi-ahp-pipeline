"""
Delphi method implementation.
"""
from __future__ import annotations

import re
import random
from typing import List, Tuple, Dict, Optional
from models import Expert, Factor, Transcript, Score


def _lang_instruction(lang: str) -> str:
    """Return language instruction block for prompts."""
    if lang == "en":
        return "## Response Language\nEnglish (concise and professional)\n"
    return "## Response Language\nChinese (concise and professional)\n"


def build_factor_extraction_prompt(
    expert_name: str,
    expert_pro: str,
    interview_text: str,
    research_topic: str,
    delphi_lang: str = "zh"
) -> str:
    """
    Build a prompt for LLM to extract evaluation factors from interview text.

    This prompt follows management/statistics expert principles:
    - Factor identification based on content analysis
    - No scoring, no weighting — pure qualitative extraction
    - Factors should be distinct, measurable concepts relevant to the research topic
    """
    prompt = f"""## Role

You are a senior expert with deep background in the intersection of management and statistics, specializing in:
- Factor identification and structured analysis in Delphi Method
- Factor decomposition and hierarchy construction in AHP
- Indicator system design in Multi-Criteria Decision Analysis (MCDA)
- Higher education management and research performance evaluation

## Task

You need to identify evaluation factors related to the research topic from the following expert interview records.
**Factors** refer to: key dimensions or characteristics that reflect team quality, contribution, or potential in the context of higher education research team performance evaluation.

## Research Topic
{research_topic}

## Expert Information
- Name: {expert_name}
- Expert Profile: {expert_pro if expert_pro else '(not provided)'}

## Interview Text

{interview_text}

## Extraction Requirements

1. **Factors SHOULD**:
   - Directly or indirectly reflect a dimension of research team performance
   - Have some degree of differentiation (different teams vary on this factor)
   - Have independent meaning in the evaluation system (not highly overlapping with other factors)
   - Be concise and clear (each factor no more than 20 characters)

2. **Factors SHOULD NOT**:
   - Be too abstract or general (e.g., "management level" without specific dimensions)
   - Be just sub-concepts of another factor (avoid nesting)
   - Be content unrelated to the research topic

3. **Extraction Quantity**: Extract 3-8 meaningful factors based on text content. More if content is rich, fewer if text is brief. **Do not fabricate content that does not appear in the text**.

## Output Format (Strictly follow this JSON format, do not include any other content)

{{
  "factors": [
    {{"name": "Factor name 1", "description": "Brief description of factor (within 20 characters)"}},
    {{"name": "Factor name 2", "description": "Brief description of factor (within 20 characters)"}}
  ]
}}

{_lang_instruction(delphi_lang)}"""
    return prompt


def parse_factor_extraction_response(response: str) -> Tuple[List[Dict], str]:
    """
    Parse extracted factors from LLM response.

    Returns:
        Tuple of (factors_list, error_message)
        factors_list: [{"name": ..., "description": ...}, ...]
        error_message: empty string if success
    """
    from llm import parse_json_response

    data = parse_json_response(response)
    if not data or not isinstance(data, dict):
        return [], f"JSON parsing failed, raw response: {response[:200]}"

    factors = data.get("factors", [])
    if not isinstance(factors, list) or len(factors) == 0:
        return [], "LLM did not return a valid factors list"

    # Validate each factor
    valid_factors = []
    for f in factors:
        if isinstance(f, dict) and f.get("name"):
            name = str(f["name"]).strip()
            desc = str(f.get("description", "")).strip()[:50]
            if 1 < len(name) <= 30:
                valid_factors.append({"name": name, "description": desc})

    if not valid_factors:
        return [], "LLM returned empty or invalid factors list"

    return valid_factors, ""


def build_delphi_prompt(
    project: dict,
    expert: dict,
    interview_framework: dict = None,
    current_question_index: int = 0,
    delphi_lang: str = "zh"
) -> str:
    """
    Build the Delphi round 1 prompt for an expert.
    Uses the expert's PRO field and interview framework for detailed prompting.

    Args:
        project: Project config dict
        expert: Expert config dict
        interview_framework: Interview framework dict (from step 4)
        current_question_index: Current question index (0-based)
        delphi_lang: Output language for Delphi responses ("zh" or "en")

    Returns:
        Formatted prompt string
    """
    answer_lang = "Chinese" if delphi_lang == "zh" else "English"

    # Get the expert's professional profile (PRO)
    pro = expert.get("pro", "")
    pro_section = f"\n\n## Your Expert Profile\n{pro}\n" if pro else ""

    # Build questions section
    if interview_framework and "questions" in interview_framework:
        # Use interview framework
        framework_title = interview_framework.get("framework_title", "Interview Framework")
        intro = interview_framework.get("introduction", "")
        closing = interview_framework.get("closing", "")

        # Build questions text
        questions_text_parts = []

        # Opening
        opening_qs = [q for q in interview_framework["questions"] if q.get("type") == "opening"]
        if opening_qs:
            questions_text_parts.append("[Opening Questions]")
            for q in opening_qs:
                questions_text_parts.append(f"\n{q.get('id')}. {q.get('question')}")

        # Core
        core_qs = [q for q in interview_framework["questions"] if q.get("type") == "core"]
        if core_qs:
            questions_text_parts.append("\n\n[Core Questions]")
            for q in core_qs:
                questions_text_parts.append(f"\n{q.get('id')}. {q.get('question')}")
                # Add follow-ups hint
                follow_ups = q.get("follow_ups", [])
                if follow_ups:
                    questions_text_parts.append(f"   Hint: {', '.join(follow_ups[:2])}")

        # Closing
        closing_qs = [q for q in interview_framework["questions"] if q.get("type") == "closing"]
        if closing_qs:
            questions_text_parts.append("\n\n[Closing Questions]")
            for q in closing_qs:
                questions_text_parts.append(f"\n{q.get('id')}. {q.get('question')}")

        questions_text = "\n".join(questions_text_parts)

        questions_section = f"""

## Interview Framework

This interview uses "{framework_title}":

{intro}

{questions_text}

{closing}
"""

    else:
        # Fallback to simple research questions
        questions = "\n".join([
            f"{i+1}. {q}"
            for i, q in enumerate(project.get("research_questions", []))
        ])

        questions_section = f"""

## Research Questions

Please provide in-depth analysis and insights based on your professional knowledge and experience:

{questions}
"""

    prompt = f"""## Role
{pro_section}

## Your Basic Information
- Position/Role: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')} (located in {expert.get('region', '')})
- Expertise: {expert.get('expertise', '')}
- Scoring Tendency: {expert.get('scoring_bias', 'moderate')}

## Research Project Information

[Research Topic] {project['title']}
[Analysis Framework] {project.get('framework', 'Unknown')}
[Research Background]
{project['background']}
[Research Purpose]
{project['purpose']}
[Research Boundaries/Scope]
{project.get('boundaries', 'Unknown')}

{questions_section}

## Interview Requirements

1. Please analyze each question from multiple perspectives based on your professional background and practical experience
2. Identify key factors (Factors) affecting the research topic and explain:
   - The specific meaning of each factor
   - The importance of the factor and reasons
   - The relationship between this factor and other factors
3. Please answer in a structured way (using numbered lists is recommended)
4. Recommended number of factors: 5-10

## Response Language
{answer_lang}
"""
    return prompt


def extract_factors(answer: str, expert: dict, start_id: int = 1) -> List[Factor]:
    """
    Extract factors from expert's Delphi round 1 answer.

    Args:
        answer: Expert's text answer
        expert: Expert config dict
        start_id: Starting factor ID number

    Returns:
        List of extracted Factor objects
    """
    factors = []
    lines = answer.split('\n')

    factor_id = start_id
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match numbered or bulleted factors
        patterns = [
            r'^\d+[.、]\s*([^\n：:]+)',
            r'^[-*]\s*([^\n：:]+)',
            r'^#{1,3}\s*([^\n：:]+)',
        ]

        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                name = match.group(1).strip()
                # Clean up the name
                name = re.split(r'[：:]', name)[0].strip()
                name = re.split(r'\(', name)[0].strip()

                if 1 < len(name) < 50:
                    factors.append(Factor(
                        id=f"F{factor_id:02d}",
                        name=name,
                        description=line[:100],
                        source=f"专家{expert['id']}"
                    ))
                    factor_id += 1
                break

    # Fallback if no factors extracted
    if not factors:
        factors = [
            Factor(
                id=f"F{factor_id:02d}",
                name="Technology Innovation Factor",
                description="Extracted from answer",
                source=f"Expert {expert['id']}"
            ),
            Factor(
                id=f"F{factor_id+1:02d}",
                name="Market Demand Factor",
                description="Extracted from answer",
                source=f"Expert {expert['id']}"
            ),
        ]

    return factors[:10]  # Limit to 10 factors per expert


def build_scoring_prompt(
    expert: dict,
    factor: Factor,
    dimensions: List[dict],
    delphi_lang: str = "zh"
) -> str:
    """
    Build the scoring prompt for Delphi round 2.

    LLM only outputs raw scores (1-10) for each dimension; total scores and weight calculations
    are entirely done by Python. Do not reveal any scores or weight information in the prompt.

    Args:
        expert: Expert config dict
        factor: Factor to score
        dimensions: List of scoring dimensions (each has name and weight)
        delphi_lang: Output language for Delphi responses ("zh" or "en")

    Returns:
        Formatted scoring prompt
    """
    dim_text = "\n".join([f"- {d['name']}" for d in dimensions])

    answer_lang = "Chinese" if delphi_lang == "zh" else "English"

    pro = expert.get("pro", "")
    pro_section = f"\n\n## Your Expert Profile\n{pro}\n" if pro else ""

    prompt = f"""## Role

You are a senior expert with deep background in the intersection of management and statistics, specializing in:
- Delphi Method expert scoring and opinion convergence analysis
- AHP judgment matrix construction and consistency testing
- Weight assignment and comprehensive scoring calculation in MCDA
- Higher education management and research performance evaluation

During the scoring process, you always follow:
- Based on empirical evidence rather than speculation
- Transparent scoring logic with documented reasoning
- Cautious attitude toward uncertain issues

{pro_section}

## Your Basic Information
- Name: {expert.get('name', '')}
- Position/Role: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')} (located in {expert.get('region', '')})
- Expertise: {expert.get('expertise', '')}
- Scoring Tendency: {expert.get('scoring_bias', 'moderate')}

## Factor to Score

Factor Name: {factor.name}
Factor Description: {factor.description}

## Scoring Dimensions (Please provide raw scores for each dimension, 1-10, 10 is highest)

{dim_text}

## Scoring Principles

1. **Independent Scoring**: Score each dimension independently, without being affected by other dimensions
2. **Professional Judgment**: Combine your academic background, industry experience, and the practical significance of this factor in higher education research evaluation
3. **Accurate Reflection**: If uncertain about a dimension, you may make comprehensive judgments combining related dimensions, but must explain in the reasoning
4. **No Calculation**: Do not calculate weighted total scores or apply any weights yourself; only provide raw scores for each dimension

## Output Format (Strictly follow this JSON format, do not include any other content)

{{
  "dimension_scores": {{
    "Strategic Alignment": 8,
    "Performance Contribution": 7,
    "Verifiability": 6,
    "Classification Adaptability": 7,
    "Sustainable Development Value": 8
  }},
  "reasoning": "Overall reasoning for scoring (within 100 characters, concise)"
}}

## Response Language
{answer_lang}
"""
    return prompt


def parse_score_response(response: str, default_score: float = 7.0) -> Tuple[Dict[str, float], str]:
    """
    Parse dimension scores from LLM response.

    LLM 返回各维度的原始分（1-10），总分由 Python 计算。

    Args:
        response: LLM response text
        default_score: Default score per dimension if parsing fails

    Returns:
        Tuple of (dimension_scores_dict, reasoning)
        dimension_scores_dict: {dim_name: raw_score}
    """
    from llm import parse_json_response

    data = parse_json_response(response)
    if data and isinstance(data, dict):
        try:
            dim_scores = data.get("dimension_scores", {})
            if isinstance(dim_scores, dict) and dim_scores:
                # Clamp each dimension score to 1-10
                clamped = {k: max(1.0, min(10.0, float(v))) for k, v in dim_scores.items()}
                reasoning = data.get("reasoning", "")
                return clamped, reasoning
        except (ValueError, TypeError):
            pass

    # Fallback: return empty dict, caller will use default
    return {}, response[:100]


def parse_pairwise_comparison_response(response: str, default_value: float = 1.0) -> float:
    """
    Parse pairwise comparison value from LLM response.

    Saaty scale:
    1 = equal importance
    3 = moderate importance
    5 = strong importance
    7 = very strong importance
    9 = extreme importance
    (2, 4, 6, 8 = intermediate values)

    Args:
        response: LLM response text
        default_value: Default value if parsing fails

    Returns:
        Comparison value (1-9 or reciprocal)
    """
    from llm import parse_json_response

    data = parse_json_response(response)
    if data and isinstance(data, dict):
        try:
            value = float(data.get("value", default_value))
            # Clamp to Saaty scale (1-9)
            value = max(1.0, min(9.0, value))
            return value
        except (ValueError, TypeError):
            pass

    # Try to parse directly from text
    import re
    match = re.search(r'(\d+\.?\d*)', response)
    if match:
        try:
            value = float(match.group(1))
            divisor = min(value, 100)
            if divisor == 0:
                return default_value
            # If value > 9, assume it's a reciprocal
            if value > 9:
                value = 1.0 / divisor
            return max(1.0, min(9.0, value))
        except ValueError:
            pass

    return default_value


def build_pairwise_comparison_prompt(
    expert: dict,
    criteria: List[dict],
    comparison_pair: Tuple[int, int],
    project_context: str = "",
    delphi_lang: str = "zh"
) -> str:
    """
    Build prompt for pairwise comparison of criteria.

    Args:
        expert: Expert config dict
        criteria: List of criteria dicts with id and name
        comparison_pair: Tuple of (index1, index2) for the pair to compare
        project_context: Optional project context string
        delphi_lang: Output language for Delphi responses ("zh" or "en")

    Returns:
        Formatted prompt string
    """
    answer_lang = "Chinese" if delphi_lang == "zh" else "English"

    pro = expert.get("pro", "")
    pro_section = f"\n\n## Your Expert Profile\n{pro}\n" if pro else ""

    idx1, idx2 = comparison_pair
    c1 = criteria[idx1]
    c2 = criteria[idx2]

    prompt = f"""## Role
{pro_section}

## Your Basic Information
- Name: {expert.get('name', '')}
- Position/Role: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')} (located in {expert.get('region', '')})
- Expertise: {expert.get('expertise', '')}
- Scoring Tendency: {expert.get('scoring_bias', 'moderate')}

{project_context}

## Pairwise Comparison Judgment

Please judge the relative importance between the following two criteria:

**Criterion A**: {c1.get('name', 'Criterion 1')}
   - Description: {c1.get('description', 'None')}

**Criterion B**: {c2.get('name', 'Criterion 2')}
   - Description: {c2.get('description', 'None')}

## Saaty Importance Scale

Please use the following scale to judge the importance of A relative to B:

| Scale Value | Meaning |
|:---:|:---|
| 1 | A and B are equally important |
| 3 | A is slightly more important than B |
| 5 | A is clearly more important than B |
| 7 | A is strongly more important than B |
| 9 | A is extremely more important than B |
| 2, 4, 6, 8 | The importance of A relative to B is between the above adjacent judgments |

If B is more important than A, please use reciprocals from 1/2 to 1/9.

## Output Format

Return only JSON format:
{{"value": number, "reasoning": "Judgment reasoning (within 30 characters)"}}

Example: If you think A is clearly more important than B, return {{"value": 5, "reasoning": "A is more critical in this research field"}}
If you think B is clearly more important than A, return {{"value": 0.2, "reasoning": "B has wider application"}}

## Response Language
{answer_lang}
"""
    return prompt


def build_criteria_extraction_prompt(
    factors: List[Factor],
    research_topic: str,
    framework: str = "",
    delphi_lang: str = "zh"
) -> str:
    """
    Build a prompt for LLM to extract criteria (Criteria Layer) from identified factors.

    The LLM should cluster/group factors into higher-level criteria dimensions.
    Each criteria should have 2-7 factors beneath it.

    Args:
        factors: List of identified factors (alternative layer)
        research_topic: Research topic title
        framework: Optional analytical framework
        delphi_lang: Output language for Delphi responses ("zh" or "en")

    Returns:
        Formatted prompt string
    """
    factor_text = "\n".join([f"- **{f.name}**: {f.description}" for f in factors])

    prompt = f"""## Role

You are a senior expert with deep background in the intersection of management and statistics, specializing in:
- Factor identification and structured analysis in Delphi Method
- Factor decomposition and hierarchy construction in AHP
- Indicator system design in Multi-Criteria Decision Analysis (MCDA)
- Higher education management and research performance evaluation

## Task

You need to cluster the identified evaluation factors into higher-level **criteria dimensions**.
The criteria layer of the AHP hierarchy is a mid-level evaluation dimension distilled from factors (alternative layer),
with each criterion containing 2-7 interrelated factors.

## Research Information

- Research Topic: {research_topic}
- Analysis Framework: {framework if framework else '(not specified)'}

## Identified Evaluation Factors (Alternative Layer)

{factor_text}

## Clustering Requirements

1. **Number of Criteria**: Naturally cluster based on the semantic structure of factors, recommend **3-7 criteria**.
   - If total factors are many (more than 15), can appropriately have more, but not exceed 7
   - If total factors are few (less than 10), can merge into 2-3 criteria
   - Each criterion must contain at least **2 factors** (single-factor criteria are meaningless, should be merged with other criteria)
   - Each criterion should contain at most **about 8 factors** (if too many, consider splitting)
2. **Criterion Naming**: Concise and clear, reflecting the core meaning of the dimension (e.g., "Technical Feasibility", "Economic Benefits", "Team Management")
3. **Factor Assignment**: Each factor must belong to and only to one criterion, assigned by semantics rather than simple keywords
4. **Criterion Description**: One sentence description per criterion (within 20 characters)
5. **Reasonableness Check**: The criteria layer should cover the main evaluation dimensions of the research topic, classification should have logical basis rather than mechanical division
6. **AHP Practice Constraint**: Criteria layer should not exceed 7, otherwise the cognitive burden of pairwise comparisons is too heavy and consistency is difficult to guarantee

## Output Format (Strictly follow this JSON format, do not include any other content)

{{
  "criteria": [
    {{
      "name": "Criterion Name 1",
      "description": "Brief description of criterion (within 20 characters)",
      "factor_ids": ["F01", "F03", "F05"]
    }},
    {{
      "name": "Criterion Name 2",
      "description": "Brief description of criterion (within 20 characters)",
      "factor_ids": ["F02", "F04"]
    }}
  ]
}}

{_lang_instruction(delphi_lang)}"""
    return prompt


def parse_criteria_extraction_response(
    response: str,
    factor_id_map: Dict[str, Factor]
) -> Tuple[List[dict], List[dict], str]:
    """
    Parse extracted criteria from LLM response.

    Args:
        response: LLM response text
        factor_id_map: Mapping from factor name to Factor object

    Returns:
        Tuple of (criteria_list, updated_alternatives, error_message)
        - criteria_list: [{"name": ..., "description": ..., "factor_ids": [...]}]
        - updated_alternatives: same factors but with belongs_to_criteria filled
        - error_message: empty string if success
    """
    from llm import parse_json_response

    data = parse_json_response(response)
    if not data or not isinstance(data, dict):
        return [], [], f"JSON parsing failed, raw response: {response[:200]}"

    raw_criteria = data.get("criteria", [])
    if not isinstance(raw_criteria, list) or len(raw_criteria) == 0:
        return [], [], "LLM did not return a valid criteria list"

    # Validate and build criteria list
    criteria_list = []
    all_assigned_factor_ids = set()
    valid_factor_ids = set(factor_id_map.keys())

    for c in raw_criteria:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        name = str(c["name"]).strip()
        desc = str(c.get("description", "")).strip()[:20]
        factor_ids = c.get("factor_ids", [])

        # Validate factor_ids: keep only those that exist in factor_id_map
        valid_ids = []
        for fid in factor_ids:
            fid_str = str(fid).strip()
            if fid_str in valid_factor_ids:
                valid_ids.append(fid_str)
                all_assigned_factor_ids.add(fid_str)

        # Enforce: each criterion must have at least 2 factors
        if len(valid_ids) < 2:
            continue  # skip criteria with fewer than 2 valid factors

        criteria_list.append({
            "name": name,
            "description": desc,
            "factor_ids": valid_ids,
        })

    if not criteria_list:
        return [], [], "LLM returned empty or invalid criteria list"

    # Validate criteria count: should be 3~7
    if len(criteria_list) < 3:
        return [], [], f"LLM returned insufficient criteria ({len(criteria_list)}), at least 3 criteria required"

    if len(criteria_list) > 7:
        return [], [], f"LLM returned too many criteria ({len(criteria_list)}), maximum 7 criteria"

    # Check for unassigned factors
    total_factors = len(factor_id_map)
    if len(all_assigned_factor_ids) < total_factors:
        unassigned = [fid for fid in factor_id_map if fid not in all_assigned_factor_ids]
        return [], [], f"{len(unassigned)} factors are not assigned to any criterion: {unassigned}, please ensure every factor has a belonging"

    # Build updated alternatives (alternatives with belongs_to_criteria filled)
    updated_alternatives = []
    for fid, factor in factor_id_map.items():
        # Find which criteria this factor belongs to
        belongs = ""
        for c in criteria_list:
            if fid in c["factor_ids"]:
                # Find or create criteria id (C1, C2, ...)
                criteria_id = f"C{criteria_list.index(c) + 1:02d}"
                belongs = criteria_id
                break
        updated_alternatives.append({
            "id": factor.id,
            "name": factor.name,
            "description": factor.description or "",
            "belongs_to_criteria": belongs or "C1",
        })

    return criteria_list, updated_alternatives, ""


def generate_mock_answer(prompt: str) -> str:
    """
    Generate a fallback answer when API fails.

    Args:
        prompt: Original prompt

    Returns:
        Fallback answer text
    """
    return """Based on the given research background and professional analysis, I have identified the following key factors:

1. Technology Innovation Factor - including AI algorithm advances, computing power improvements, etc.
2. Market Demand Factor - changes in industry demand for new technology talent
3. Policy Support Factor - government policy guidance and support
4. Talent Cultivation Factor - adaptation and adjustment of higher education system
5. Industry Application Factor - practical application of new technologies in different fields

The above factors need to be comprehensively considered to form a complete research conclusion.
"""


def calculate_cv(scores: List[float]) -> float:
    """
    Calculate Coefficient of Variation for convergence check.

    Args:
        scores: List of scores

    Returns:
        CV value (lower = more convergent)
    """
    if len(scores) < 2:
        return 0.0

    mean = sum(scores) / len(scores)
    # Handle zero or near-zero mean to avoid division by zero
    if abs(mean) < 1e-10:
        return 0.0

    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std_dev = variance ** 0.5

    return std_dev / abs(mean)


def check_convergence(scores_by_factor: dict, threshold: float = 0.5) -> dict:
    """
    Check convergence for all factors.

    Args:
        scores_by_factor: Dict mapping factor_id to list of scores
        threshold: CV threshold for convergence

    Returns:
        Dict with convergence status for each factor
    """
    result = {}
    for factor_id, scores in scores_by_factor.items():
        cv = calculate_cv(scores)
        result[factor_id] = {
            "cv": cv,
            "converged": cv <= threshold,
            "scores": scores,
            "mean": sum(scores) / len(scores) if scores else 0,
        }
    return result


def summarize_viewpoints(conversation_history: List[dict], expert: dict, project: dict) -> str:
    """
    Based on conversation history, LLM generates expert viewpoint summary.

    Args:
        conversation_history: Conversation history list, each element contains question and answer
        expert: Expert config dict
        project: Project config dict

    Returns:
        Structured viewpoint summary string
    """
    from llm import call_llm, LLMError

    # Determine answer language from project delphi_lang
    delphi_lang = project.get("delphi_lang", "zh")
    answer_lang = "Chinese" if delphi_lang == "zh" else "English"

    # Build conversation text for the prompt
    conversation_text = ""
    for i, qa in enumerate(conversation_history):
        question = qa.get("question", "")
        answer = qa.get("answer", "")
        conversation_text += f"\n## Round {i+1} Q&A\n"
        conversation_text += f"[Question]: {question}\n"
        conversation_text += f"[Answer]: {answer}\n"

    # Build the summary prompt
    prompt = f"""## Research Topic
{project.get('title', 'Unknown')}

## Research Background
{project.get('background', 'Unknown')}

## Expert Information
- Name: {expert.get('name', '')}
- Position/Role: {expert.get('role', '')}
- Organization: {expert.get('org_type', '')} (located in {expert.get('region', '')})
- Expertise: {expert.get('expertise', '')}

## Conversation History

{conversation_text}

## Summary Requirements

Based on the above conversation history, please generate a structured summary of the expert's viewpoints, including:

1. **Main Viewpoints**: What are the expert's core viewpoints and positions? (List 3-5 key points)
2. **Key Insights**: What unique insights or perspectives did the expert provide? What particularly noteworthy views?
3. **Potential Contradictions**: Are there logical contradictions, inconsistencies, or areas needing further clarification in the expert's answers?
4. **Relationships with Other Factors**: Which factors does the expert believe are interrelated? How?

Please output the summary results in structured Markdown format.

## Output Language
{answer_lang}
"""

    system_prompt = "You are a professional Delphi method research analyst, skilled at extracting key viewpoints from expert conversations and providing structured summaries."

    # Get LLM settings from expert
    base_url = expert.get("base_url", "")
    api_key = expert.get("api_key", "")
    model = expert.get("model", "")

    # Call LLM
    try:
        response = call_llm(
            base_url=base_url,
            api_key=api_key,
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )
        return response
    except LLMError as e:
        return f"[Viewpoint summary generation failed: {str(e)}]"
