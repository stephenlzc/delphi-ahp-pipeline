"""
Step 5: Execute Pipeline - Hierarchical AHP
"""
from __future__ import annotations

import json
import questionary
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from models import Expert, Factor, Score, Project, RoundsConfig, Provider, ScoringDimension
from llm import call_llm, LLMError
from delphi import (
    build_pairwise_comparison_prompt,
    parse_pairwise_comparison_response,
    build_scoring_prompt,
    parse_score_response,
    build_factor_extraction_prompt,
    parse_factor_extraction_response,
    build_criteria_extraction_prompt,
    parse_criteria_extraction_response,
)
from ahp import run_hierarchical_ahp
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)


def print_step_header():
    """Print step 5 header."""
    print()
    print("-" * 60)
    print("  Step 5/8: AHP Hierarchy & Delphi Round 2")
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
    """Save JSON file with support for dataclasses and objects with __dict__."""
    from dataclasses import is_dataclass, asdict

    filepath.parent.mkdir(parents=True, exist_ok=True)

    def convert_to_dict(obj):
        """Convert dataclass or object with __dict__ to dict."""
        # Handle lists and tuples first - recurse into elements
        if isinstance(obj, (list, tuple)):
            return [convert_to_dict(v) for v in obj]
        # Handle dataclasses - use asdict but also capture dynamic attrs
        if is_dataclass(obj) and not isinstance(obj, type):
            # Get base dataclass fields
            result = asdict(obj)
            # Add dynamic attributes (those not in dataclass fields)
            dataclass_fields = set(result.keys())
            for key, value in obj.__dict__.items():
                if key not in dataclass_fields and not key.startswith('_'):
                    result[key] = convert_to_dict(value)
            return result
        elif hasattr(obj, '__dict__'):
            result = {}
            # Get all attributes including dynamic ones
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    if isinstance(value, (list, tuple)):
                        result[key] = [convert_to_dict(v) for v in value]
                    elif hasattr(value, '__dict__') or is_dataclass(value):
                        result[key] = convert_to_dict(value)
                    else:
                        result[key] = value
            return result
        elif isinstance(obj, dict):
            return {k: convert_to_dict(v) for k, v in obj.items()}
        return obj

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(convert_to_dict(data), f, ensure_ascii=False, indent=2)
    print(f"  [Saved] {filepath}")


