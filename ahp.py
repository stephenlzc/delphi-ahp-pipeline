"""
AHP (Analytic Hierarchy Process) implementation.
"""
from __future__ import annotations

import random
from typing import List, Dict, Tuple
from models import Factor, Score, AHPResult


def validate_comparison_matrix(matrix: List[List[float]], epsilon: float = 0.01) -> Tuple[bool, str]:
    """
    Validate that a comparison matrix satisfies AHP requirements.

    Args:
        matrix: The comparison matrix to validate
        epsilon: Tolerance for floating point comparisons

    Returns:
        Tuple of (is_valid, error_message)
    """
    n = len(matrix)
    if n < 2:
        return False, "Matrix dimension must be at least 2"

    for i in range(n):
        # Check diagonal is 1
        if abs(matrix[i][i] - 1.0) > epsilon:
            return False, f"Diagonal element matrix[{i}][{i}] must be 1.0"
        for j in range(n):
            # Check reciprocity: a[i,j] * a[j,i] should ≈ 1
            product = matrix[i][j] * matrix[j][i]
            if abs(product - 1.0) > epsilon:
                return False, f"Matrix does not satisfy reciprocity: matrix[{i}][{j}] * matrix[{j}][{i}] = {product}, expected = 1.0"
            # Check all values are positive
            if matrix[i][j] <= 0:
                return False, f"Matrix element matrix[{i}][{j}] must be positive"

    return True, "OK"


def validate_pairwise_matrix_with_details(
    matrix: List[List[float]],
    names: List[str],
    epsilon: float = 0.01,
) -> Tuple[bool, List[dict]]:
    """
    Validate pairwise matrix and return detailed violation info for each pair.

    Returns:
        Tuple of (is_valid, violations)
        violations: list of dicts with keys: i, j, name_i, name_j, aij, aji, product, suggestion
    """
    n = len(matrix)
    violations = []
    for i in range(n):
        for j in range(i + 1, n):
            aij = matrix[i][j]
            aji = matrix[j][i]
            product = aij * aji
            if abs(product - 1.0) > epsilon or aij <= 0:
                # Compute suggested value: use geometric mean of aij and 1/aji
                suggested = (aij * (1.0 / aji)) ** 0.5 if aji != 0 else aij
                suggested_clamped = max(1.0, min(9.0, suggested))
                violations.append({
                    "i": i,
                    "j": j,
                    "name_i": names[i],
                    "name_j": names[j],
                    "aij": round(aij, 3),
                    "aji": round(aji, 3),
                    "product": round(product, 3),
                    "suggested": round(suggested_clamped, 2),
                })
    return len(violations) == 0, violations


def suggest_consistency_improvements(
    matrix: List[List[float]],
    weights: List[float],
    names: List[str],
    top_k: int = 3,
) -> List[dict]:
    """
    Find the comparison pairs most likely causing inconsistency and suggest adjustments.

    Uses the consistency indicator: (weighted_sum / weight_i) / lambda_max.
    Pairs with values furthest from the implied consensus contribute most to CI.

    Returns:
        List of dicts with keys: i, j, name_i, name_j, current_value, implied, suggestion, deviation
    """
    n = len(matrix)
    if n < 2 or not weights:
        return []

    # Calculate weighted sum ratio for each row
    weighted_sums = []
    for i in range(n):
        ws = sum(matrix[i][k] * weights[k] for k in range(n))
        weighted_sums.append(ws)

    # Implied values: w_i / w_j
    implied = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif weights[j] > 0:
                row.append(weights[i] / weights[j])
            else:
                row.append(1.0)
        implied.append(row)

    # For each pair i<j, compute deviation from implied
    deviations = []
    for i in range(n):
        for j in range(i + 1, n):
            current = matrix[i][j]
            imp = implied[i][j]
            if imp > 0:
                deviation = abs(current - imp) / imp
            else:
                deviation = abs(current - 1.0)
            # Suggestion: move current toward implied value, clamped to Saaty scale
            suggested = max(1.0, min(9.0, imp))
            deviations.append({
                "i": i,
                "j": j,
                "name_i": names[i],
                "name_j": names[j],
                "current": round(current, 2),
                "implied": round(imp, 2),
                "suggested": round(suggested, 2),
                "deviation": round(deviation, 3),
            })

    # Sort by deviation descending, take top-k
    deviations.sort(key=lambda x: x["deviation"], reverse=True)
    return deviations[:top_k]


