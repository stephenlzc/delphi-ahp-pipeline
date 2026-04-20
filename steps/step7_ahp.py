"""
Step 7: Sensitivity Analysis
"""
from __future__ import annotations

import json
import copy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)


def print_step_header():
    """Print step 7 header."""
    print()
    print("-" * 60)
    print("  Step 7/8: Sensitivity Analysis")
    print("-" * 60)
    print()


def load_json(filepath: Path) -> dict:
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath: Path, data: dict):
    """Save JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [Saved] {filepath}")


def normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
    """Normalize scores to 0-1 range."""
    if not scores:
        return {}

    values = list(scores.values())
    max_score = max(values)
    min_score = min(values)
    score_range = max_score - min_score if max_score > min_score else 1.0

    normalized = {}
    for alt_id, score in scores.items():
        normalized[alt_id] = (score - min_score) / score_range

    return normalized


def recalculate_combined_weights(
    criteria_weights: List[float],
    criteria_ids: List[str],
    alternatives: List[dict],
    normalized_scores: Dict[str, float]
) -> Dict[str, float]:
    """Recalculate combined weights with modified criteria weights or scores."""
    combined = {}
    n_criteria = len(criteria_weights)

    for alt in alternatives:
        alt_id = alt["id"]
        crit_id = alt.get("belongs_to_criteria", criteria_ids[0] if criteria_ids else "C1")

        crit_idx = criteria_ids.index(crit_id) if crit_id in criteria_ids else 0
        crit_weight = criteria_weights[crit_idx] if crit_idx < len(criteria_weights) else 1.0 / n_criteria

        alt_score = normalized_scores.get(alt_id, 0.5)
        combined[alt_id] = round(crit_weight * (0.5 + 0.5 * alt_score), 4)

    return combined


def rank_alternatives(combined_weights: Dict[str, float]) -> List[Tuple[str, float, int]]:
    """Rank alternatives by combined weight. Returns list of (id, weight, rank)."""
    sorted_items = sorted(combined_weights.items(), key=lambda x: x[1], reverse=True)
    return [(alt_id, weight, rank + 1) for rank, (alt_id, weight) in enumerate(sorted_items)]


def compare_rankings(
    original_ranking: List[Tuple[str, float, int]],
    new_ranking: List[Tuple[str, float, int]]
) -> Dict[str, Dict]:
    """Compare two rankings and return changes."""
    # Build maps
    orig_rank_map = {item[0]: item[2] for item in original_ranking}
    new_rank_map = {item[0]: item[2] for item in new_ranking}

    changes = {}
    for alt_id in orig_rank_map:
        orig_rank = orig_rank_map.get(alt_id, 999)
        new_rank = new_rank_map.get(alt_id, 999)
        rank_change = orig_rank - new_rank  # Positive = improved, Negative = worsened

        changes[alt_id] = {
            "original_rank": orig_rank,
            "new_rank": new_rank,
            "rank_change": rank_change,
            "stable": orig_rank == new_rank,
        }

    return changes


def run_criteria_sensitivity(
    criteria: List[dict],
    alternatives: List[dict],
    criteria_comparisons: Dict[str, float],
    alternative_scores: Dict[str, float],
    variation: float = 0.1
) -> Dict:
    """
    Run sensitivity analysis on criteria weights.

    Args:
        criteria: List of criteria dicts
        alternatives: List of alternative dicts
        criteria_comparisons: Original comparison values
        alternative_scores: Original alternative scores
        variation: Percentage variation (default 10%)

    Returns:
        Sensitivity analysis results
    """
    from ahp import calculate_weights, calculate_consistency

    n = len(criteria)
    criteria_ids = [c["id"] for c in criteria]

    # Build original criteria matrix
    criteria_matrix = [[1.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            key = f"{i},{j}"
            val = criteria_comparisons.get(key, 1.0)
            criteria_matrix[i][j] = val
            criteria_matrix[j][i] = 1.0 / val if val > 0 else 1.0

    # Original weights
    orig_weights = calculate_weights(criteria_matrix)

    # Normalized scores
    normalized_scores = normalize_scores(alternative_scores)

    # Original combined weights and ranking
    orig_combined = recalculate_combined_weights(orig_weights, criteria_ids, alternatives, normalized_scores)
    orig_ranking = rank_alternatives(orig_combined)

    results = {
        "original_weights": {criteria_ids[i]: round(orig_weights[i], 4) for i in range(n)},
        "original_ranking": [{"id": r[0], "weight": r[1], "rank": r[2]} for r in orig_ranking],
        "variation_percent": variation * 100,
        "scenarios": [],
    }

    # Test each criteria with ±variation
    for idx, criterion in enumerate(criteria):
        crit_id = criterion["id"]

        # Scenario 1: Increase by variation
        modified_weights_up = orig_weights.copy()
        modified_weights_up[idx] *= (1 + variation)
        # Renormalize
        total_up = sum(modified_weights_up)
        modified_weights_up = [w / total_up for w in modified_weights_up]

        combined_up = recalculate_combined_weights(modified_weights_up, criteria_ids, alternatives, normalized_scores)
        ranking_up = rank_alternatives(combined_up)
        changes_up = compare_rankings(orig_ranking, ranking_up)

        # Scenario 2: Decrease by variation
        modified_weights_down = orig_weights.copy()
        modified_weights_down[idx] *= (1 - variation)
        # Renormalize
        total_down = sum(modified_weights_down)
        modified_weights_down = [w / total_down for w in modified_weights_down]

        combined_down = recalculate_combined_weights(modified_weights_down, criteria_ids, alternatives, normalized_scores)
        ranking_down = rank_alternatives(combined_down)
        changes_down = compare_rankings(orig_ranking, ranking_down)

        results["scenarios"].append({
            "criteria_id": crit_id,
            "criteria_name": criterion["name"],
            "original_weight": round(orig_weights[idx], 4),
            "increase_scenario": {
                "new_weight": round(modified_weights_up[idx], 4),
                "weight_change_pct": round((modified_weights_up[idx] - orig_weights[idx]) / orig_weights[idx] * 100, 2) if orig_weights[idx] != 0 else 0,
                "ranking_changes": changes_up,
                "top3": [{"id": r[0], "rank": r[2]} for r in ranking_up[:3]],
            },
            "decrease_scenario": {
                "new_weight": round(modified_weights_down[idx], 4),
                "weight_change_pct": round((modified_weights_down[idx] - orig_weights[idx]) / orig_weights[idx] * 100, 2) if orig_weights[idx] != 0 else 0,
                "ranking_changes": changes_down,
                "top3": [{"id": r[0], "rank": r[2]} for r in ranking_down[:3]],
            },
        })

    return results


def normalize_criteria_sensitivity(result: Dict) -> Dict:
    """
    Normalize criteria sensitivity payload to flat shape with top-level `scenarios`.

    Supports both:
    - New shape: {"scenarios": [...]}
    - Legacy nested shape: {"criteria_sensitivity": {"scenarios": [...]}}
    """
    if not isinstance(result, dict):
        return {"original_weights": {}, "original_ranking": [], "variation_percent": 0, "scenarios": []}

    if "scenarios" in result and isinstance(result.get("scenarios"), list):
        return result

    nested = result.get("criteria_sensitivity")
    if isinstance(nested, dict) and isinstance(nested.get("scenarios"), list):
        return nested

    return {"original_weights": {}, "original_ranking": [], "variation_percent": 0, "scenarios": []}


def normalize_score_sensitivity(result: Dict) -> Dict:
    """
    Normalize score sensitivity payload to flat shape with top-level `scenarios`.
    """
    if not isinstance(result, dict):
        return {"original_scores": {}, "original_ranking": [], "variation_percent": 0, "scenarios": []}
    if "scenarios" in result and isinstance(result.get("scenarios"), list):
        return result

    nested = result.get("score_sensitivity")
    if isinstance(nested, dict) and isinstance(nested.get("scenarios"), list):
        return nested

    return {"original_scores": {}, "original_ranking": [], "variation_percent": 0, "scenarios": []}


def run_score_sensitivity(
    alternatives: List[dict],
    criteria_weights: Dict[str, float],
    alternative_scores: Dict[str, float],
    variation: float = 0.1
) -> Dict:
    """
    Run sensitivity analysis on alternative scores.

    Args:
        alternatives: List of alternative dicts
        criteria_weights: Criteria weights dict
        alternative_scores: Original alternative scores
        variation: Percentage variation (default 10%)

    Returns:
        Score sensitivity results
    """
    # Normalize original scores
    normalized_scores = normalize_scores(alternative_scores)

    # Original combined weights
    combined_weights = {}
    for alt in alternatives:
        alt_id = alt["id"]
        crit_id = alt.get("belongs_to_criteria", "C1")
        crit_weight = criteria_weights.get(crit_id, 0.25)
        alt_score = normalized_scores.get(alt_id, 0.5)
        combined_weights[alt_id] = round(crit_weight * (0.5 + 0.5 * alt_score), 4)

    orig_ranking = rank_alternatives(combined_weights)

    results = {
        "original_scores": alternative_scores,
        "original_ranking": [{"id": r[0], "weight": r[1], "rank": r[2]} for r in orig_ranking],
        "variation_percent": variation * 100,
        "scenarios": [],
    }

    # Test each alternative with ±variation
    for alt in alternatives:
        alt_id = alt["id"]
        orig_score = alternative_scores.get(alt_id, 7.0)

        # Scenario 1: Increase score by variation
        new_score_up = orig_score * (1 + variation)
        test_scores_up = alternative_scores.copy()
        test_scores_up[alt_id] = new_score_up
        norm_up = normalize_scores(test_scores_up)

        combined_up = {}
        for a in alternatives:
            a_id = a["id"]
            crit_id = a.get("belongs_to_criteria", "C1")
            crit_weight = criteria_weights.get(crit_id, 0.25)
            alt_score = norm_up.get(a_id, 0.5)
            combined_up[a_id] = round(crit_weight * (0.5 + 0.5 * alt_score), 4)

        ranking_up = rank_alternatives(combined_up)
        changes_up = compare_rankings(orig_ranking, ranking_up)

        # Scenario 2: Decrease score by variation
        new_score_down = orig_score * (1 - variation)
        test_scores_down = alternative_scores.copy()
        test_scores_down[alt_id] = new_score_down
        norm_down = normalize_scores(test_scores_down)

        combined_down = {}
        for a in alternatives:
            a_id = a["id"]
            crit_id = a.get("belongs_to_criteria", "C1")
            crit_weight = criteria_weights.get(crit_id, 0.25)
            alt_score = norm_down.get(a_id, 0.5)
            combined_down[a_id] = round(crit_weight * (0.5 + 0.5 * alt_score), 4)

        ranking_down = rank_alternatives(combined_down)
        changes_down = compare_rankings(orig_ranking, ranking_down)

        results["scenarios"].append({
            "alternative_id": alt_id,
            "alternative_name": alt.get("name", "未知"),
            "original_score": orig_score,
            "increase_scenario": {
                "new_score": round(new_score_up, 2),
                "ranking_changes": changes_up,
                "top3": [{"id": r[0], "rank": r[2]} for r in ranking_up[:3]],
            },
            "decrease_scenario": {
                "new_score": round(new_score_down, 2),
                "ranking_changes": changes_down,
                "top3": [{"id": r[0], "rank": r[2]} for r in ranking_down[:3]],
            },
        })

    return results


def generate_sensitivity_summary(sensitivity_results: Dict) -> str:
    """Generate sensitivity analysis summary markdown."""
    lines = []
    lines.append("# 敏感性分析汇总")
    lines.append("")
    lines.append(f"**分析变幅**: ±{sensitivity_results.get('variation_percent', 10)}%")
    lines.append("")

    # Criteria sensitivity summary
    lines.append("## 准则权重敏感性")
    lines.append("")

    stable_count = 0
    total_scenarios = 0

    for scenario in sensitivity_results.get("criteria_sensitivity", {}).get("scenarios", []):
        crit_name = scenario.get("criteria_name", "?")
        orig_weight = scenario.get("original_weight", 0)

        changes_up = scenario.get("increase_scenario", {}).get("ranking_changes", {})
        changes_down = scenario.get("decrease_scenario", {}).get("ranking_changes", {})

        unstable_up = sum(1 for c in changes_up.values() if not c.get("stable", True))
        unstable_down = sum(1 for c in changes_down.values() if not c.get("stable", True))

        total_scenarios += 1
        if unstable_up == 0:
            stable_count += 1
        total_scenarios += 1
        if unstable_down == 0:
            stable_count += 1

        if unstable_up == 0 and unstable_down == 0:
            status = "✓ 稳定"
        else:
            status = f"⚠ 变化(↑{unstable_up}, ↓{unstable_down})"

        lines.append(f"- **{crit_name}** (权重:{orig_weight:.4f}) {status}")

    # Alternative score sensitivity summary
    lines.append("")
    lines.append("## 方案得分敏感性")
    lines.append("")

    for scenario in sensitivity_results.get("score_sensitivity", {}).get("scenarios", []):
        alt_name = scenario.get("alternative_name", "?")
        orig_score = scenario.get("original_score", 0)

        changes_up = scenario.get("increase_scenario", {}).get("ranking_changes", {})
        changes_down = scenario.get("decrease_scenario", {}).get("ranking_changes", {})

        unstable_up = sum(1 for c in changes_up.values() if not c.get("stable", True))
        unstable_down = sum(1 for c in changes_down.values() if not c.get("stable", True))

        total_scenarios += 1
        if unstable_up == 0:
            stable_count += 1
        total_scenarios += 1
        if unstable_down == 0:
            stable_count += 1

        if unstable_up == 0 and unstable_down == 0:
            status = "✓ 稳定"
        else:
            status = f"⚠ 变化(↑{unstable_up}, ↓{unstable_down})"

        lines.append(f"- **{alt_name}** (得分:{orig_score:.2f}) {status}")

    # Overall assessment
    lines.append("")
    lines.append("## 总体评估")

    stable_pct = stable_count / total_scenarios * 100 if total_scenarios > 0 else 0
    if stable_pct >= 80:
        assessment = "**结果稳健性：高** - AHP分析结果具有较好的稳定性"
    elif stable_pct >= 50:
        assessment = "**结果稳健性：中** - 部分因素权重变化会影响排名"
    else:
        assessment = "**结果稳健性：低** - 建议重新审视判断矩阵"

    lines.append(assessment)

    return "\n".join(lines)


def run_step7(state: dict) -> dict:
    """
    Run step 7: Sensitivity analysis on AHP results.

    This step automatically:
    1. Loads AHP hierarchy and results from step 5
    2. Runs criteria weight sensitivity (±10% variation)
    3. Runs alternative score sensitivity (±10% variation)
    4. Generates sensitivity analysis report

    Args:
        state: Current state dict

    Returns:
        Updated state dict
    """
    print_step_header()

    run_id = state.get("run_id", "unknown")
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / run_id))

    print(f"Run ID: {run_id}")
    print(f"运行目录: {run_dir}")
    print()

    # Load required data
    hierarchy_path = run_dir / "ahp_hierarchy.json"
    criteria_comp_path = run_dir / "criteria_comparisons.json"
    alt_scores_path = run_dir / "alternative_scores.json"
    ahp_results_path = run_dir / "ahp_results.json"

    if not all(p.exists() for p in [hierarchy_path, criteria_comp_path, alt_scores_path, ahp_results_path]):
        print("  [错误] 找不到必要的AHP数据文件")
        return state

    hierarchy = load_json(hierarchy_path)
    criteria_comp = load_json(criteria_comp_path)
    alt_scores_data = load_json(alt_scores_path)
    ahp_results = load_json(ahp_results_path)

    criteria = hierarchy.get("criteria_layer", [])
    alternatives = hierarchy.get("alternative_layer", [])
    criteria_comparisons = criteria_comp.get("comparisons", {})
    alternative_scores = alt_scores_data.get("average_scores", {})

    print(f"  准则数量: {len(criteria)}")
    print(f"  方案数量: {len(alternatives)}")
    print()

    # Run criteria sensitivity analysis
    print("=" * 60)
    print("  【准则权重敏感性分析】")
    print("=" * 60)
    print()

    criteria_sensitivity = normalize_criteria_sensitivity(run_criteria_sensitivity(
        criteria, alternatives, criteria_comparisons, alternative_scores, variation=0.1
    ))

    print(f"  变幅: ±10%")
    print()

    for scenario in criteria_sensitivity.get("scenarios", []):
        crit_name = scenario.get("criteria_name", "?")
        orig_weight = scenario.get("original_weight", 0)

        changes_up = scenario.get("increase_scenario", {}).get("ranking_changes", {})
        changes_down = scenario.get("decrease_scenario", {}).get("ranking_changes", {})

        unstable_up = sum(1 for c in changes_up.values() if not c.get("stable", True))
        unstable_down = sum(1 for c in changes_down.values() if not c.get("stable", True))

        if unstable_up == 0 and unstable_down == 0:
            status = "✓ 排名稳定"
        else:
            status = f"⚠ 排名变化(↑{unstable_up}, ↓{unstable_down})"

        print(f"  {crit_name} (权重:{orig_weight:.4f})")
        print(f"    {status}")

    # Run score sensitivity analysis
    print()
    print("=" * 60)
    print("  【方案得分敏感性分析】")
    print("=" * 60)
    print()

    # Build criteria weights dict
    criteria_weights = {}
    for c in ahp_results.get("criteria", []):
        criteria_weights[c["id"]] = c.get("weight", 0)

    score_sensitivity = normalize_score_sensitivity(run_score_sensitivity(
        alternatives, criteria_weights, alternative_scores, variation=0.1
    ))

    print(f"  变幅: ±10%")
    print()

    for scenario in score_sensitivity.get("scenarios", []):
        alt_name = scenario.get("alternative_name", "?")
        orig_score = scenario.get("original_score", 0)

        changes_up = scenario.get("increase_scenario", {}).get("ranking_changes", {})
        changes_down = scenario.get("decrease_scenario", {}).get("ranking_changes", {})

        unstable_up = sum(1 for c in changes_up.values() if not c.get("stable", True))
        unstable_down = sum(1 for c in changes_down.values() if not c.get("stable", True))

        if unstable_up == 0 and unstable_down == 0:
            status = "✓ 排名稳定"
        else:
            status = f"⚠ 排名变化(↑{unstable_up}, ↓{unstable_down})"

        print(f"  {alt_name} (得分:{orig_score:.2f})")
        print(f"    {status}")

    # Save sensitivity results
    sensitivity_data = {
        "run_id": run_id,
        "criteria_sensitivity": criteria_sensitivity,
        "score_sensitivity": score_sensitivity,
        "timestamp": datetime.now().isoformat(),
    }
    save_json(run_dir / "sensitivity_analysis.json", sensitivity_data)

    # Generate summary markdown
    summary_text = generate_sensitivity_summary(sensitivity_data)
    summary_path = run_dir / "sensitivity_summary.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f"\n  [已保存] {summary_path}")

    # Overall stability assessment
    print()
    stable_count = 0
    total_scenarios = 0

    for scenario in criteria_sensitivity.get("scenarios", []):
        changes_up = scenario.get("increase_scenario", {}).get("ranking_changes", {})
        changes_down = scenario.get("decrease_scenario", {}).get("ranking_changes", {})
        unstable_up = sum(1 for c in changes_up.values() if not c.get("stable", True))
        unstable_down = sum(1 for c in changes_down.values() if not c.get("stable", True))
        total_scenarios += 1
        if unstable_up == 0:
            stable_count += 1
        total_scenarios += 1
        if unstable_down == 0:
            stable_count += 1

    for scenario in score_sensitivity.get("scenarios", []):
        changes_up = scenario.get("increase_scenario", {}).get("ranking_changes", {})
        changes_down = scenario.get("decrease_scenario", {}).get("ranking_changes", {})
        unstable_up = sum(1 for c in changes_up.values() if not c.get("stable", True))
        unstable_down = sum(1 for c in changes_down.values() if not c.get("stable", True))
        total_scenarios += 1
        if unstable_up == 0:
            stable_count += 1
        total_scenarios += 1
        if unstable_down == 0:
            stable_count += 1

    stable_pct = stable_count / total_scenarios * 100 if total_scenarios > 0 else 0

    print("=" * 60)
    print("  【总体稳健性评估】")
    print("=" * 60)
    print()
    print(f"  稳定场景比例: {stable_pct:.1f}% ({stable_count}/{total_scenarios})")

    if stable_pct >= 80:
        print("  结果稳健性: 高 - AHP分析结果具有良好的稳定性")
    elif stable_pct >= 50:
        print("  结果稳健性: 中 - 部分参数变化会影响排名")
    else:
        print("  结果稳健性: 低 - 建议重新审视判断矩阵")

    state["sensitivity_result"] = sensitivity_data
    state["run_status"] = "step7_completed"

    print()
    print("=" * 60)
    print("  步骤 7 完成！")
    print("=" * 60)
    print(f"\n  已生成文件：")
    print(f"    - sensitivity_analysis.json (敏感性分析详情)")
    print(f"    - sensitivity_summary.md (敏感性分析汇总)")

    return state