def load_interview_records(run_dir: Path) -> dict:
    """Load interview records from step 4."""
    records_path = run_dir / "interview_records.json"
    if records_path.exists():
        try:
            with open(records_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [Error] Failed to read interview records: {e}")
            return {}
    return {}


def load_ahp_hierarchy(run_dir: Path) -> dict | None:
    """Load AHP hierarchy from step 5 Part 2."""
    hierarchy_path = run_dir / "ahp_hierarchy.json"
    if hierarchy_path.exists():
        try:
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [Error] Failed to read AHP hierarchy: {e}")
            return None
    return None


def resolve_expert_llm_config(expert: Expert, providers: Dict[str, Provider]) -> Tuple[str, str, str]:
    """
    Resolve expert LLM connection config with provider fallback.

    Priority:
    1) Expert-level fields (`base_url`, `api_key`, `model`)
    2) Provider-level fields from `providers[expert.provider]`
    """
    provider_cfg = providers.get(expert.provider) if isinstance(providers, dict) else None

    provider_base_url = ""
    provider_api_key = ""
    provider_default_model = ""
    if isinstance(provider_cfg, Provider):
        provider_base_url = provider_cfg.base_url or ""
        provider_api_key = provider_cfg.api_key or ""
        provider_default_model = provider_cfg.default_model or ""
    elif isinstance(provider_cfg, dict):
        provider_base_url = provider_cfg.get("base_url", "") or ""
        provider_api_key = provider_cfg.get("api_key", "") or ""
        provider_default_model = provider_cfg.get("default_model", "") or ""

    base_url = (expert.base_url or "").strip() or provider_base_url
    api_key = (expert.api_key or "").strip() or provider_api_key
    model = (expert.model or "").strip() or provider_default_model
    return base_url, api_key, model


def select_scoring_model(providers: Dict[str, Provider]) -> Tuple[str, str, str]:
    """
    Let user select a single LLM for all scoring (pairwise comparisons and factor scoring).
    Expert personas are still embedded in prompts; only one model is used for all calls.

    Returns:
        Tuple of (base_url, api_key, model_name)
    """
    # Collect all available (provider_key, model) combos with valid credentials
    choices = []
    for pkey, pval in providers.items():
        if not isinstance(pval, Provider):
            continue
        p_base = getattr(pval, "base_url", "") or ""
        p_key = getattr(pval, "api_key", "") or ""
        p_models = getattr(pval, "models", []) or []
        if p_base and p_key and p_models:
            for m in p_models:
                choices.append((pkey, m, p_base, p_key))

    if not choices:
        raise LLMError("No available LLM configuration, please configure a valid API provider in Step 2")

    # Format for questionary
    labeled = [f"{pkey}/{m}" for pkey, m, _, _ in choices]
    sel = questionary.select(
        "Please select LLM for alternative layer scoring (all experts share this model):",
        choices=labeled,
    ).ask()

    if sel is None:
        raise LLMError("User cancelled, stopping scoring")

    # Find selected combo
    for pkey, m, p_base, p_key in choices:
        if f"{pkey}/{m}" == sel:
            print(f"  Selected: {pkey} / {m}")
            return p_base, p_key, m

    raise LLMError("Selected LLM configuration not found")


def switch_expert_llm_config(
    failed_expert: Expert,
    all_experts: List[Expert],
    providers: Dict[str, Provider],
    task_desc: str,
    run_dir: Path,
) -> Tuple[str, str, str]:
    """
    When an LLM call fails, let user pick another expert's LLM config to retry.
    Updates both the in-memory expert object and experts.json on disk.

    Returns:
        Tuple of (new_base_url, new_api_key, new_model) to use for retry

    Raises:
        LLMError if user cancels or no config works
    """
    print(f"\n  [Error] {task_desc} LLM call failed")
    print(f"\n  Current expert '{failed_expert.name}' configuration:")
    cur_base_url, cur_api_key, cur_model = resolve_expert_llm_config(failed_expert, providers)
    print(f"    Provider: {failed_expert.provider or '(default)'}")
    print(f"    Model: {cur_model}")

    # Build list of other experts with working configs
    other_choices = []
    for e in all_experts:
        if e.id == failed_expert.id:
            continue
        url, key, model = resolve_expert_llm_config(e, providers)
        if model and url:
            other_choices.append((e, url, key, model))

    # Build list of available provider/model combinations from providers dict
    provider_model_choices = []
    for pkey, pval in providers.items():
        if not isinstance(pval, Provider):
            continue
        p_models = getattr(pval, "models", []) or []
        p_base = getattr(pval, "base_url", "") or ""
        p_key = getattr(pval, "api_key", "") or ""
        p_adapter = getattr(pval, "adapter", "") or ""
        if p_models and p_base and p_key:
            for m in p_models:
                provider_model_choices.append((pkey, m, p_base, p_key, p_adapter))

    # Build questionary choices
    choices = []
    if other_choices:
        for e, url, key, model in other_choices:
            choices.append(f"Borrow config from expert '{e.name}' ({e.provider}/{model})")
    if provider_model_choices:
        for pkey, m, p_base, p_key, p_adapter in provider_model_choices:
            choices.append(f"Switch to {pkey}/{m}")

    if not choices:
        raise LLMError(f"No other available LLM configuration, please configure a valid API provider in Step 2 first")

    choices.append("Cancel (skip this expert)")

    sel = questionary.select(
        "Please select replacement LLM configuration (will update expert config and retry):",
        choices=choices,
    ).ask()

    if sel is None or sel == "Cancel (skip this expert)":
        raise LLMError("User cancelled, stopping current evaluation")

    # Parse selection and update expert
    if sel.startswith("Borrow config"):
        for e, url, key, model in other_choices:
            if e.name in sel:
                failed_expert.provider = e.provider
                failed_expert.base_url = url
                failed_expert.api_key = key
                failed_expert.model = model
                print(f"  [Updated] Borrowed config from '{e.name}': {e.provider}/{model}")
                break
    else:
        # sel format: "Switch to {provider}/{model}"
        prefix = "Switch to "
        if sel.startswith(prefix):
            sel = sel[len(prefix):]
        pkey, m = sel.split("/", 1)
        pval = providers.get(pkey)
        if pval:
            failed_expert.provider = pkey
            failed_expert.base_url = getattr(pval, "base_url", "") or ""
            failed_expert.api_key = getattr(pval, "api_key", "") or ""
            failed_expert.model = m
            failed_expert.adapter = getattr(pval, "adapter", "") or ""
            print(f"  [Updated] Switched to {pkey}/{m}")

    # Persist updated expert config to experts.json
    _save_experts_list(all_experts, run_dir)

    new_base_url, new_api_key, new_model = resolve_expert_llm_config(failed_expert, providers)
    return new_base_url, new_api_key, new_model


def _save_experts_list(experts: List[Expert], run_dir: Path) -> None:
    """Save the expert list to experts.json, updating only the LLM config fields."""
    experts_file = run_dir / "experts.json"
    if experts_file.exists():
        with open(experts_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {"experts_count": 0, "experts": []}

    # Build id -> expert map from current in-memory list
    expert_map = {e.id: e for e in experts}

    # Update matching experts in the saved list
    for exp_dict in existing.get("experts", []):
        exp_id = exp_dict.get("id", "")
        if exp_id in expert_map:
            e = expert_map[exp_id]
            exp_dict["provider"] = e.provider
            exp_dict["base_url"] = e.base_url
            exp_dict["api_key"] = e.api_key
            exp_dict["model"] = e.model
            exp_dict["adapter"] = e.adapter

    save_json(experts_file, existing)


def extract_factors_from_interviews(interview_records: dict) -> List[Factor]:
    """
    Extract factors from interview records with source tracking.

    Each factor now includes source information indicating which expert
    and which round the factor was derived from.
    """
    factors = []
    factor_id_counter = 1

    records = interview_records.get("records", [])
    for record in records:
        expert_name = record.get("expert_name", "unknown")
        expert_id = record.get("expert_id", "E00")
        qa_pairs = record.get("qa_pairs", [])

        # Track sources for each answer segment
        answer_segments = []
        for qa in qa_pairs:
            answer = qa.get("answer", "")
            round_info = qa.get("round", "Round 1")
            question = qa.get("question", "")
            if answer:
                answer_segments.append({
                    "text": answer,
                    "round": round_info,
                    "question": question
                })

        # Combine answers for factor extraction
        combined_answer = "\n".join(seg["text"] for seg in answer_segments if seg["text"])

        if combined_answer:
            from delphi import extract_factors
            expert_dict = {"id": expert_id, "name": expert_name}
            extracted = extract_factors(combined_answer, expert_dict, factor_id_counter)

            # Add source tracking to each factor
            for factor in extracted:
                # Determine which round(s) this factor came from
                rounds_involved = list(set(
                    seg["round"] for seg in answer_segments
                    if seg["text"] and (seg["text"] in combined_answer or any(
                        keyword in combined_answer for keyword in factor.name.split()
                        if len(keyword) > 2
                    ))
                ))
                if not rounds_involved:
                    rounds_involved = ["Round 1"]

                # Build source information
                factor.source_expert = expert_id
                factor.source_expert_name = expert_name
                factor.source_rounds = rounds_involved
                factor.source_description = (
                    f"From expert '{expert_name}' (ID: {expert_id}), "
                    f"{', '.join(rounds_involved)} responses"
                )

            factors.extend(extracted)
            factor_id_counter += len(extracted)

    return factors[:20]


def generate_pairwise_comparisons(
    experts: List[Expert],
    criteria: List[dict],
    project_context: str,
    scoring_base_url: str,
    scoring_api_key: str,
    scoring_model: str,
) -> Tuple[Dict, List[dict]]:
    """
    Generate pairwise comparisons for criteria layer.
    All experts use the same single scoring model; expert persona is embedded in the prompt.

    Returns:
        Tuple of (comparisons_dict, expert_comparisons_list)
    """
    n = len(criteria)
    all_comparisons = []

    # Generate all pairs (i, j) where i < j
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]

    print(f"\n  Criteria layer pairwise comparisons: {len(pairs)} items/expert")
    print(f"  Using model: {scoring_model}")

    for expert in experts:
        print(f"\n  Getting criteria comparison judgments from {expert.name}...")

        expert_comparisons = []
        criteria_comparisons = {}

        for idx1, idx2 in pairs:
            c1 = criteria[idx1]
            c2 = criteria[idx2]

            print(f"    Comparing: {c1['name']} vs {c2['name']}")

            value = None
            for attempt in range(2):  # retry on network error
                try:
                    prompt = build_pairwise_comparison_prompt(
                        expert.to_dict(),
                        criteria,
                        (idx1, idx2),
                        project_context,
                        project.get("delphi_lang", "zh")
                    )

                    response = call_llm(
                        base_url=scoring_base_url,
                        api_key=scoring_api_key,
                        model=scoring_model,
                        prompt=prompt,
                    )

                    value = parse_pairwise_comparison_response(response)
                    break  # success, exit retry loop

                except LLMError as e:
                    if attempt == 0:
                        print(f"      [Error] {str(e)}, retrying...")
                        continue  # retry
                    # Second failure: use default
                    print(f"      [Warning] Still cannot get judgment after retry, using default value 1.0 (equally important)")
                    value = 1.0

            # Store comparison
            key = f"{idx1},{idx2}"
            criteria_comparisons[key] = value

            expert_comparisons.append({
                "pair": [c1["id"], c2["id"]],
                "value": value,
            })

            print(f"      Result: {value}")

        all_comparisons.append({
            "expert_id": expert.id,
            "expert_name": expert.name,
            "comparisons": expert_comparisons,
        })

    # Average comparisons across experts (P3: geometric mean preserves reciprocity)
    import math
    avg_comparisons = {}
    for idx1, idx2 in pairs:
        key = f"{idx1},{idx2}"
        pair_id = f"{criteria[idx1]['id']},{criteria[idx2]['id']}"
        values = []
        for ec in all_comparisons:
            for comp in ec["comparisons"]:
                if comp.get("pair") == [criteria[idx1]["id"], criteria[idx2]["id"]]:
                    values.append(comp.get("value", 1.0))
                    break
        if values:
            # Geometric mean: prod(values) ** (1/n)
            # Fall back to arithmetic if any value <= 0
            if all(v > 0 for v in values):
                avg_comparisons[key] = math.prod(values) ** (1.0 / len(values))
            else:
                avg_comparisons[key] = sum(values) / len(values)
        else:
            avg_comparisons[key] = 1.0

    return avg_comparisons, all_comparisons


def generate_alternative_scores(
    experts: List[Expert],
    factors: List[Factor],
    dimensions: List[dict],
    scoring_base_url: str,
    scoring_api_key: str,
    scoring_model: str,
) -> Tuple[Dict[str, float], List[dict]]:
    """
    Generate scores for alternatives (factors).
    All experts use the same single scoring model; expert persona is embedded in the prompt.
    LLM 只返回各维度的原始分（1-10），总分和权重计算全部由 Python 完成。

    Returns:
        Tuple of (average_scores_dict, expert_scores_list)
    """
    total_weight = sum(d.get("weight", 1.0) for d in dimensions)
    if total_weight <= 0:
        total_weight = len(dimensions)  # 等权fallback
    norm_weights = {d["name"]: d.get("weight", 1.0) / total_weight for d in dimensions}

    dim_names = [d["name"] for d in dimensions]

    all_scores = []

    print(f"\n  方案层评分共 {len(factors)} 个因素")
    print(f"  评分维度：{dim_names}")
    print(f"  归一化权重：{ {k: round(v, 4) for k, v in norm_weights.items()} }")
    print(f"  使用模型: {scoring_model}")

    for expert in experts:
        print(f"\n  正在获取 {expert.name} 的因素评分...")

        expert_scores = []

        for factor in factors:
            print(f"    评分因素: {factor.name}")

            dim_scores: Dict[str, float] = {}
            reasoning = ""

            for attempt in range(2):  # simple retry on network error
                try:
                    prompt = build_scoring_prompt(
                        expert.to_dict(),
                        factor,
                        dimensions,
                        project.get("delphi_lang", "zh")
                    )

                    response = call_llm(
                        base_url=scoring_base_url,
                        api_key=scoring_api_key,
                        model=scoring_model,
                        prompt=prompt,
                    )

                    raw_dim_scores, reasoning = parse_score_response(response)

                    # Verify LLM returned all configured dimensions
                    missing_dims = [d for d in dim_names if d not in raw_dim_scores]
                    if missing_dims or not raw_dim_scores:
                        if attempt == 0:
                            preview = response[:300].replace("\n", " ")
                            print(f"      [错误] LLM 返回无法解析或缺少维度：{missing_dims or '空响应'}")
                            print(f"      [提示] LLM 原始返回片段：{preview}")
                            continue  # retry once
                        # Second attempt failed: skip this factor with default score
                        print(f"      [警告] 重试后仍无法获取有效评分，跳过该因素（默认 7.0 分）")
                        for dn in dim_names:
                            dim_scores[dn] = 7.0
                        reasoning = "[跳过因素]"
                        break

                    # parse succeeded and all dims present
                    for dn in dim_names:
                        dim_scores[dn] = raw_dim_scores[dn]
                    break  # success, exit retry loop

                except LLMError as e:
                    if attempt == 0:
                        print(f"      [错误] {str(e)}，重试...")
                        continue  # retry
                    # Second failure: skip this factor with default score
                    print(f"      [警告] 重试后仍无法获取有效评分，跳过该因素（默认 7.0 分）")
                    for dn in dim_names:
                        dim_scores[dn] = 7.0
                    reasoning = "[跳过因素]"
                    break

            # ------------------------------------------------------------
            # Step 2: Python 计算加权总分（权重归一化后求内积）
            # ------------------------------------------------------------
            weighted_total = sum(
                dim_scores[dim_name] * norm_weights[dim_name]
                for dim_name in dim_names
            )
            # clamping 到 [1, 10]
            final_score = max(1.0, min(10.0, weighted_total))

            expert_scores.append({
                "factor_id": factor.id,
                "factor_name": factor.name,
                "dimension_scores": dim_scores,    # 各维度原始分（LLM输出）
                "dimension_weights": {k: round(v, 4) for k, v in norm_weights.items()},  # 归一化权重
                "weighted_score": round(final_score, 4),  # Python计算最终得分
                "reasoning": reasoning,
            })

            print(f"      维度原始分: {dim_scores}")
            print(f"      加权总分: {round(final_score, 2)}")

        all_scores.append({
            "expert_id": expert.id,
            "expert_name": expert.name,
            "scores": expert_scores,
        })

    # ------------------------------------------------------------
    # Step 3: 汇总所有专家对每个因素的加权总分（几何平均，P3）
    # ------------------------------------------------------------
    import math
    avg_scores = {}
    for factor in factors:
        weighted_scores = []
        for es in all_scores:
            for s in es["scores"]:
                if s["factor_id"] == factor.id:
                    weighted_scores.append(s["weighted_score"])
        if weighted_scores:
            # Geometric mean for ratio-scale aggregation (preserves proportionality)
            if all(w > 0 for w in weighted_scores):
                avg_scores[factor.id] = round(math.prod(weighted_scores) ** (1.0 / len(weighted_scores)), 4)
            else:
                avg_scores[factor.id] = round(sum(weighted_scores) / len(weighted_scores), 4)
        else:
            avg_scores[factor.id] = 7.0

    return avg_scores, all_scores


def generate_alternative_pairwise_comparisons(
    experts: List[Expert],
    criteria: List[dict],
    alternatives: List[dict],
    project_context: str,
    scoring_base_url: str,
    scoring_api_key: str,
    scoring_model: str,
) -> Tuple[Dict[str, Dict[str, float]], List[dict]]:
    """
    Generate pairwise comparisons for the alternative layer (P1: true AHP method).

    For each criterion, all alternatives belonging to that criterion are compared
    pairwise using Saaty 1-9 scale. Each expert provides comparisons for each
    criterion's alternative set; results are aggregated via geometric mean per
    expert's priority vector, then across experts via geometric mean.

    Returns:
        Tuple of (local_weights, expert_details)
        local_weights: {criterion_id: {alternative_id: local_weight}}
        expert_details: list of per-expert per-criterion comparison matrices
    """
    # Build alternatives_by_criteria mapping
    criteria_ids = [c["id"] for c in criteria]
    alternatives_by_criteria: Dict[str, List[dict]] = {}
    for alt in alternatives:
        crit_id = alt.get("belongs_to_criteria", criteria_ids[0] if criteria_ids else "C1")
        if crit_id not in alternatives_by_criteria:
            alternatives_by_criteria[crit_id] = []
        alternatives_by_criteria[crit_id].append(alt)

    import math

    # Compute pairwise pairs per criterion
    criterion_alt_pairs: Dict[str, List[Tuple[int, int]]] = {}
    for crit_id, alts in alternatives_by_criteria.items():
        n = len(alts)
        criterion_alt_pairs[crit_id] = [(i, j) for i in range(n) for j in range(i + 1, n)]

    print(f"\n  Alternative layer pairwise comparisons: {len(criteria)} criteria layers")
    for crit_id, pairs in criterion_alt_pairs.items():
        n_alts = len(alternatives_by_criteria.get(crit_id, []))
        print(f"    Criterion '{crit_id}': {n_alts} alternatives -> {len(pairs)} pairs")

    print(f"\n  Using model: {scoring_model}")

    # For each expert, for each criterion, build comparison matrix and compute local weights
    expert_details: List[dict] = []

    for expert in experts:
        print(f"\n  Getting alternative comparison judgments from {expert.name}...")

        expert_criterion_matrices: Dict[str, List[List[float]]] = {}
        expert_local_weights: Dict[str, Dict[str, float]] = {}

        for crit in criteria:
            crit_id = crit["id"]
            alts = alternatives_by_criteria.get(crit_id, [])
            n = len(alts)

            if n < 2:
                # Single alternative: weight = 1.0
                if alts:
                    expert_local_weights[crit_id] = {alts[0]["id"]: 1.0}
                continue

            pairs = criterion_alt_pairs.get(crit_id, [])

            # Build comparison matrix for this criterion's alternatives
            matrix = [[1.0 for _ in range(n)] for _ in range(n)]
            comparisons_record: List[dict] = []

            for idx1, idx2 in pairs:
                a1 = alts[idx1]
                a2 = alts[idx2]

                print(f"    比较 [{crit_id}] {a1['name']} vs {a2['name']}")

                value = None
                for attempt in range(2):  # retry on network error
                    try:
                        # Use pairwise comparison prompt adapted for alternatives
                        alt_comparison_pair = (idx1, idx2)
                        prompt = _build_alternative_pairwise_prompt(
                            expert.to_dict(),
                            alts,
                            alt_comparison_pair,
                            project_context,
                            crit["name"],
                        )

                        response = call_llm(
                            base_url=scoring_base_url,
                            api_key=scoring_api_key,
                            model=scoring_model,
                            prompt=prompt,
                        )

                        value = parse_pairwise_comparison_response(response)
                        break
                    except LLMError as e:
                        if attempt == 0:
                            print(f"      [错误] {str(e)}，重试...")
                            continue
                        print(f"      [警告] 重试后仍无法获取判断，使用默认值 1.0")
                        value = 1.0

                matrix[idx1][idx2] = value
                matrix[idx2][idx1] = 1.0 / value if value > 0 else 1.0
                comparisons_record.append({
                    "pair": [a1["id"], a2["id"]],
                    "value": value,
                })
                print(f"      结果: {value}")

            expert_criterion_matrices[crit_id] = matrix

            # Calculate local priority weights via geometric mean method
            from ahp import calculate_weights
            local_w = calculate_weights(matrix)
            alt_ids = [a["id"] for a in alts]
            expert_local_weights[crit_id] = {aid: round(local_w[i], 4) for i, aid in enumerate(alt_ids)}

        expert_details.append({
            "expert_id": expert.id,
            "expert_name": expert.name,
            "criterion_matrices": expert_criterion_matrices,
            "local_weights": expert_local_weights,
        })

    # Aggregate across experts via geometric mean for each criterion's alternative weights
    local_weights: Dict[str, Dict[str, float]] = {}
    for crit in criteria:
        crit_id = crit["id"]
        alts = alternatives_by_criteria.get(crit_id, [])
        if not alts:
            continue

        # Collect each expert's weight vector for this criterion
        expert_weight_vectors: List[Dict[str, float]] = []
        for ed in expert_details:
            ew = ed["local_weights"].get(crit_id, {})
            if ew:
                expert_weight_vectors.append(ew)

        if not expert_weight_vectors:
            # Fallback: equal weights
            local_weights[crit_id] = {a["id"]: round(1.0 / len(alts), 4) for a in alts}
            continue

        # Geometric mean per alternative across experts
        agg_weights: Dict[str, float] = {}
        for alt in alts:
            aid = alt["id"]
            values = [ew.get(aid, 0) for ew in expert_weight_vectors]
            valid = [v for v in values if v > 0]
            if valid:
                geo_mean = math.prod(valid) ** (1.0 / len(valid))
                agg_weights[aid] = round(geo_mean, 4)
            else:
                agg_weights[aid] = round(1.0 / len(alts), 4)

        # Renormalize so they sum to 1.0 within this criterion
        total = sum(agg_weights.values())
        if total > 0:
            agg_weights = {k: round(v / total, 4) for k, v in agg_weights.items()}

        local_weights[crit_id] = agg_weights

    return local_weights, expert_details


def _build_alternative_pairwise_prompt(
    expert: dict,
    alternatives: List[dict],
    comparison_pair: Tuple[int, int],
    project_context: str,
    criterion_name: str,
) -> str:
    """
    Build prompt for pairwise comparison of alternatives under a specific criterion.
    """
    language = expert.get("language", "zh-CN")
    answer_lang = "Chinese" if language == "zh-CN" else ("English" if language == "en-US" else "Chinese and English")

    pro = expert.get("pro", "")
    pro_section = f"\n\n## 您的专家画像\n{pro}\n" if pro else ""

    idx1, idx2 = comparison_pair
    a1 = alternatives[idx1]
    a2 = alternatives[idx2]

    return f"""## 角色设定
{pro_section}

## 您的基本信息
- 姓名：{expert.get('name', '')}
- 职位/角色：{expert.get('role', '')}
- 所属机构：{expert.get('org_type', '')}（位于 {expert.get('region', '')}）
- 专业领域：{expert.get('expertise', '')}
- 评分倾向：{expert.get('scoring_bias', 'moderate')}

{project_context}

## 方案层两两比较（在准则「{criterion_name}」下）

请您判断在"*{criterion_name}*"这个准则下，以下两个方案的相对优劣：

**方案 A**: {a1.get('name', '方案1')}
   - 描述: {a1.get('description', '无')}

**方案 B**: {a2.get('name', '方案2')}
   - 描述: {a2.get('description', '无')}

## Saaty 重要性标度

请使用以下标度来判断 A 相对于 B 在"*{criterion_name}*"准则下的优劣：

| 标度值 | 含义 |
|:---:|:---|
| 1 | A 和 B 同等重要 |
| 3 | A 略微优于 B |
| 5 | A 明显优于 B |
| 7 | A 强烈优于 B |
| 9 | A 极端优于 B |
| 2, 4, 6, 8 | A 相对于 B 的优劣在上述相邻判断之间 |

如果 B 比 A 更重要，请使用 1/2 到 1/9 的倒数。

## 输出格式

只返回 JSON 格式：
{{"value": 数字, "reasoning": "判断理由（30字以内）"}}

例如：如果您认为 A 比 B 明显重要，返回 {{"value": 5, "reasoning": "A在该维度表现更突出"}}
如果您认为 B 比 A 明显重要，返回 {{"value": 0.2, "reasoning": "B的应用范围更广"}}

## 回答语言
{answer_lang}
"""


def generate_criteria_comparison_table(run_dir: Path) -> str:
    """Generate criteria comparison matrix table."""
    comp_path = run_dir / "criteria_comparisons.json"
    if not comp_path.exists():
        return ""

    with open(comp_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    criteria = data.get("criteria", [])
    comparisons = data.get("comparisons", {})
    expert_comparisons = data.get("expert_comparisons", [])

    n = len(criteria)
    if n < 2:
        return ""

    lines = []
    lines.append("# 表1 准则层两两比较矩阵")
    lines.append("")
    lines.append("## 1.1 专家判断详情")
    lines.append("")

    # Build matrix for display
    header = "| 准则 A | 准则 B |"
    separator = "|---|---|"
    for ec in expert_comparisons:
        expert_name = ec.get("expert_name", f"专家{ec.get('expert_id', '?')}")
        header += f" {expert_name} |"
        separator += "---|"

    lines.append(header)
    lines.append(separator)

    # All pairs where i < j
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    for idx1, idx2 in pairs:
        c1 = criteria[idx1]
        c2 = criteria[idx2]
        key = f"{idx1},{idx2}"
        row = f"| {c1['name']} | {c2['name']} |"

        # Find values for each expert
        for ec in expert_comparisons:
            comps = ec.get("comparisons", [])
            # Find matching pair
            val = ""
            for comp in comps:
                if comp.get("pair") == [c1["id"], c2["id"]]:
                    val = str(comp.get("value", "-"))
                    break
                # Check reverse
                if comp.get("pair") == [c2["id"], c1["id"]]:
                    rev_val = comp.get("value", 1.0)
                    val = str(round(1.0 / rev_val, 2)) if rev_val != 0 else "-"
                    break
            row += f" {val} |"

        lines.append(row)

    lines.append("")
    lines.append("## 1.2 平均比较值矩阵")
    lines.append("")

    # Average matrix header
    avg_header = "| 准则 |"
    for c in criteria:
        avg_header += f" {c['name'][:8]} |"
    lines.append(avg_header)
    lines.append("|" + "|".join(["---"] * (n + 1)) + "|")

    # Average matrix rows
    for i, c1 in enumerate(criteria):
        row = f"| {c1['name']} |"
        for j, c2 in enumerate(criteria):
            if i == j:
                row += " 1.00 |"
            elif i < j:
                key = f"{i},{j}"
                val = comparisons.get(key, 1.0)
                row += f" {val:.2f} |"
            else:
                key = f"{j},{i}"
                val = comparisons.get(key, 1.0)
                row += f" {1.0/val:.2f} |" if val != 0 else " - |"
        lines.append(row)

    lines.append("")
    lines.append(f"*表1说明： Saaty 1-9 标度，值>1表示行准则比列准则更重要*")

    return "\n".join(lines)


def generate_criteria_weights_table(run_dir: Path) -> str:
    """Generate criteria weights table."""
    result_path = run_dir / "ahp_results.json"
    if not result_path.exists():
        return ""

    with open(result_path, 'r', encoding='utf-8') as f:
        result = json.load(f)

    criteria = result.get("criteria", [])
    consistency = result.get("criteria_consistency", {})

    lines = []
    lines.append("# 表2 准则层权重及一致性检验")
    lines.append("")
    lines.append("## 2.1 准则层权重")
    lines.append("")
    lines.append(f"| 编号 | 准则名称 | 权重 | 一致性比例(CR) | 检验结果 |")
    lines.append(f"|---|---|---|---|---|")

    for c in criteria:
        cr = c.get("cr", 0)
        passed = c.get("consistency_passed", False)
        status = "通过 ✓" if passed else f"未通过 ✗ (CR={cr:.4f})"
        lines.append(f"| {c['id']} | {c['name']} | {c['weight']:.4f} | {cr:.4f} | {status} |")

    lines.append("")
    lines.append("## 2.2 一致性检验汇总")
    lines.append("")
    lines.append(f"| 检验项目 | 数值 |")
    lines.append(f"|---|---|")
    lines.append(f"| λmax (最大特征值) | {consistency.get('lambda_max', 0):.4f} |")
    lines.append(f"| CI (一致性指标) | {consistency.get('ci', 0):.4f} |")
    lines.append(f"| CR (一致性比例) | {consistency.get('cr', 0):.4f} |")

    cr_val = consistency.get('cr', 0)
    passed = consistency.get('passed', False)
    lines.append(f"| 检验结论 | {'通过 (CR≤0.10) ✓' if passed else f'未通过 (CR={cr_val:.4f}>0.10) ✗'} |")

    lines.append("")
    lines.append(f"*表2说明： CR≤0.10 表示判断矩阵通过一致性检验，结果可接受*")

    return "\n".join(lines)


def generate_alternative_scores_table(run_dir: Path) -> str:
    """Generate alternative (factor) scores table — P1: pairwise comparison format."""
    score_path = run_dir / "alternative_scores.json"
    if not score_path.exists():
        return ""

    with open(score_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    criteria_ids = data.get("criteria_ids", [])
    alt_by_crit = data.get("alternatives_by_criteria", {})
    local_weights = data.get("local_weights", {})   # {crit_id: {alt_id: weight}}
    expert_details = data.get("expert_details", [])  # [{expert_name, local_weights}, ...]

    lines = []
    lines.append("# 表3 方案层因素评分表")
    lines.append("")
    lines.append("## 3.1 方案层局部权重（各准则下）")
    lines.append("")
    lines.append("*各方案在某准则下的权重表示该方案相对于同准则下其他方案的优先程度（0-1，归一化）*")
    lines.append("")

    # Per-criterion sub-tables
    for crit_id in criteria_ids:
        alts = alt_by_crit.get(crit_id, [])
        if not alts:
            continue
        crit_weights = local_weights.get(crit_id, {})

        lines.append(f"**准则 {crit_id}**")

        # Header
        header = "| 编号 | 方案名称 |"
        for ed in expert_details:
            en = ed.get("expert_name", "专家?")
            header += f" {en} |"
        header += " 聚合权重 |"
        lines.append(header)

        sep = "|---|---|"
        for _ in expert_details:
            sep += "---|"
        sep += "---|"
        lines.append(sep)

        # Rows
        for alt in alts:
            aid = alt.get("id", "?")
            aname = alt.get("name", "未知")
            row = f"| {aid} | {aname} |"
            for ed in expert_details:
                ew = ed.get("local_weights", {}).get(crit_id, {})
                w = ew.get(aid, 0.0)
                row += f" {w:.4f} |"
            row += f" {crit_weights.get(aid, 0.0):.4f} |"
            lines.append(row)

        lines.append("")

    lines.append("*表3说明： 各专家对同准则下方案进行两两比较，综合权重通过 Σ(准则权重×方案在准则下的局部权重) 计算*")

    return "\n".join(lines)


def generate_combined_weights_ranking_table(run_dir: Path) -> str:
    """Generate combined weights ranking table."""
    result_path = run_dir / "ahp_results.json"
    if not result_path.exists():
        return ""

    with open(result_path, 'r', encoding='utf-8') as f:
        result = json.load(f)

    criteria = result.get("criteria", [])
    alternatives = result.get("alternatives", [])
    ranking = result.get("ranking", [])

    # Build criteria name map
    criteria_map = {c["id"]: c["name"] for c in criteria}

    # Build ranking map
    rank_map = {r["id"]: r["rank"] for r in ranking}

    lines = []
    lines.append("# 表4 综合权重排名表")
    lines.append("")
    lines.append("## 4.1 因素综合权重排名")
    lines.append("")

    lines.append(f"| 排名 | 编号 | 因素名称 | 所属准则 | 原始得分 | 综合权重 |")
    lines.append(f"|---|---|---|---|---|---|")

    # Sort alternatives by rank
    sorted_alts = sorted(alternatives, key=lambda x: rank_map.get(x["id"], 999))

    for alt in sorted_alts:
        alt_id = alt.get("id", "?")
        rank = rank_map.get(alt_id, "?")
        name = alt.get("name", "未知")
        crit_id = alt.get("belongs_to_criteria", "?")
        crit_name = criteria_map.get(crit_id, crit_id)
        raw_score = alt.get("raw_score", 0)
        combined_weight = alt.get("combined_weight", 0)

        lines.append(f"| {rank} | {alt_id} | {name} | {crit_name} | {raw_score:.2f} | {combined_weight:.4f} |")

    lines.append("")
    lines.append("## 4.2 准则层权重分布")
    lines.append("")

    lines.append(f"| 编号 | 准则名称 | 准则层权重 |")
    lines.append(f"|---|---|---|")
    for c in criteria:
        lines.append(f"| {c['id']} | {c['name']} | {c['weight']:.4f} |")

    lines.append("")
    lines.append(f"*表4说明： 综合权重 = 准则层权重 × (0.5 + 0.5 × 归一化得分)，反映因素在目标层下的综合重要程度*")

    return "\n".join(lines)


def generate_weight_distribution_chart(run_dir: Path) -> str:
    """Generate ASCII weight distribution chart and summary table."""
    result_path = run_dir / "ahp_results.json"
    if not result_path.exists():
        return ""

    with open(result_path, 'r', encoding='utf-8') as f:
        result = json.load(f)

    alternatives = result.get("alternatives", [])
    ranking = result.get("ranking", [])

    # Build ranking map
    rank_map = {r["id"]: r["rank"] for r in ranking}

    lines = []
    lines.append("# 表5 权重分布图")
    lines.append("")
    lines.append("## 5.1 权重分布条形图")
    lines.append("")

    # Sort by combined weight
    sorted_alts = sorted(alternatives, key=lambda x: x.get("combined_weight", 0), reverse=True)

    if not sorted_alts:
        lines.append("*暂无数据*")
        return "\n".join(lines)

    max_weight = max(alt.get("combined_weight", 0) for alt in sorted_alts)

    lines.append(f"{'排名':<4} {'因素名称':<15} {'权重值':<8} {'分布图':<35}")
    lines.append("|" + "|" .join(["---"] * 4) + "|")

    for alt in sorted_alts:
        alt_id = alt.get("id", "?")
        rank = rank_map.get(alt_id, "?")
        name = alt.get("name", "未知")[:14]
        weight = alt.get("combined_weight", 0)

        # Scale bar to 30 chars max
        bar_len = int(weight / max_weight * 30) if max_weight > 0 else 0
        bar = "█" * bar_len + "░" * (30 - bar_len)

        lines.append(f"| {rank:<4} | {name:<15} | {weight:.4f}  | {bar} |")

    lines.append("")
    lines.append("## 5.2 权重分布统计")
    lines.append("")

    weights = [alt.get("combined_weight", 0) for alt in sorted_alts]
    total = sum(weights)

    lines.append(f"| 统计项 | 数值 |")
    lines.append(f"|---|---|")
    lines.append(f"| 因素总数 | {len(sorted_alts)} |")
    lines.append(f"| 权重总和 | {total:.4f} |")
    lines.append(f"| 最大权重 | {max(weights):.4f} |")
    lines.append(f"| 最小权重 | {min(weights):.4f} |")
    lines.append(f"| 平均权重 | {sum(weights)/len(weights) if weights else 0:.4f} |")

    # Top 3 and Bottom 3
    lines.append("")
    lines.append("## 5.3 关键发现")
    lines.append("")

    top3 = sorted_alts[:3]
    bottom3 = sorted_alts[-3:] if len(sorted_alts) > 3 else []

    lines.append("**权重最高的前3个因素：**")
    for i, alt in enumerate(top3, 1):
        lines.append(f"{i}. {alt.get('name', '未知')} ({alt.get('combined_weight', 0):.2%})")

    if bottom3:
        lines.append("")
        lines.append("**权重最低的后3个因素：**")
        for i, alt in enumerate(bottom3, 1):
            lines.append(f"{i}. {alt.get('name', '未知')} ({alt.get('combined_weight', 0):.2%})")

    lines.append("")
    lines.append(f"*表5说明： 条形图长度反映因素权重相对大小，█ 表示权重比例，░ 表示未填充部分*")

    return "\n".join(lines)


def save_tables(run_dir: Path):
    """Generate and save all 5 tables to markdown file."""
    table1 = generate_criteria_comparison_table(run_dir)
    table2 = generate_criteria_weights_table(run_dir)
    table3 = generate_alternative_scores_table(run_dir)
    table4 = generate_combined_weights_ranking_table(run_dir)
    table5 = generate_weight_distribution_chart(run_dir)

    full_content = f"""# Delphi-AHP 分析结果报告
> 自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{table1}

---

{table2}

---

{table3}

---

{table4}

---

{table5}

---

*本报告由 Delphi-AHP 流程自动生成*
"""

    output_path = run_dir / "analysis_results.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_content)

    print(f"  [已保存] {output_path}")
    return output_path


def display_hierarchical_results(result: dict):
    """Display hierarchical AHP results."""
    print("\n" + "=" * 60)
    print("  AHP 分层权重结果")
    print("=" * 60)

    # Criteria results
    criteria = result.get("criteria", [])
    print(f"\n【准则层权重】")
    print(f"{'ID':<6} {'准则名称':<20} {'权重':<10} {'CR':<8} {'一致性'}")
    print("-" * 60)
    for c in criteria:
        status = "✓" if c.get("consistency_passed") else "✗"
        print(f"{c['id']:<6} {c['name'][:18]:<20} {c['weight']:<10.4f} {c['cr']:<8.4f} {status}")

    # Criteria consistency
    crit_cons = result.get("criteria_consistency", {})
    print(f"\n  准则层一致性检验:")
    print(f"    CR = {crit_cons.get('cr', 0):.4f}", end="")
    if crit_cons.get("passed"):
        print(" ✓ 通过")
    else:
        print(" ✗ 未通过")

    # P4: Show consistency improvement guidance
    guidance = result.get("consistency_guidance")
    if guidance:
        print(f"\n  [警告] {guidance['message']}")
        for suggestion in guidance.get("suggestions", []):
            print(suggestion)

    # Alternative results
    alternatives = result.get("alternatives", [])
    ranking = result.get("ranking", [])

    print(f"\n【方案层权重排名】")
    print(f"{'排名':<6} {'ID':<6} {'方案名称':<20} {'所属准则':<10} {'综合权重':<10}")
    print("-" * 60)

    # Create ranking map
    rank_map = {r["id"]: r["rank"] for r in ranking}

    for alt in sorted(alternatives, key=lambda x: rank_map.get(x["id"], 999)):
        rank = rank_map.get(alt["id"], "?")
        print(f"{rank:<6} {alt['id']:<6} {alt['name'][:18]:<20} {alt['belongs_to_criteria']:<10} {alt['combined_weight']:<10.4f}")

    # Weight distribution
    print("\n【权重分布】")
    max_weight = max(alt["combined_weight"] for alt in alternatives) if alternatives else 1.0
    for alt in alternatives:
        bar_len = int(alt["combined_weight"] / max_weight * 30) if max_weight > 0 else 0
        bar = "█" * bar_len + "░" * (30 - bar_len)
        print(f"  {alt['name'][:15]:<15} {bar} {alt['combined_weight']:.2%}")


def run_step5(state: dict) -> dict:
    """
    Run step 5: Hierarchical AHP & Delphi Round 2.

    支持断点续传：state["resume_part"] 指定从第几个 Part 开始（1-based）。

    Args:
        state: Current state dict
        state["resume_part"]: 从第几个 Part 开始（1=从头）

    Returns:
        Updated state dict
    """
    print_step_header()

    resume_part = state.pop("resume_part", 1)
    resume_part = int(resume_part)

    run_id = state.get("run_id", "unknown")
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / run_id))
    project: dict = state.get("project", {})
    providers = state.get("providers", {})
    experts: List[Expert] = state.get("experts", [])
    rounds: RoundsConfig = state.get("rounds")

    if not project:
        print("  [错误] 找不到项目信息，请先完成步骤 1")
        return state
    if not experts:
        print("  [错误] 尚未配置专家小组，请先完成步骤 3")
        return state
    if rounds is None:
        print("  [错误] 尚未配置轮次，请先完成步骤 4")
        return state

    print(f"Run ID: {run_id}")
    print(f"运行目录: {run_dir}")
    print(f"项目: {project.get('title')}")
    print(f"专家数: {len(experts)}")
    print()

    # Load interview records
    interview_records = load_interview_records(run_dir)
    if not interview_records or not interview_records.get("records"):
        print("  [错误] 未找到步骤4的访谈记录")
        return state

    print(f"  找到 {len(interview_records.get('records', []))} 位专家的访谈记录")

    # ============================================================
    # Part 1: Extract Factors via LLM (each expert uses their own model)
    # ============================================================
    print("\n" + "=" * 60)
    print("  【第一部分】从访谈记录提取因素")
    print("=" * 60)

    # Build expert_id -> Expert config map
    expert_config_map: Dict[str, Expert] = {e.id: e for e in experts}

    print(f"\n  正在从 {len(interview_records.get('records', []))} 位专家的访谈记录中提取因素...")
    print(f"  （每位专家使用自己的 LLM 模型）")

    all_extracted_raw: List[Dict] = []   # [{"name":..., "description":..., "source":...}, ...]
    records = interview_records.get("records", [])

    for rec in records:
        expert_name = rec.get("expert_name", "unknown")
        expert_id = rec.get("expert_id", "E00")

        # 合并该专家所有问答文本
        qa_pairs = rec.get("qa_pairs", [])
        texts = []
        for qa in qa_pairs:
            ans = qa.get("answer", "").strip()
            if ans:
                texts.append(ans)
        combined_text = "\n---\n".join(texts)

        if not combined_text:
            print(f"\n  专家「{expert_name}」无有效访谈文本，跳过")
            continue

        # Use THIS expert's own LLM config
        rec_expert = expert_config_map.get(expert_id)
        if rec_expert is None:
            print(f"\n  专家「{expert_name}」(ID: {expert_id}) 未在专家列表中找到，跳过")
            continue

        exp_base_url, exp_api_key, exp_model = resolve_expert_llm_config(rec_expert, providers)
        if not exp_model or not exp_base_url:
            print(f"\n  专家「{expert_name}」未配置有效 LLM，跳过")
            continue

        print(f"\n  正在提取专家「{expert_name}」的因素（模型: {exp_model}）...")

        # 取该专家的 PRO
        expert_pro = rec_expert.pro if hasattr(rec_expert, 'pro') else ""

        try:
            prompt = build_factor_extraction_prompt(
                expert_name=expert_name,
                expert_pro=expert_pro,
                interview_text=combined_text[:3000],  # limit text length
                research_topic=project.get("title", ""),
                delphi_lang=project.get("delphi_lang", "zh"),
            )

            response = call_llm(
                base_url=exp_base_url,
                api_key=exp_api_key,
                model=exp_model,
                prompt=prompt,
            )

            raw_factors, err = parse_factor_extraction_response(response)

            if err or not raw_factors:
                print(f"  [警告] 专家「{expert_name}」因素提取失败：{err}，跳过该专家")
                continue

            for f in raw_factors:
                all_extracted_raw.append({
                    "name": f["name"],
                    "description": f.get("description", ""),
                    "source": f"来自专家「{expert_name}」(ID: {expert_id})"
                })
            names = [f["name"] for f in raw_factors]
            print(f"  提取到 {len(raw_factors)} 个因素：{', '.join(names)}")

        except LLMError as e:
            print(f"  [错误] 专家「{expert_name}」LLM调用失败：{str(e)}，跳过该专家")
            continue

    if not all_extracted_raw:
        print("\n  [错误] 所有专家的访谈记录均未能提取到有效因素")
        return state

    # 去重（按因素名称精确去重）
    seen = set()
    unique_factors_raw = []
    for f in all_extracted_raw:
        if f["name"] not in seen:
            seen.add(f["name"])
            unique_factors_raw.append(f)

    print(f"\n  合计提取到 {len(unique_factors_raw)} 个不重复因素")

    # 转换为 Factor 对象
    all_factors: List[Factor] = []
    for i, f_dict in enumerate(unique_factors_raw[:20], 1):  # 最多20个
        factor = Factor(
            id=f"F{i:02d}",
            name=f_dict["name"],
            description=f_dict.get("description", ""),
            source=f_dict.get("source", ""),
        )
        all_factors.append(factor)

    print("\n  因素列表：")
    for i, f in enumerate(all_factors, 1):
        print(f"    {i}. {f.name}")

    state["factors"] = all_factors

    # Save factor coding
    used_models = [
        {"expert_id": e.id, "expert_name": e.name, "model": e.model}
        for e in experts if e.id in expert_config_map
    ]
    factor_coding = {
        "run_id": run_id,
        "factors": [f.__dict__ for f in all_factors],
        "factor_count": len(all_factors),
        "raw_extracted": unique_factors_raw,
        "extraction_models": used_models,
        "timestamp": datetime.now().isoformat(),
    }
    save_json(run_dir / "factor_coding.json", factor_coding)

    # ── Part 1 完成 ── 跳过到对应 Part
    # resume_part > 3: 全部跳过，直接到 Part 4 增量
    criteria_comparisons = None  # 初始化，skip block 会设置
    expert_comparisons = None
    alt_scores_data = None
    if resume_part > 3:
        # 加载全部已有数据
        hierarchy_path = run_dir / "ahp_hierarchy.json"
        if hierarchy_path.exists():
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                hierarchy = json.load(f)
            criteria = hierarchy.get("criteria_layer", [])
            alternatives = hierarchy.get("alternative_layer", [])
        comp_path = run_dir / "criteria_comparisons.json"
        if comp_path.exists():
            with open(comp_path, 'r', encoding='utf-8') as f:
                criteria_comparison_data = json.load(f)
                criteria_comparisons = criteria_comparison_data.get("comparisons", {})
        alt_path = run_dir / "alternative_scores.json"
        alt_scores_data = None
        if alt_path.exists():
            with open(alt_path, 'r', encoding='utf-8') as f:
                alt_scores_data = json.load(f)
        ahp_path = run_dir / "ahp_results.json"
        if ahp_path.exists():
            with open(ahp_path, 'r', encoding='utf-8') as f:
                ahp_result = json.load(f)
            print("[跳过] 步骤5全部完成（从断点恢复）")
            state["ahp_result"] = ahp_result
            return state
        # ahp_results 不存在，但数据都在，进入 Part 4 增量
        print("[提示] 从断点恢复，进入 Part 4 增量重跑...")
        state["factors"] = all_factors
        state["ahp_hierarchy"] = hierarchy
        state["criteria_comparisons"] = criteria_comparisons
        state["alt_scores_data"] = alt_scores_data
        # 继续到 Part 4 增量重跑（不重新构建 criteria）
    elif resume_part > 2:
        # resume_part == 3: 跳过 Part 1-2，加载数据，进入 Part 3
        hierarchy_path = run_dir / "ahp_hierarchy.json"
        if hierarchy_path.exists():
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                hierarchy = json.load(f)
            criteria = hierarchy.get("criteria_layer", [])
            alternatives = hierarchy.get("alternative_layer", [])
        comp_path = run_dir / "criteria_comparisons.json"
        if comp_path.exists():
            with open(comp_path, 'r', encoding='utf-8') as f:
                criteria_comparison_data = json.load(f)
                criteria_comparisons = criteria_comparison_data.get("comparisons", {})
        alt_path = run_dir / "alternative_scores.json"
        alt_scores_data = None
        if alt_path.exists():
            with open(alt_path, 'r', encoding='utf-8') as f:
                alt_scores_data = json.load(f)
        print("[跳过] Part 1-2 已完成，直接进入 Part 3")
        # 继续到 Part 3
    elif resume_part > 1:
        # resume_part == 2: 跳过 Part 1，数据存在则加载，进入 Part 2 生成层次结构
        hierarchy_path = run_dir / "ahp_hierarchy.json"
        if hierarchy_path.exists():
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                hierarchy = json.load(f)
            criteria = hierarchy.get("criteria_layer", [])
            alternatives = hierarchy.get("alternative_layer", [])
            print("[跳过] 因素提取已完成，直接使用已有因素列表")
        # 如果 hierarchy 不存在，hierarchy 变量保持 None，正常进入 Part 2 让 LLM 生成

    # ============================================================
    # Part 2: AHP Hierarchy
    # ============================================================
    print("\n" + "=" * 60)
    print("  【第二部分】AHP 层次结构")
    print("=" * 60)

    # Only load if coming from fresh start (resume_part == 1)
    # When resume_part > 1, hierarchy is already loaded in skip block above
    if resume_part == 1:
        hierarchy = load_ahp_hierarchy(run_dir)

    if not hierarchy:
        # Build hierarchy via LLM (criteria extraction from factors)
        print("\n  正在生成 AHP 层次结构...")

        # Build factor_id_map keyed by factor ID (not name) for parse_criteria_extraction_response
        factor_id_map = {f.id: f for f in all_factors}

        # Use the first expert's LLM config for criteria extraction
        first_expert = experts[0] if experts else None
        if not first_expert:
            print("  [错误] 未配置专家，无法提取准则层")
            return state

        criteria_base_url, criteria_api_key, criteria_model = resolve_expert_llm_config(first_expert, providers)
        print(f"  使用模型: {criteria_model}")

        # Call LLM to extract criteria from factors
        criteria_prompt = build_criteria_extraction_prompt(
            factors=all_factors,
            research_topic=project.get("title", ""),
            framework=project.get("framework", ""),
            delphi_lang=project.get("delphi_lang", "zh"),
        )

        # Outer try/except wraps the entire retry loop + criteria assignment
        criteria = None
        alternatives = None
        try:
            for attempt in range(2):
                try:
                    llm_response = call_llm(
                        base_url=criteria_base_url,
                        api_key=criteria_api_key,
                        model=criteria_model,
                        prompt=criteria_prompt,
                    )

                    raw_criteria, raw_alternatives, err = parse_criteria_extraction_response(
                        llm_response, factor_id_map
                    )

                    if err:
                        if attempt == 0:
                            print(f"  [警告] 准则提取失败：{err}，重试...")
                            continue
                        print(f"  [错误] 重试后仍失败：{err}")
                        print(f"  [提示] 请手动编辑 ahp_hierarchy.json 后重新运行步骤 5")
                        return state

                    print(f"  提取到 {len(raw_criteria)} 个准则")

                    # Assign proper IDs to criteria
                    criteria = []
                    for i, c in enumerate(raw_criteria, 1):
                        criteria.append({
                            "id": f"C{i:02d}",
                            "name": c["name"],
                            "description": c["description"],
                        })

                    # Update raw_alternatives with correct criteria IDs
                    alternatives = []
                    for alt in raw_alternatives:
                        criteria_idx = -1
                        for qi, c in enumerate(raw_criteria):
                            if alt["id"] in c.get("factor_ids", []):
                                criteria_idx = qi
                                break
                        criteria_id = f"C{criteria_idx + 1:02d}" if criteria_idx >= 0 else "C1"
                        alternatives.append({
                            "id": alt["id"],
                            "name": alt["name"],
                            "description": alt.get("description", ""),
                            "belongs_to_criteria": criteria_id,
                        })

                    print(f"\n  [成功] LLM 提取到 {len(criteria)} 个准则层维度")
                    for i, c in enumerate(criteria, 1):
                        assigned = sum(1 for alt in alternatives if alt.get("belongs_to_criteria") == c["id"])
                        print(f"    [{c['id']}] {c['name']}（含 {assigned} 个因素）")
                    break  # success, exit retry loop

                except LLMError as e:
                    if attempt == 0:
                        print(f"  [错误] {str(e)}，重试...")
                        continue
                    print(f"  [错误] 重试后仍失败：{str(e)}")
                    return state

        except Exception as e:
            print(f"\n  [错误] 准则层提取异常：{str(e)}")
            print(f"  [提示] 请检查网络连接和 API 配置，然后重新运行步骤 5")
            return state

        hierarchy = {
            "goal_layer": {
                "name": project.get("title"),
                "description": f"基于{project.get('framework')}框架的{project.get('title')}研究"
            },
            "criteria_layer": criteria,
            "alternative_layer": alternatives,
        }

        save_json(run_dir / "ahp_hierarchy.json", hierarchy)

    # 构建确认内容
    content_lines = []
    content_lines.append(f"{Colors.CYAN}AHP 层次结构：{Colors.RESET}")
    content_lines.append(f"{Colors.WHITE}目标层: {hierarchy.get('goal_layer', {}).get('name', '未定义')}{Colors.RESET}")

    criteria = hierarchy.get("criteria_layer", [])
    content_lines.append(f"{Colors.WHITE}准则层 ({len(criteria)} 个)：{Colors.RESET}")
    for c in criteria:
        content_lines.append(f"  [{c['id']}] {c['name']}")

    alternatives = hierarchy.get("alternative_layer", [])
    content_lines.append(f"{Colors.WHITE}方案层 ({len(alternatives)} 个因素)：{Colors.RESET}")
    for a in alternatives[:5]:
        content_lines.append(f"  [{a['id']}] {a['name']} -> {a.get('belongs_to_criteria', '?')}")
    if len(alternatives) > 5:
        content_lines.append(f"  ... 还有 {len(alternatives) - 5} 个")

    # 打印黄色方框
    box_width = 70
    print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}     确认 AHP 层次结构     {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")

    for line in content_lines:
        padding = box_width - len(line) - 4
        if padding < 0:
            padding = 0
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")

    print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}确认使用此层次结构{Colors.RESET}{' ' * (box_width - 36)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.CYAN}  2{Colors.RESET} - {Colors.CYAN}编辑准则层{Colors.RESET}{' ' * (box_width - 28)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")

    choice = questionary.select(
        "选择操作",
        choices=["确认使用此层次结构", "编辑准则层"],
    ).ask()

    if choice == "编辑准则层" or choice is None:
        print("\n  --- 准则层编辑模式 ---")

        current_criteria = hierarchy.get("criteria_layer", [])
        # 去掉用户已输入的默认项，建立新的列表
        criteria_list: List[dict] = [dict(c) for c in current_criteria]

        while True:
            # 显示当前准则列表
            print("\n  当前准则层：")
            if not criteria_list:
                print("    （空）")
            for i, c in enumerate(criteria_list, 1):
                print(f"    [{i}] {c['name']} — {c.get('description', '')}")

            edit_choice = questionary.select(
                "操作",
                choices=["添加新准则", "编辑已有准则", "删除准则", "完成编辑"],
            ).ask()

            if edit_choice == "添加新准则":
                name = ask("  准则名称")
                if not name:
                    print("  [提示] 名称不能为空")
                    continue
                desc = ask(f"  {name} 的描述（可选）")
                new_id = f"C{len(criteria_list) + 1:02d}"
                criteria_list.append({"id": new_id, "name": name, "description": desc or f"{name}相关的评价维度"})
                print(f"  [已添加] {name} (ID: {new_id})")

            elif edit_choice == "编辑已有准则":
                if not criteria_list:
                    print("  [提示] 当前没有准则，请先添加")
                    continue
                names = [c["name"] for c in criteria_list]
                sel = questionary.select("选择要编辑的准则", choices=names).ask()
                if sel is None:
                    continue
                idx = names.index(sel)
                new_name = ask(f"  新名称", criteria_list[idx]["name"])
                new_desc = ask(f"  新描述", criteria_list[idx].get("description", ""))
                criteria_list[idx]["name"] = new_name or criteria_list[idx]["name"]
                criteria_list[idx]["description"] = new_desc
                print(f"  [已更新] {criteria_list[idx]['name']}")

            elif edit_choice == "删除准则":
                if not criteria_list:
                    print("  [提示] 当前没有准则")
                    continue
                names = [c["name"] for c in criteria_list]
                sel = questionary.select("选择要删除的准则", choices=names).ask()
                if sel is None:
                    continue
                idx = names.index(sel)
                removed = criteria_list.pop(idx)
                # 重新编号
                for i, c in enumerate(criteria_list):
                    c["id"] = f"C{i + 1:02d}"
                print(f"  [已删除] {removed['name']}")

            elif edit_choice == "完成编辑":
                if len(criteria_list) < 2:
                    print("  [错误] 准则层至少需要 2 个准则")
                    continue
                break

        # 重新构建 alternatives，保持因素与新准则层的对应关系
        # 如果准则数量变化，重新分配 belongs_to_criteria（循环分配）
        new_alternatives = [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description or "",
                "belongs_to_criteria": criteria_list[i % len(criteria_list)]["id"]
                if criteria_list else "C1"
            }
            for i, f in enumerate(all_factors)
        ]

        hierarchy = {
            "goal_layer": hierarchy.get("goal_layer", {}),
            "criteria_layer": criteria_list,
            "alternative_layer": new_alternatives,
        }

        # 保存更新后的层次结构
        save_json(run_dir / "ahp_hierarchy.json", hierarchy)

        # 重新构建确认内容并展示（递归调用自身确认流程）
        content_lines = []
        content_lines.append(f"{Colors.CYAN}AHP 层次结构（已更新）：{Colors.RESET}")
        content_lines.append(f"{Colors.WHITE}目标层: {hierarchy.get('goal_layer', {}).get('name', '未定义')}{Colors.RESET}")
        criteria = hierarchy.get("criteria_layer", [])
        content_lines.append(f"{Colors.WHITE}准则层 ({len(criteria)} 个)：{Colors.RESET}")
        for c in criteria:
            content_lines.append(f"  [{c['id']}] {c['name']}")
        alternatives = hierarchy.get("alternative_layer", [])
        content_lines.append(f"{Colors.WHITE}方案层 ({len(alternatives)} 个因素)：{Colors.RESET}")
        for a in alternatives[:5]:
            content_lines.append(f"  [{a['id']}] {a['name']} -> {a.get('belongs_to_criteria', '?')}")
        if len(alternatives) > 5:
            content_lines.append(f"  ... 还有 {len(alternatives) - 5} 个")

        print(f"\n{Colors.BRIGHT_YELLOW}╔{'═' * (box_width - 2)}╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.BOLD}{Colors.YELLOW}     确认 AHP 层次结构     {Colors.RESET}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        for line in content_lines:
            padding = box_width - len(line) - 4
            if padding < 0:
                padding = 0
            print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET} {line}{' ' * padding} {Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╠{'═' * (box_width - 2)}╣{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.GREEN}  1{Colors.RESET} - {Colors.GREEN}确认使用此层次结构{Colors.RESET}{' ' * (box_width - 36)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}║{Colors.RESET}{Colors.CYAN}  2{Colors.RESET} - {Colors.CYAN}编辑准则层{Colors.RESET}{' ' * (box_width - 28)}{Colors.BRIGHT_YELLOW}║{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}╚{'═' * (box_width - 2)}╝{Colors.RESET}")

        confirm = questionary.select(
            "选择操作",
            choices=["确认使用此层次结构", "编辑准则层"],
        ).ask()
        if confirm != "确认使用此层次结构":
            print("\n  [提示] 请重新运行步骤 5 以继续")
            return state

    state["ahp_hierarchy"] = hierarchy

    # Extract scoring dimensions from interview_framework dimensions (Part 2 generates them)
    # scoring_dimensions come from interview_framework's dimensions, not from rounds.json
    interview_framework = state.get("interview_framework")
    if not interview_framework:
        fw_path = run_dir / "interview_framework.json"
        if fw_path.exists():
            with open(fw_path, 'r', encoding='utf-8') as f:
                interview_framework = json.load(f)
    fw_dimensions = interview_framework.get("dimensions", []) if interview_framework else []
    # Convert framework dimensions to ScoringDimension list (equal weight = 1.0 for each)
    scoring_dimensions = [ScoringDimension(name=d.get("name", f"维度{i+1}"), weight=1.0) for i, d in enumerate(fw_dimensions)]
    if not scoring_dimensions:
        # Fallback if no dimensions in framework
        scoring_dimensions = [ScoringDimension(name="综合性", weight=1.0)]
    # Patch into state["rounds"] so Part 4 can read it
    state["rounds"].round_2_dimensions = scoring_dimensions

    # ============================================================
    # Part 3: Delphi Round 2 - Criteria Pairwise Comparisons
    # ============================================================
    if criteria_comparisons is None:
        # 需要执行 Part 3（resume_part <= 3）
        print("\n" + "=" * 60)
        print("  【第三部分】准则层两两比较")
        print("=" * 60)
        print(f"""
  准则层包含 {len(criteria)} 个准则，需要进行两两比较判断。
  判断采用 Saaty 1-9 标度：
    1 = 同等重要
    3 = 略微重要
    5 = 明显重要
    7 = 强烈重要
    9 = 极端重要
    (2,4,6,8 为中间值)
""")

        # Build project context
        project_context = f"""
## 研究项目信息
【研究主题】{project.get('title')}
【分析框架】{project.get('framework')}
【研究目的】{project.get('purpose')}
"""

        # Generate pairwise comparisons
        scoring_base_url, scoring_api_key, scoring_model = select_scoring_model(providers)
        criteria_comparisons, expert_comparisons = generate_pairwise_comparisons(
            experts, criteria, project_context, scoring_base_url, scoring_api_key, scoring_model
        )

        print(f"\n  [完成] 准则层两两比较完成")

        # Save criteria comparisons
        criteria_comparison_data = {
            "criteria": criteria,
            "comparisons": criteria_comparisons,
            "expert_comparisons": expert_comparisons,
            "timestamp": datetime.now().isoformat(),
        }
        save_json(run_dir / "criteria_comparisons.json", criteria_comparison_data)
    else:
        # 跳过 Part 3，直接使用已加载的 criteria_comparisons
        print("[跳过] 准则层两两比较已完成（从断点恢复）")

    # ============================================================
    # Part 4: Delphi Round 2 - Alternative Pairwise Comparisons (P1: true AHP)
    # ============================================================
    print("\n" + "=" * 60)
    print("  【第四部分】方案层成对比较")
    print("=" * 60)

    # Build alternatives_by_criteria for the new function
    criteria_ids_for_alt = [c["id"] for c in criteria]
    alternatives_by_criteria: Dict[str, List[dict]] = {}
    for alt in alternatives:
        crit_id = alt.get("belongs_to_criteria", criteria_ids_for_alt[0] if criteria_ids_for_alt else "C1")
        if crit_id not in alternatives_by_criteria:
            alternatives_by_criteria[crit_id] = []
        alternatives_by_criteria[crit_id].append(alt)

    # Total comparison count for display
    total_pairs = 0
    for crit_id, alts in alternatives_by_criteria.items():
        n = len(alts)
        total_pairs += n * (n - 1) // 2

    print(f"""
  方案层包含 {len(alternatives)} 个因素，分布在 {len(alternatives_by_criteria)} 个准则下。
  在每个准则下，各方案进行两两比较（Saaty 1-9 标度）。
  比较总数：{total_pairs} 对/专家
""")

    # Build project context (same as criteria comparisons)
    project_context = f"""
## 研究项目信息
【研究主题】{project.get('title')}
【分析框架】{project.get('framework')}
【研究目的】{project.get('purpose')}
"""

    scoring_base_url, scoring_api_key, scoring_model = select_scoring_model(providers)

    # P1: 使用成对比较而非直接评分
    local_weights, expert_alt_details = generate_alternative_pairwise_comparisons(
        experts=experts,
        criteria=criteria,
        alternatives=alternatives,
        project_context=project_context,
        scoring_base_url=scoring_base_url,
        scoring_api_key=scoring_api_key,
        scoring_model=scoring_model,
    )

    print(f"\n  [完成] 方案层成对比较完成")

    # Save alternative scores in new format
    alternative_score_data = {
        "format": "pairwise_comparisons",
        "criteria_ids": criteria_ids_for_alt,
        "alternatives_by_criteria": alternatives_by_criteria,
        "local_weights": local_weights,
        "expert_details": expert_alt_details,
        "timestamp": datetime.now().isoformat(),
    }
    save_json(run_dir / "alternative_scores.json", alternative_score_data)

    # ============================================================
    # Part 5: Hierarchical AHP Calculation
    # ============================================================
    print("\n" + "=" * 60)
    print("  【第五部分】分层 AHP 计算")
    print("=" * 60)

    # P1 new format: run_hierarchical_ahp receives per-criterion local weights
    ahp_result = run_hierarchical_ahp(
        criteria=criteria,
        alternatives=alternatives,
        criteria_comparisons=criteria_comparisons,
        alternative_scores=local_weights,
    )

    # Save results
    save_json(run_dir / "ahp_results.json", ahp_result)

    print(f"\n  [完成] AHP 计算完成")

    # Display results
    display_hierarchical_results(ahp_result)

    # Generate and save analysis tables
    print("\n  正在生成分析表格...")
    output_file = save_tables(run_dir)

    # Final summary
    state["run_status"] = "completed"
    state["run_dir"] = str(run_dir)
    state["ahp_result"] = ahp_result

    # Save summary
    summary = {
        "run_id": run_id,
        "title": project.get("title"),
        "status": "completed",
        "created_at": datetime.now().isoformat(),
        "artifacts": [
            "project.json",
            "interview_records.json",
            "factor_coding.json",
            "ahp_hierarchy.json",
            "criteria_comparisons.json",
            "alternative_scores.json",
            "ahp_results.json",
            "analysis_results.md",
        ]
    }
    save_json(run_dir / "summary.json", summary)

    print("\n" + "=" * 60)
    print("  步骤 5 完成！")
    print("=" * 60)
    print(f"\n  已生成文件：")
    print(f"    - factor_coding.json (因素列表)")
    print(f"    - ahp_hierarchy.json (AHP层次结构)")
    print(f"    - criteria_comparisons.json (准则层比较)")
    print(f"    - alternative_scores.json (方案层评分)")
    print(f"    - ahp_results.json (最终权重结果)")
    print(f"    - analysis_results.md (5张分析表格)")

    return state