def build_comparison_matrix(
    factors: List[Factor],
    scores: List[Score]
) -> Tuple[List[List[float]], Dict[str, float]]:
    """
    Build pairwise comparison matrix from expert scores.

    Args:
        factors: List of factors
        scores: List of expert scores

    Returns:
        Tuple of (comparison_matrix, average_scores)
    """
    n = len(factors)
    factor_ids = [f.id for f in factors]

    # Calculate average score per factor
    factor_score_lists: Dict[str, List[float]] = {f.id: [] for f in factors}
    for s in scores:
        if s.factor_id in factor_score_lists:
            factor_score_lists[s.factor_id].append(s.score)

    avg_scores: Dict[str, float] = {}
    for fid, score_list in factor_score_lists.items():
        avg_scores[fid] = sum(score_list) / len(score_list) if score_list else 5.0

    # Build comparison matrix using ratio of average scores
    matrix = [[1.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            elif i < j:
                score_i = avg_scores.get(factor_ids[i], 5.0)
                score_j = avg_scores.get(factor_ids[j], 5.0)
                if score_j > 0:
                    ratio = score_i / score_j
                    # Limit to 1-9 scale
                    ratio = max(0.11, min(9.0, ratio))
                    matrix[i][j] = round(ratio, 2)
                    matrix[j][i] = round(1.0 / ratio, 2) if ratio != 0 else 1.0

    return matrix, avg_scores


def build_criteria_comparison_matrix(
    criteria: List[str],
    pairwise_values: List[List[float]]
) -> List[List[float]]:
    """
    Build criteria comparison matrix from pairwise comparison values.

    Args:
        criteria: List of criteria IDs
        pairwise_values: Matrix of comparison values where [i][j] = value for i/j

    Returns:
        Full comparison matrix
    """
    n = len(criteria)
    matrix = [[1.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = pairwise_values[i][j]

    return matrix


def calculate_weights(matrix: List[List[float]]) -> List[float]:
    """
    Calculate priority weights using geometric mean method.

    Args:
        matrix: Pairwise comparison matrix

    Returns:
        List of weights
    """
    n = len(matrix)
    if n == 0:
        return []

    # Calculate geometric mean for each row
    weights = []
    for i in range(n):
        row_product = 1.0
        for j in range(n):
            row_product *= matrix[i][j]
        # Handle zero or negative product (invalid comparison matrix)
        # Use small epsilon to avoid zero weights causing division errors later
        if row_product <= 0:
            weights.append(1e-10)  # Small positive value instead of 0
        else:
            weights.append(row_product ** (1.0 / n))

    # Normalize
    total = sum(weights)
    if total > 0:
        weights = [w / total for w in weights]

    return weights


def calculate_consistency(
    matrix: List[List[float]],
    weights: List[float]
) -> Tuple[float, float, float]:
    """
    Calculate consistency ratio.

    Args:
        matrix: Pairwise comparison matrix
        weights: Priority weights

    Returns:
        Tuple of (lambda_max, CI, CR)
    """
    n = len(matrix)
    if n < 2:
        return float(n), 0.0, 0.0

    # Calculate lambda_max
    weighted_sums = []
    for i in range(n):
        ws = sum(matrix[i][j] * weights[j] for j in range(n))
        weighted_sums.append(ws / weights[i] if weights[i] > 0 else 0)

    lambda_max = sum(weighted_sums) / n if n > 0 else n

    # Calculate CI
    ci = (lambda_max - n) / (n - 1) if n > 1 else 0

    # RI table
    ri_table = {
        1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12,
        6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49
    }
    ri = ri_table.get(n, 1.49)

    # Calculate CR
    cr = ci / ri if ri > 0 else 0

    return lambda_max, ci, cr


def run_ahp(factors: List[Factor], scores: List[Score]) -> AHPResult:
    """
    Run full AHP calculation.

    Args:
        factors: List of factors
        scores: List of expert scores

    Returns:
        AHPResult object
    """
    n = len(factors)

    if n < 2:
        return AHPResult(
            weights={},
            factor_details=[],
            consistency_ratio=0.0,
            consistency_passed=True,
            matrix=[],
            lambda_max=0.0
        )

    # Build comparison matrix
    matrix, avg_scores = build_comparison_matrix(factors, scores)

    # Calculate weights
    weights = calculate_weights(matrix)

    # Calculate consistency
    lambda_max, ci, cr = calculate_consistency(matrix, weights)

    # Create factor details with weights
    factor_details = []
    for i, factor in enumerate(factors):
        factor_details.append({
            "id": factor.id,
            "name": factor.name,
            "weight": round(weights[i], 4),
            "avg_score": round(avg_scores.get(factor.id, 0), 2),
        })

    # Sort by weight descending
    factor_details.sort(key=lambda x: x["weight"], reverse=True)

    # Add rank
    for i, fd in enumerate(factor_details):
        fd["rank"] = i + 1

    # Build weights dict
    weights_dict = {factors[i].id: round(weights[i], 4) for i in range(n)}

    return AHPResult(
        weights=weights_dict,
        factor_details=factor_details,
        consistency_ratio=round(cr, 4),
        consistency_passed=cr <= 0.1,
        matrix=[[round(m, 2) for m in row] for row in matrix],
        lambda_max=round(lambda_max, 4)
    )


def run_hierarchical_ahp(
    criteria: List[dict],
    alternatives: List[dict],
    criteria_comparisons: Dict[str, Dict[str, float]],
    alternative_scores: Dict[str, float],
) -> Dict:
    """
    Run hierarchical AHP calculation.

    Supports two input formats for alternative_scores:
    - New format (P1 pairwise): {criterion_id: {alternative_id: local_weight}}
      Each alternative's weight is computed from pairwise comparisons within its criterion.
    - Legacy format (direct scoring): {alternative_id: avg_score (1-10)}
      Alternatives are scored directly and normalized to 0-1.

    Args:
        criteria: List of criteria dicts with id, name, description
        alternatives: List of alternative dicts with id, name, belongs_to_criteria
        criteria_comparisons: Dict mapping "i,j" to comparison value
        alternative_scores: Either {criterion_id: {alt_id: local_weight}}
                           or {alt_id: avg_score}

    Returns:
        Dict with criteria_weights, alternative_weights, combined_weights
    """
    n_criteria = len(criteria)
    criteria_ids = [c["id"] for c in criteria]
    criteria_names = [c["name"] for c in criteria]

    # Build criteria comparison matrix
    criteria_matrix = [[1.0 for _ in range(n_criteria)] for _ in range(n_criteria)]
    for i in range(n_criteria):
        for j in range(i + 1, n_criteria):
            key = f"{i},{j}"
            val = criteria_comparisons.get(key, 1.0)
            criteria_matrix[i][j] = val
            criteria_matrix[j][i] = 1.0 / val if val > 0 else 1.0

    # P0: Validate reciprocity before computing
    reciprocity_ok, reciprocity_violations = validate_pairwise_matrix_with_details(
        criteria_matrix, criteria_names
    )
    if not reciprocity_ok:
        violation_msgs = []
        for v in reciprocity_violations:
            violation_msgs.append(
                f"  • {v['name_i']} vs {v['name_j']}: "
                f"当前值 {v['aij']} / {v['aji']}（乘积={v['product']}），"
                f"建议调整为 {v['suggested']} 以满足互反性"
            )
        raise ValueError(
            "Criteria layer judgment matrix violates reciprocity, cannot continue:\n" + "\n".join(violation_msgs)
        )

    # Calculate criteria weights
    criteria_weights = calculate_weights(criteria_matrix)
    criteria_lambda_max, criteria_ci, criteria_cr = calculate_consistency(
        criteria_matrix, criteria_weights
    )

    # P1: Detect input format
    # New format: first value is a dict {alt_id: weight}
    # Legacy format: first value is a float (avg score)
    first_val = next(iter(alternative_scores.values()), None) if alternative_scores else None
    is_new_format = isinstance(first_val, dict)

    if is_new_format:
        # P1 new format: {criterion_id: {alternative_id: local_weight}}
        # Each alternative's combined weight = criterion_weight × local_weight
        local_weights_by_criterion: Dict[str, Dict[str, float]] = alternative_scores
        combined_weights = {}
        raw_scores = {}
        for alt in alternatives:
            alt_id = alt["id"]
            crit_id = alt.get("belongs_to_criteria", criteria_ids[0] if criteria_ids else "C1")
            try:
                crit_idx = criteria_ids.index(crit_id)
            except ValueError:
                crit_idx = 0
            crit_weight = criteria_weights[crit_idx] if crit_idx < len(criteria_weights) else 1.0 / n_criteria
            local_w = local_weights_by_criterion.get(crit_id, {}).get(alt_id, 0.0)
            # P2: pure linear combination, no ad-hoc offset
            combined_weights[alt_id] = round(crit_weight * local_w, 4)
            raw_scores[alt_id] = local_w
    else:
        # Legacy format: {alt_id: avg_score (1-10)} — normalize to 0-1
        alt_ids = [a["id"] for a in alternatives]
        scores_dict: Dict[str, float] = alternative_scores
        max_score = max(scores_dict.values()) if scores_dict else 10.0
        min_score = min(scores_dict.values()) if scores_dict else 1.0
        score_range = max_score - min_score if max_score > min_score else 1.0
        normalized_scores = {
            alt_id: (score - min_score) / score_range
            for alt_id, score in scores_dict.items()
        }
        combined_weights = {}
        raw_scores = {}
        for alt in alternatives:
            alt_id = alt["id"]
            crit_id = alt.get("belongs_to_criteria", criteria_ids[0] if criteria_ids else "C1")
            try:
                crit_idx = criteria_ids.index(crit_id)
            except ValueError:
                crit_idx = 0
            crit_weight = criteria_weights[crit_idx] if crit_idx < len(criteria_weights) else 1.0 / n_criteria
            alt_score = normalized_scores.get(alt_id, 0.5)
            # P2: pure linear combination
            combined_weights[alt_id] = round(crit_weight * alt_score, 4)
            raw_scores[alt_id] = scores_dict.get(alt_id, 0.0)

    # Sort by combined weight
    sorted_weights = sorted(combined_weights.items(), key=lambda x: x[1], reverse=True)

    # P4: Generate consistency improvement suggestions when CR > 0.1
    consistency_guidance = None
    if criteria_cr > 0.1:
        top_violations = suggest_consistency_improvements(
            criteria_matrix, criteria_weights, criteria_names, top_k=3
        )
        guidance_items = []
        for v in top_violations:
            direction = "decrease" if v["current"] > v["implied"] else "increase"
            guidance_items.append(
                f"  • {v['name_i']} vs {v['name_j']}: "
                f"current value {v['current']} → suggest adjusting to {v['suggested']} "
                f"({direction}, more consistent with other judgments)"
            )
        consistency_guidance = {
            "message": (
                f"Criteria layer consistency ratio CR={round(criteria_cr, 4)} > 0.10, consistency check failed."
                "Priority adjustment suggestions:"
            ),
            "suggestions": guidance_items,
        }

    # Build result
    result = {
        "criteria": [
            {
                "id": criteria[i]["id"],
                "name": criteria[i]["name"],
                "weight": round(criteria_weights[i], 4),
                "lambda_max": round(criteria_lambda_max, 4),
                "ci": round(criteria_ci, 4),
                "cr": round(criteria_cr, 4),
                "consistency_passed": criteria_cr <= 0.1,
            }
            for i in range(n_criteria)
        ],
        "alternatives": [
            {
                "id": alt["id"],
                "name": alt["name"],
                "belongs_to_criteria": alt.get("belongs_to_criteria", ""),
                "combined_weight": combined_weights.get(alt["id"], 0),
                "raw_score": raw_scores.get(alt["id"], 0),
            }
            for alt in alternatives
        ],
        "criteria_consistency": {
            "lambda_max": round(criteria_lambda_max, 4),
            "ci": round(criteria_ci, 4),
            "cr": round(criteria_cr, 4),
            "passed": criteria_cr <= 0.1,
        },
        "consistency_guidance": consistency_guidance,
        "ranking": [
            {"rank": i + 1, "id": wid, "weight": w}
            for i, (wid, w) in enumerate(sorted_weights)
        ],
    }

    return result


def display_ahp_results(result: AHPResult) -> None:
    """
    Print AHP results to console.

    Args:
        result: AHPResult object
    """
    print(f"\nConsistency Ratio (CR): {result.consistency_ratio:.4f}")
    print(f"Maximum Eigenvalue: {result.lambda_max:.4f}")
    print(f"Consistency Check: {'Passed' if result.consistency_passed else 'Failed'}")

    if not result.consistency_passed:
        print("\n  [Warning] Consistency ratio exceeds 0.10, judgment matrix may need adjustment")

    print(f"\n{'Rank':<6} {'ID':<8} {'Name':<20} {'Weight':<10} {'Avg Score':<8}")
    print("-" * 60)

    for fd in result.factor_details:
        print(f"{fd['rank']:<6} {fd['id']:<8} {fd['name']:<20} {fd['weight']:<10.4f} {fd['avg_score']:<8.2f}")

    # Display weight distribution bar
    print("\nWeight Distribution:")
    max_weight = max(fd["weight"] for fd in result.factor_details)
    for fd in result.factor_details:
        bar_len = int(fd["weight"] / max_weight * 30) if max_weight > 0 else 0
        bar = "█" * bar_len + "░" * (30 - bar_len)
        print(f"  {fd['name']:<15} {bar} {fd['weight']:.2%}")
