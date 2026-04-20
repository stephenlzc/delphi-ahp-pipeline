# Bug 记录

本文档记录开发过程中遇到的 Bug 及修复情况。

---

## 2026-04-20 本次会话修复/发现的 Bug

### 1. detect_run_progress 返回错误的 part 号导致无限循环

**严重性**：🔴 高
**状态**：✅ 已修复

**问题描述**：
循环遍历所有 Part 时，遇到缺失文件不会立即返回，而是继续检查后面的 Part，最后返回"最后一个缺失的 Part"。导致菜单显示下一步为 Step 6，但 Step 5 Part 1 文件实际不存在，形成无限循环。

**根因**：
`detect_run_progress` 逻辑缺陷 + `_build_result` 的 `next_step = step + 1` 不考虑 part 是否 > 0。

**修复**：
- `detect_run_progress` 循环中遇到第一个缺失 Part 立即 `return _build_result(...)`
- `_build_result` 中 `next_step = step if part > 0 else step + 1`

---

### 2. detect_run_progress 遇到 continue 后跳过 Step 4 Part 3

**严重性**：🔴 高
**状态**：✅ 已修复

**问题描述**：
如果 Step 4 Part 2 完成（对话文件满足条件），循环执行 `continue` 跳出内层循环，直接进入 Step 5，导致 Step 4 Part 3 的 `rounds.json` 从未被检查。

**修复**：
`continue` 语句现在仅在 Step 4 Part 2 特定检查逻辑内生效，Part 3 的检查不受影响。

---

### 3. resume_part 重置导致 Part 2+ 恢复时从 Part 1 重新开始

**严重性**：🔴 高
**状态**：✅ 已修复

**问题描述**：
resume 时传入 `resume_part > 1`，但 `state.pop("resume_part", 1)` 未正确保留。

**修复**：
`resume_part` 现在通过 state dict 正确传递和保留。

---

### 4. modify_scores_interactive 返回 None 而非布尔值

**严重性**：🔴 高
**状态**：✅ 已修复

**问题描述**：
函数以裸 `return`（返回 None）结束，调用方期望布尔值，导致控制流判断错误。

**修复**：
所有分支现在正确返回布尔值（`True`/`False`）。

---

### 5. generate_sensitivity_summary 函数对已归一化的返回值仍按嵌套结构访问

**严重性**：🟡 中
**状态**：🟡 部分修复（新问题）

**问题描述**：
`run_criteria_sensitivity` 的返回值结构已修复为扁平化（`scenarios` 在顶层），但 `generate_sensitivity_summary` 内部仍使用 `.get("criteria_sensitivity", {}).get("scenarios", [])` 访问，导致取到空列表。

**根因**：
返回值结构变更后，访问路径未同步更新。

**代码位置**：`step7_ahp.py` 第 343 行附近。

**状态**：待修复。

---

### 6. delphi.py 导入不存在的 Transcript/Score 模型

**严重性**：🟡 中
**状态**：✅ 已修复

**问题描述**：
`models.py` 中已正确定义了 `Transcript` 和 `Score` dataclass，导入现已有效。

---

### 7. 局部 import json/re 隐藏模块级导入，语义混乱

**严重性**：🟡 中
**状态**：⚠️ 未修复（低严重性）

**问题描述**：
`checkpoints.py` 中部分函数内有局部 `import json/re`，但实际上并未隐藏模块级导入（checkpoints.py 本身无模块级同名导入）。各函数内的局部导入在各自作用域内使用一致，无实际冲突。

**代码位置**：`checkpoints.py` 第 257、334 行附近。

**状态**：低严重性，可保留。

---

### 8. call_llm_stream 未完全消费 yield 导致返回值不完整

**严重性**：🟡 中
**状态**：⚠️ 潜在缺陷（无实际影响）

**问题描述**：
函数为生成器，`return full_content` 在生成器耗尽后才执行。调用方通过迭代消费 `yield` 来构建 `full_response`，不依赖返回值，因此无实际功能影响。

