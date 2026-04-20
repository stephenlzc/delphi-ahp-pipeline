"""
Step 6: Delphi Convergence Check
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from statistics import stdev, mean
import questionary
from steps.colors import (
    Colors, color, red, green, yellow, blue, magenta, cyan, white,
    bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan
)


def print_step_header():
    """Print step 6 header."""
    print()
    print("-" * 60)
    print("  Step 6/8: Convergence Check & Expert Opinion Summary")
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


def ask_float(prompt: str, default: float, min_val: float = 0, max_val: float = 10) -> float:
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


def load_json(filepath: Path) -> dict:
    """Load JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [Warning] Failed to read file {filepath}: {e}")
        return {}


def save_json(filepath: Path, data: dict):
    """Save JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [Saved] {filepath}")


def calculate_cv(scores: List[float]) -> Tuple[float, float, float, float]:
    """
    Calculate Coefficient of Variation for a list of scores.

    Returns:
        Tuple of (mean, std_dev, cv, cv_percent)
    """
    if len(scores) < 2:
        return mean(scores) if scores else 0.0, 0.0, 0.0, 0.0

    m = mean(scores)
    s = stdev(scores)
    cv = s / m if m != 0 else 0.0
    cv_percent = cv * 100

    return m, s, cv, cv_percent


def calculate_expert_agreement(scores: List[float]) -> str:
    """
    Determine expert agreement level based on scores.
    """
    if len(scores) < 2:
        return "Insufficient data"

    m, s, cv, cv_percent = calculate_cv(scores)

    if cv_percent <= 20:
        return "Highly consistent"
    elif cv_percent <= 40:
        return "Basically consistent"
    elif cv_percent <= 60:
        return "Significant disagreement"
    else:
        return "Serious disagreement"


def check_factor_convergence(
    factor_scores: Dict[str, List[float]],
    threshold: float = 0.5
) -> Dict[str, dict]:
    """
    Check convergence for all factors.

    Args:
        factor_scores: Dict mapping factor_id to list of expert scores
        threshold: CV threshold (default 0.5 = 50%)

    Returns:
        Dict with convergence status for each factor
    """
    result = {}
    for factor_id, scores in factor_scores.items():
        m, s, cv, cv_percent = calculate_cv(scores)
        result[factor_id] = {
            "mean": round(m, 4),
            "std_dev": round(s, 4),
            "cv": round(cv, 4),
            "cv_percent": round(cv_percent, 2),
            "converged": cv <= threshold,
            "scores": scores,
            "expert_count": len(scores),
            "agreement": calculate_expert_agreement(scores),
        }
    return result


def generate_convergence_summary(convergence_results: dict) -> str:
    """Generate convergence summary text."""
    total = len(convergence_results)
    converged = sum(1 for r in convergence_results.values() if r["converged"])
    not_converged = total - converged
    conv_pct = (converged / total * 100) if total > 0 else 0.0

    summary = f"""# 收敛检验汇总

## 总体情况
- 检验因素总数：{total}
- 已收敛因素数：{converged} ({conv_pct:.1f}%)
- 未收敛因素数：{not_converged} ({not_converged/total*100:.1f}%)

## 收敛判断标准
- 变异系数(CV) ≤ 0.50（50%）视为收敛
- CV ≤ 20%：高度一致
- CV 20%-40%：基本一致
- CV 40%-60%：分歧较大
- CV > 60%：分歧严重