**代码位置**：`llm.py` 第 97-215 行。

**状态**：低严重性， dead code 但无实际影响。

---

### 9. checkpoints.py 检查函数不存在时仅警告不报错

**严重性**：🟢 低
**状态**：⚠️ 未修复

**问题描述**：
`validate_step_prerequisites` 中若检查函数不存在，只将错误追加到列表而不抛出异常，导致验证通过但实际未做检查。

**代码位置**：`checkpoints.py` 第 378-381 行。

**状态**：待修复。

---

### 10. resume_mode 验证失败时 sys.exit(1) 而非回退

**严重性**：🟢 低
**状态**：⚠️ 未修复（低优先级）

**问题描述**：
`interactive_checkpoint` 验证失败时直接 `sys.exit(1)`，用户无法回退上一步。

**代码位置**：`app.py` 第 748-750 行附近。

**状态**：低优先级，暂未修复。

---

## 历史 Bug（2026-04-19 阶段）

### 13. 确认框编辑/删除选项无效

**严重性**：🔴 高 | **状态**：✅ 已修复

### 14. 文件保存条件判断错误

**严重性**：🔴 高 | **状态**：✅ 已修复

### 15. interview_framework.json 未保存

**严重性**：🔴 高 | **状态**：✅ 已修复

### 16. 提供商编辑模式不完整

**严重性**：🟡 中 | **状态**：✅ 已修复

### 17. 交互式选择器 macOS 不工作

**严重性**：🟡 中 | **状态**：✅ 已修复（改用 questionary）

### 18. 选项编号与显示不一致

**严重性**：🔴 高 | **状态**：✅ 已修复

### 19. step3 专家生成报错 'Project' object has no attribute 'get'

**严重性**：🔴 高 | **状态**：✅ 已修复

### 20. rounds.json 中 scoring_dimensions 不应由人工预设权重

**严重性**：🔴 高 | **状态**：✅ 已修复（2026-04-20）

### 21. step4_rounds.py Part 1 skip block 重复代码导致跳过失效

**严重性**：🔴 高 | **状态**：✅ 已修复（2026-04-20）

### 22. step5_run.py 局部 import questionary 导致 UnboundLocalError

**严重性**：🔴 高 | **状态**：✅ 已修复（2026-04-20）

### 23. 专家数据类型 dict/object 混用导致 AttributeError

**严重性**：🔴 高 | **状态**：✅ 已修复（2026-04-20）

### 24. resume 恢复时 rounds 为 dict 而非 RoundsConfig 对象

**严重性**：🔴 高 | **状态**：✅ 已修复（2026-04-20）

---

## 待修复 Bug 汇总

| # | Bug | 严重性 | 状态 |
|:---:|:---|:---:|:---:|
| 7 | generate_sensitivity_summary 访问路径错误 | 🟡 中 | 🟡 部分修复 |
| 11 | checkpoints.py 检查函数不存在仅警告不报错 | 🟢 低 | ⚠️ 未修复 |
| 12 | resume_mode sys.exit(1) 无法回退 | 🟢 低 | ⚠️ 未修复 |
| 9 | 局部 import json/re 语义混乱 | 🟡 中 | ⚠️ 未修复（低严重性） |
| 10 | call_llm_stream 返回值未使用（dead code） | 🟡 中 | ⚠️ 潜在缺陷（无影响） |

---

## 开发建议

### 避免 JSON 文件损坏

在对 JSON 文件进行字符串替换时，**不要**直接使用 `str.replace()` 替换长度不同的字符串。正确做法：

```python
# ❌ 错误：直接字符串替换
content = open("file.json").read()
content = content.replace(api_key, "sk-••••••")

# ✅ 正确：解析→修改→序列化
data = json.load(open("file.json"))
data["api_key"] = "sk-••••••"
json.dump(data, open("file.json", "w"), indent=2)
```

### 验证 JSON 文件有效性

每次修改 JSON 文件后验证：

```python
import json
data = json.load(open("file.json"))  # 损坏则抛异常
print("Valid JSON ✓")
```