## 各因素收敛状态
"""

    for fid, result in convergence_results.items():
        status = "✓ 已收敛" if result["converged"] else "✗ 未收敛"
        summary += f"- {fid}: CV={result['cv_percent']:.2f}% ({result['agreement']}) {status}\n"

    return summary


def display_convergence_results(convergence_results: dict, factors: List[dict], ahp_consistency: dict = None) -> bool:
    """
    Display convergence results and ask for user confirmation.

    Returns:
        True if user confirms results are acceptable, False otherwise
    """
    print("=" * 60)
    print("  【收敛检验结果】")
    print("=" * 60)
    print()

    # Criteria: CV <= 0.5 (50%)
    print("【评分收敛性检验】")
    print(f"{'因素ID':<8} {'因素名称':<15} {'均值':<8} {'标准差':<8} {'CV':<10} {'一致性'}")
    print("-" * 70)

    converged_count = 0
    not_converged_factors = []

    for factor in factors:
        fid = factor.get("id", "?")
        fname = factor.get("name", "未知")[:14]
        result = convergence_results.get(fid, {})

        cv = result.get("cv", 0)
        cv_display = f"{result.get('cv_percent', 0):.2f}%"
        agreement = result.get("agreement", "未知")
        mean_val = result.get("mean", 0)
        std_val = result.get("std_dev", 0)

        status_icon = "✓" if result.get("converged", False) else "✗"
        print(f"{fid:<8} {fname:<15} {mean_val:<8.2f} {std_val:<8.2f} {cv_display:<10} {agreement} {status_icon}")

        if result.get("converged", False):
            converged_count += 1
        else:
            not_converged_factors.append((fid, fname, cv_display, result.get("scores", [])))

    print()
    total = len(factors)
    print(f"  收敛比例: {converged_count}/{total} ({converged_count/total*100:.1f}%)")

    if converged_count == total:
        print("  ✓ 所有因素评分已收敛，专家意见达成一致")
        cv_status = "通过"
    elif converged_count >= total * 0.8:
        print("  ⚠ 多数因素已收敛，个别因素存在分歧")
        cv_status = "基本通过"
    elif converged_count >= total * 0.5:
        print("  ⚠ 部分因素未收敛，存在较大分歧")
        cv_status = "待改进"
    else:
        print("  ✗ 多数因素未收敛，专家意见分歧严重")
        cv_status = "未通过"

    # AHP consistency check
    print()
    print("【AHP一致性检验】")
    print("-" * 70)

    if ahp_consistency:
        cr = ahp_consistency.get("cr", 0)
        lambda_max = ahp_consistency.get("lambda_max", 0)
        ci = ahp_consistency.get("ci", 0)
        passed = ahp_consistency.get("passed", False)

        print(f"  λmax (最大特征值): {lambda_max:.4f}")
        print(f"  CI (一致性指标):   {ci:.4f}")
        print(f"  CR (一致性比例):   {cr:.4f}")
        print(f"  检验标准:          CR ≤ 0.10")

        if passed:
            print(f"  ✓ CR = {cr:.4f} ≤ 0.10，一致性检验通过")
            cr_status = "通过"
        else:
            print(f"  ✗ CR = {cr:.4f} > 0.10，一致性检验未通过")
            cr_status = "未通过"
    else:
        print("  [无AHP数据]")
        cr_status = "未知"

    print()
    print("=" * 60)
    print("  【检验结论】")
    print("=" * 60)

    overall_pass = (cv_status in ["通过", "基本通过"]) and (cr_status in ["通过", "未知"])
    if overall_pass:
        print(f"  评分收敛性: {cv_status}")
        print(f"  AHP一致性: {cr_status}")
        print()
        print("  ✓ 总体评价：检验基本通过，可以继续分析")
        return True
    else:
        print(f"  评分收敛性: {cv_status}")
        print(f"  AHP一致性: {cr_status}")
        print()
        print("  ✗ 总体评价：存在问题，需要修改")
        return False


def get_modification_guidance(
    not_converged_factors: List[Tuple],
    ahp_cr_failed: bool = False
) -> str:
    """
    Generate guidance for user on what and how to modify.

    Returns:
        Modification guidance text
    """
    guidance = []
    guidance.append("")
    guidance.append("=" * 60)
    guidance.append("  【修改建议】")
    guidance.append("=" * 60)
    guidance.append("")

    if not_converged_factors:
        guidance.append("【一、评分收敛性问题】")
        guidance.append("")
        guidance.append("  以下因素的专家意见分歧较大，需要调整：")
        guidance.append("")
        for fid, fname, cv_display, scores in not_converged_factors:
            guidance.append(f"  ▶ {fid} {fname}")
            guidance.append(f"    当前CV值: {cv_display} (标准: ≤50%)")
            guidance.append(f"    专家局部权重: {[round(s, 4) for s in scores]}")
            guidance.append("")
        guidance.append("  修改方法：")
        guidance.append("  1. 打开 `alternative_scores.json` 文件")
        guidance.append("  2. 找到 expert_details 中对应专家的比较矩阵")
        guidance.append("  3. 调整 Saaty 判断值使各专家的局部权重趋于一致")
        guidance.append("  4. 保存文件后重新运行步骤6")
        guidance.append("")

    if ahp_cr_failed:
        guidance.append("【二、AHP一致性检验问题】")
        guidance.append("")
        guidance.append("  准则层判断矩阵一致性检验未通过（CR > 0.10）")
        guidance.append("")
        guidance.append("  修改方法：")
        guidance.append("  1. 打开 `criteria_comparisons.json` 文件")
        guidance.append("  2. 检查准则层两两比较的判断值")
        guidance.append("  3. 确保判断逻辑一致，例如：")
        guidance.append("     - 如果A比B重要(值为3)，则B比A应该为1/3")
        guidance.append("     - 如果A比B同等重要，值应为1")
        guidance.append("  4. 调整后重新计算，确保满足 Saaty 标度逻辑")
        guidance.append("  5. 保存文件后重新运行步骤6")
        guidance.append("")

    guidance.append("【三、通用修改规则】")
    guidance.append("")
    guidance.append("  Saaty 1-9 标度说明：")
    guidance.append("  1 = 同等重要")
    guidance.append("  3 = 略微重要")
    guidance.append("  5 = 明显重要")
    guidance.append("  7 = 强烈重要")
    guidance.append("  9 = 极端重要")
    guidance.append("  2,4,6,8 = 相邻判断的中间值")
    guidance.append("")
    guidance.append("  变异系数(CV)计算公式：CV = 标准差 / 均值")
    guidance.append("  CV ≤ 0.5 表示专家意见收敛")
    guidance.append("")

    return "\n".join(guidance)


def modify_scores_interactive(run_dir: Path, factors: List[dict]) -> bool:
    """
    Interactive score modification.

    Returns:
        True if user made modifications, False otherwise
    """
    print()
    print("=" * 60)
    print("  【交互式评分修改】")
    print("=" * 60)
    print()
    print("  提示：输入空格跳过当前因素，输入 'q' 退出修改模式")
    print()

    score_path = run_dir / "alternative_scores.json"
    score_data = load_json(score_path)
    fmt = score_data.get("format", "")

    # P1 新格式暂不支持交互式修改（需编辑矩阵，重算权重）
    if fmt == "pairwise_comparisons":
        print("  [提示] 成对比较格式暂不支持交互式修改。")
        print("  请直接编辑 alternative_scores.json 中的 expert_details 数据，")
        print("  然后重新运行步骤 6。")
        print()
        print("  具体修改方式：")
        print("  - 找到 expert_details 中对应专家的 criterion_matrices")
        print("  - 调整矩阵中的比较值（Saaty 1-9 标度）")
        print("  - 保存后重新运行即可")
        return False

    expert_scores = score_data.get("expert_scores", [])

    modified = False

    for factor in factors:
        fid = factor.get("id", "?")
        fname = factor.get("name", "未知")

        print(f"  因素 {fid}: {fname}")
        print("  " + "-" * 40)

        # Find scores for this factor
        factor_score_idx = None
        for i, es in enumerate(expert_scores):
            for j, s in enumerate(es.get("scores", [])):
                if s.get("factor_id") == fid:
                    factor_score_idx = (i, j)
                    break
            if factor_score_idx:
                break

        if factor_score_idx is None:
            print("    未找到评分记录，跳过")
            print()
            continue

        # Validate indices are within bounds
        i, j = factor_score_idx
        if i < 0 or i >= len(expert_scores):
            print("    评分数据结构异常，跳过")
            print()
            continue
        es = expert_scores[i]
        scores_list = es.get("scores", [])
        if not isinstance(scores_list, list) or j < 0 or j >= len(scores_list):
            print("    评分数据结构异常，跳过")
            print()
            continue

        expert_name = es.get("expert_name", f"专家{i+1}")
        current_score = scores_list[j].get("score", 0)

        response = ask(f"    专家{i+1}({expert_name})当前评分: {current_score} -> 修改为", str(int(current_score)))

        if response.lower() == 'q':
            print("\n    退出修改模式")
            break
        elif response.strip() == '':
            print("    保持不变")
        else:
            try:
                new_score = float(response)
                if 1 <= new_score <= 10:
                    scores_list[j]["score"] = new_score
                    print(f"    已修改为: {new_score}")
                    modified = True
                else:
                    print("    评分必须在1-10之间，保持不变")
            except ValueError:
                print("    无效输入，保持不变")

        print()

    if modified:
        print("  [确认] 保存修改后的评分？")
        if questionary.confirm("  保存修改", default=True).ask():
            # Recalculate average scores
            avg_scores = {}
            for es in expert_scores:
                for s in es.get("scores", []):
                    fid = s.get("factor_id")
                    if fid not in avg_scores:
                        avg_scores[fid] = []
                    avg_scores[fid].append(s.get("score", 0))

            final_avg = {}
            for fid, scores in avg_scores.items():
                final_avg[fid] = sum(scores) / len(scores) if scores else 7.0

            score_data["average_scores"] = final_avg
            save_json(score_path, score_data)
            print("  [已保存] 修改后的评分")
            return True

    return False


def recalc_convergence_from_scores(
    score_path: Path,
    factors: List[dict],
    ahp_consistency: dict | None,
) -> Tuple[List[dict], dict, bool]:
    """
    Recalculate convergence from persisted scores and display results.
    Supports both old (direct scoring) and new (pairwise comparison) formats.

    Returns:
        (expert_records, convergence_results, overall_pass)
    """
    score_data = load_json(score_path)
    fmt = score_data.get("format", "")
    factor_scores: Dict[str, List[float]] = {}

    if fmt == "pairwise_comparisons":
        # P1 新格式
        expert_details = score_data.get("expert_details", [])
        alternatives_by_criteria = score_data.get("alternatives_by_criteria", {})
        # Rebuild factors list from alternatives_by_criteria
        factors = []
        for crit_id, alts in alternatives_by_criteria.items():
            factors.extend(alts)
        # alt_id -> criterion_id
        alt_to_crit: Dict[str, str] = {}
        for crit_id, alts in alternatives_by_criteria.items():
            for alt in alts:
                alt_to_crit[alt["id"]] = crit_id
        factor_scores = {alt["id"]: [] for alt in factors}
        for ed in expert_details:
            local_w = ed.get("local_weights", {})
            for alt_id, crit_id in alt_to_crit.items():
                w = local_w.get(crit_id, {}).get(alt_id, 0.0)
                if w > 0:
                    factor_scores[alt_id].append(w)
        return_data = expert_details
    else:
        # 旧格式
        expert_scores = score_data.get("expert_scores", [])
        factor_scores = {f.get("id", "?"): [] for f in factors}
        for es in expert_scores:
            for score_record in es.get("scores", []):
                fid = score_record.get("factor_id")
                score_val = score_record.get("score", 0)
                if fid in factor_scores:
                    factor_scores[fid].append(score_val)
        return_data = expert_scores

    convergence_results = check_factor_convergence(factor_scores, threshold=0.5)
    overall_pass = display_convergence_results(convergence_results, factors, ahp_consistency)
    return return_data, convergence_results, overall_pass


def run_step6(state: dict) -> dict:
    """
    Run step 6: Delphi convergence check and expert opinion summary.

    This step:
    1. Loads alternative scores from step 5
    2. Calculates coefficient of variation (CV) for each factor
    3. Displays results for user review
    4. User can confirm or request modifications
    5. After modifications, regenerates results

    Args:
        state: Current state dict

    Returns:
        Updated state dict
    """
    print_step_header()

    run_id = state.get("run_id", "unknown")
    run_dir = Path(state.get("run_dir", Path(__file__).parent.parent / "run_result" / run_id))
    project = state.get("project", {})

    print(f"Run ID: {run_id}")
    print(f"运行目录: {run_dir}")
    print()

    # Check required files
    score_path = run_dir / "alternative_scores.json"
    if not score_path.exists():
        print("  [错误] 找不到 alternative_scores.json")
        return state

    score_data = load_json(score_path)
    fmt = score_data.get("format", "")

    # Build factor -> scores mapping (format-agnostic)
    factor_scores: Dict[str, List[float]] = {}

    if fmt == "pairwise_comparisons":
        # P1 新格式：成对比较
        # 每位专家对每个方案在其所属准则下给出一个局部权重
        # 收敛检验：对每个方案，收集所有专家的局部权重，计算 CV
        expert_details = score_data.get("expert_details", [])
        # alternatives_by_criteria: {crit_id: [alt_dict, ...]}
        alternatives_by_criteria = score_data.get("alternatives_by_criteria", {})
        # 构建 alt_id -> criterion_id 映射
        alt_to_crit: Dict[str, str] = {}
        for crit_id, alts in alternatives_by_criteria.items():
            for alt in alts:
                alt_to_crit[alt["id"]] = crit_id
        # factors = 所有 alternative
        factors = []
        for crit_id, alts in alternatives_by_criteria.items():
            factors.extend(alts)
        # 构建 alt_id -> name 映射（用于 display）
        alt_names: Dict[str, str] = {alt["id"]: alt.get("name", "未知") for alt in factors}

        # 初始化 factor_scores
        for alt in factors:
            factor_scores[alt["id"]] = []

        # 填充每专家的局部权重
        for ed in expert_details:
            local_w = ed.get("local_weights", {})  # {crit_id: {alt_id: weight}}
            for alt_id, crit_id in alt_to_crit.items():
                w = local_w.get(crit_id, {}).get(alt_id, 0.0)
                if w > 0:
                    factor_scores[alt_id].append(w)

        # factor_scores 现在是 {alt_id: [per-expert local weights]}
        print(f"  找到 {len(expert_details)} 位专家的方案层成对比较记录")
        print(f"  待检验因素数: {len(factors)}")
        print(f"  注：收敛检验基于各专家对每因素的局部权重（CV 阈值 50%）")
        print()
        expert_scores_for_save = expert_details  # 仅用于保存摘要，不用于修改
    else:
        # 旧格式：直接评分
        expert_scores = score_data.get("expert_scores", [])
        factors = score_data.get("factors", [])

        if not expert_scores:
            print("  [错误] 找不到专家评分数据")
            return state

        print(f"  找到 {len(expert_scores)} 位专家的评分记录")
        print(f"  待检验因素数: {len(factors)}")
        print()

        for factor in factors:
            fid = factor.get("id", "?")
            factor_scores[fid] = []

        for es in expert_scores:
            for score_record in es.get("scores", []):
                fid = score_record.get("factor_id")
                score_val = score_record.get("score", 0)
                if fid in factor_scores:
                    factor_scores[fid].append(score_val)
        expert_scores_for_save = expert_scores

    # Load AHP results for consistency check
    ahp_path = run_dir / "ahp_results.json"
    ahp_consistency = None
    if ahp_path.exists():
        ahp_data = load_json(ahp_path)
        crit_cons = ahp_data.get("criteria_consistency", {})
        ahp_consistency = {
            "cr": crit_cons.get("cr", 0),
            "lambda_max": crit_cons.get("lambda_max", 0),
            "ci": crit_cons.get("ci", 0),
            "passed": crit_cons.get("passed", False),
        }

    # Calculate convergence
    convergence_results = check_factor_convergence(factor_scores, threshold=0.5)

    # Check for issues
    converged_count = sum(1 for r in convergence_results.values() if r["converged"])
    not_converged_factors = [
        (f.get("id", "?"), f.get("name", "未知")[:14],
         f"{convergence_results.get(f.get('id', '?'), {}).get('cv_percent', 0):.2f}%",
         convergence_results.get(f.get('id', '?'), {}).get("scores", []))
        for f in factors
        if not convergence_results.get(f.get("id", "?"), {}).get("converged", False)
    ]

    ahp_cr_failed = ahp_consistency and not ahp_consistency.get("passed", False)

    # Display results and ask for confirmation
    overall_pass = display_convergence_results(convergence_results, factors, ahp_consistency)

    # Show modification guidance if needed
    if not overall_pass:
        print(get_modification_guidance(not_converged_factors, ahp_cr_failed))

    # Ask user what to do
    print()
    if overall_pass:
        print("  检验结果已通过，您可以直接继续。")
        if not questionary.confirm("\n  是否需要查看或修改评分？", default=False).ask():
            # User is satisfied, save and continue
            pass
        else:
            # User wants to modify
            modified = modify_scores_interactive(run_dir, factors)
            if modified:
                print("\n  重新计算收敛检验...")
                expert_scores_for_save, convergence_results, overall_pass = recalc_convergence_from_scores(
                    score_path, factors, ahp_consistency
                )
                if not overall_pass:
                    print("\n  修改后仍未通过收敛检验。")
                    if questionary.confirm("  是否跳过步骤6继续后续步骤？", default=False).ask():
                        overall_pass = True
                    else:
                        print("\n  请继续调整评分后重新运行步骤6")
                        return state
            else:
                print("\n  未保存任何评分修改，保持原检验结果。")
    else:
        print("  检验结果未通过，请根据上述建议修改后重新运行。")
        print()
        print("  您可以选择：")
        print("    1. 手动修改 JSON 文件后，重新运行步骤6")
        print("    2. 使用交互式修改（输入 'm'）")
        print("    3. 跳过步骤6继续后续步骤（可能影响结果准确性）")
        print()

        choice = ask("  请选择 [1/2/3/skip]", "1").strip().lower()

        if choice in ('m', '2'):
            modified = modify_scores_interactive(run_dir, factors)
            if not modified:
                print("\n  未保存任何评分修改，请手动修改后重新运行步骤6")
                return state

            print("\n  重新计算收敛检验...")
            expert_scores_for_save, convergence_results, overall_pass = recalc_convergence_from_scores(
                score_path, factors, ahp_consistency
            )

            if not overall_pass:
                print("\n  重新检验后仍未通过。")
                if questionary.confirm("  是否跳过步骤6继续后续步骤？", default=False).ask():
                    overall_pass = True
                else:
                    print("\n  请继续修改后重新运行步骤6")
                    return state
        elif choice in ('skip', '3'):
            print("\n  已跳过收敛检验，继续后续步骤")
            overall_pass = True  # Allow to continue
        else:
            print("\n  请手动修改后重新运行步骤6")
            return state

    # Save convergence results
    final_converged = sum(1 for r in convergence_results.values() if r["converged"])

    convergence_data = {
        "run_id": run_id,
        "project_title": project.get("title", "") if isinstance(project, dict) else getattr(project, 'title', ''),
        "threshold": 0.5,
        "total_factors": len(factors),
        "converged_count": final_converged,
        "not_converged_count": len(factors) - final_converged,
        "factor_results": convergence_results,
        "overall_pass": overall_pass,
        "expert_scores_summary": [
            {
                "expert_id": es.get("expert_id"),
                "expert_name": es.get("expert_name"),
                "score_count": len(es.get("scores", [])) if "scores" in es else len(es.get("local_weights", {})),
            }
            for es in expert_scores_for_save
        ],
        "timestamp": datetime.now().isoformat(),
    }

    if ahp_consistency:
        convergence_data["ahp_consistency"] = ahp_consistency

    save_json(run_dir / "convergence_check.json", convergence_data)

    # Generate summary markdown
    summary_text = generate_convergence_summary(convergence_results)
    summary_path = run_dir / "convergence_summary.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f"  [已保存] {summary_path}")

    state["convergence_result"] = convergence_data
    state["run_status"] = "step6_completed"

    print()
    print("=" * 60)
    print("  步骤 6 完成！")
    print("=" * 60)
    print(f"\n  已生成文件：")
    print(f"    - convergence_check.json (收敛检验详情)")
    print(f"    - convergence_summary.md (收敛检验汇总)")

    return state
