# 评测方法论

本文档记录评测的完整口径、实现细节与已知局限，供复核与复现使用。

---

## 1. 数据来源

| 项 | 内容 |
|---|---|
| 仓库 | [OpenLMLab/GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench) |
| 许可 | Apache-2.0 |
| 目录 | `Data/Objective_Questions/` |
| 文件 | 14 个 JSON |
| 题量 | 1781 道客观题 |

原始 JSON 结构：

```json
{
  "keywords": "...",
  "example": [
    {
      "year": "2010",
      "category": "（新课标）",
      "question": "1. （5 分) 已知集合 ...（\\quad$ ）\nA. $(0,2)$\nB. $[0,2]$\n...",
      "answer": ["D"],
      "analysis": "解: ...",
      "index": 0,
      "score": 5
    }
  ]
}
```

数据文件**不随本仓库分发**，由 `scripts/01_download_official_data.py` 在运行时从上游拉取。

### 1.1 上游数据的已知编码缺陷

使用中发现上游数据存在一处 LaTeX 转义缺陷：原 LaTeX `\bar` 里的 `\b` 被某处理流程
当成转义序列，变成了**退格符 U+0008**。同一份文本因此出现两种形态：

| 来源 | 实际内容（`\cdot` 之后） | 字符 |
|---|---|---|
| 官方 JSON | `$z\cdot⟨0x08⟩ar{z}$` | 字面退格符 |
| Excel 导出后 | `$z\cdot_x005f_x0008_ar{z}$` | Excel 把退格符转义成 `_x0008_` |

**影响**：若不归一化，同一道题在两个来源里的题干文本不相等，会导致结果无法对齐。
本项目的处理方式是两个形态统一还原为 `\bar`：

```python
BS = chr(92)                                  # 字面反斜杠, 避免与退格符混淆
s = s.replace('_x005f_x0008_', BS + 'b')      # Excel 转义形态 -> \b
s = s.replace(chr(8), BS + 'b')               # 上游退格符     -> \b
s = s.replace('_x005f_', '_')
s = re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), s)
```

> **编码陷阱提醒**：在 Python 源码里写 `'\\b'` 表示「反斜杠 + b」两个字符，而 `'\b'` 是退格符。
> 两者肉眼几乎无法区分，却会导致完全不同的结果。建议一律用 `chr(92) + 'b'` 显式构造。

实测该缺陷影响 **1 道题**（数学 I 2015 年第 2 题），对整体准确率的影响可忽略，
但作为数据质量记录在此。

---

## 2. 题目类型分类（决定哪些能测）

官方 1781 题按 `answer` 字段的实际形态可分为三类。**这个分类是本评测口径的基础**：

| 类型 | 判定规则 | 题量 | 能否用 choice 单选格式测 |
|---|---|---|---|
| **单选** | `answer` 为单元素且内容为单个字母（如 `["D"]`） | **1503** | ✅ 可以，本评测的测试范围 |
| 题组 | `answer` 多元素（如 `["B","C","A"]`） | 255 | ❌ 一个条目含多个小题，需多答案输出 |
| 多选 | `answer` 单元素但内容多字母（如 `["AC"]`） | 23 | ❌ 需多标签输出，全部集中在物理 |

### 易踩的坑

`["AC"]` 的 `len(answer) == 1`，很容易被误判为单选题。必须同时检查**元素内容的长度**：

```python
a = [str(x).strip().upper() for x in (e.get('answer') or [])]
if len(a) == 1 and len(a[0]) == 1 and a[0] in 'ABCD':
    kind = 'single'      # 真单选
elif len(a) == 1:
    kind = 'multi_one'   # ['AC'] 多选
elif len(a) > 1:
    kind = 'group'       # ['B','C'] 题组
```

题组型（255 题）的具体构成：

| 文件 | 题量 | `answer` 长度 |
|---|---|---|
| English_Reading_Comp | 124 | 3–5 |
| Geography_MCQs | 34 | 2–3 |
| English_Fill_in_Blanks | 30 | 20 |
| Chinese_Modern_Lit | 29 | 3 |
| English_Cloze_Test | 26 | 5 |
| Chinese_Lang_and_Usage | 12 | 3 |

其中 **English_Reading_Comp 的 `question` 字段只包含阅读文章正文，不含小题题干与选项**，
即便拆题也无法还原，属于上游数据的固有缺口。

---

## 3. 选项解析：4 种格式变体

源数据里选项有 4 种写法，**简单正则只能覆盖其中一部分**：

| 变体 | 示例 | 常见场景 |
|---|---|---|
| ① 换行分隔 | `A. xxx` 换行 `B. xxx` | 数学、物理 |
| ② 同行空格分隔 | `A. xxx B. xxx` | 部分数学题 |
| ③ 半角点号 | `A.` `B.` | 通用 |
| ④ **全角点号** | `A．` `B．` | 生物、化学、政治 |

因此正则必须同时支持 `.` `．` `、` 三种标点，且**不要求匹配行首**：

```python
OPT_MARK = re.compile(r'([A-D])\s*[\.．、]\s*')
```

### 为什么还要筛「严格递增序列」

题干正文里经常出现字母 A/B/C/D（如数学题的 $A \cap B$、物理题的选项引用），
只按标点匹配会把这些误判成选项标记。做法是定位所有候选标记后，
**筛出构成 A→B→C→D 严格递增的那一组**：

```python
ti, chosen = 0, []
for s, e, letter in ms:              # ms 按出现位置排序
    if ti < 4 and letter == TARGET[ti]:
        chosen.append((s, e, letter)); ti += 1
if ti != 4:
    return None                      # 解析失败, 交由人工/多模态处理
stem = q[:chosen[0][0]].strip()
opts = {chosen[i][2]: q[chosen[i][1]:(chosen[i+1][0] if i < 3 else len(q))].strip()
        for i in range(4)}
```

---

## 4. 请求体构造

Jev 的 `choice` 题型是**对每个候选选项单独打分再归一化**。
因此选项必须从题干里拆出来，放到 `criteria`，不能留在 `state` 里——
留在题干里模型看到的只是一段说明文字，而不是四个可比较的候选。

```json
{
  "model": "jev-latest",
  "state": "<题干>",
  "questions": {
    "answer": {
      "type": "choice",
      "instructions": "Read the question carefully and choose the single correct option. Mathematical formulas are written in LaTeX ($...$). Return the option that answers the question correctly.",
      "criteria": { "A": "<选项A文本>", "B": "...", "C": "...", "D": "..." }
    }
  }
}
```

---

## 5. 答案泄漏防护

模型评测中最致命的问题是「把答案喂给了模型」。本项目的防护分四层：

| 层级 | 做法 | 结果 |
|---|---|---|
| **L1 结构层** | 请求体的键白名单校验：只允许 `model / state / questions / answer / type / instructions / criteria / A–D` | 全部通过 |
| **L2 内容层** | 精确扫描「答案(是/为/:) X」的答案给出模式（裸词扫描会产生假阳性，见下） | 全部通过 |
| **L3 来源层** | 确认 `state` 只取自 `question` 字段，从不读取 `answer` / `analysis` | 通过 |
| **L4 重组完整性** | 把 `state + A + B + C + D` 按序拼回，与官方原始 `question` **逐字比较** | **逐字一致，无变长/变短** |

### L4 为什么是决定性证据

重组校验从两侧同时卡死：

- 若转换过程**插入了任何额外内容**（比如答案），重组结果会比原文**长**
- 若**丢失了内容**，重组结果会比原文**短**

实测结果：所有试题逐字一致，**没有任何一题变长或变短**。
这就证明了：发给模型的文本 = 官方 `question` 原文，不多一个字、不少一个字，`answer` 字段从未被读取。

### 关于裸词扫描的假阳性

早期版本用裸词扫描（搜 `答案`、`gold`）会命中题干里的自然语言，例如：

- 数学题：「这款软件的激活码为下面数学问题的**答案**: 已知数列…」（题目故事的一部分）
- 英语题：「The discovery of **gold** in Australia…」（gold = 黄金，普通名词）

因此最终口径改为精确匹配「答案后紧跟选项字母」这种明确给出答案的写法，裸词扫描仅作附录定性。

---

## 6. 两个文件的分工

| 文件 | 性质 | 用途 |
|---|---|---|
| `data/requests.json` | **纯请求体**，零答案字段 | **实际发给模型的只有这个** |
| `data/items.json` | 题库记录，含 `gold`（正确答案） | 仅供本地比对与统计 |

两者逐条一一对应。**不要把 `items.json` 直接投喂模型。**

---

## 7. 与 GAOKAO-Bench 官方基线的可比性（重要）

GAOKAO-Bench README 给出的 GPT-4 客观题得分率为 **72.2%**。这个数字**不能**与本项目结果直接相减比较，原因有三：

1. **题集口径不同**
   官方对 **1781 题**（含 255 道题组）评分；本项目只覆盖 **1503 道单选题**。

2. **输出形式不同**
   官方评测的是**生成式模型**，需要模型生成答案再由**规则抽取**，存在格式解析损耗；
   本项目给 Jev 的是**结构化 choice 输入**（题干与四个选项分离），没有格式损耗。

3. **模型范式不同**
   Jev 是非自回归的**逐候选打分决策模型**，不做 token 生成；GPT-4 是生成式模型。
   两者的「答题」机制本质上不同。

**结论**：两个数字只能作量级参考，不构成严格对比。若要严格对比，需要让基线模型也走
「结构化四选一打分」的口径重跑——这超出本项目的范围。

---

## 8. 已知局限

1. **覆盖 1503/1781**：255 道题组 + 23 道多选题不在 choice 单选口径内；另有 6 道单选题因题干/选项为图片无法文本化。
2. **数据污染无法排除**：2010–2022 高考题在互联网上公开流传，无法确认模型训练语料是否覆盖。
   本项目已排除「位置记忆」（打乱选项后准确率与选项内容一致率均在 96%+），
   但**无法排除「题目记忆」**——记住题干的模型打乱选项后照样答得对。
3. **中文场景**：Jev 官方模型卡说明其英文表现优于非英文，本评测为中文场景，结果不能外推到英文任务。
4. **单次快照**：结果对应特定时间点的模型版本（见 `results/summary.json` 的 `model` 字段），
   `jev-latest` 别名会漂移，复现时建议锁定具体版本号。
5. **无温度控制**：Jev API 未暴露采样温度参数，实测同一输入重复调用存在轻微概率抖动
   （置信度越低抖动越大），因此单题结果可能有小幅差异。

---

## 9. 引用

```
@inproceedings{Zhang2023EvaluatingTP,
  title={Evaluating the Performance of Large Language Models on GAOKAO Benchmark},
  author={Xiaotian Zhang and Chunyang Li and Yi Zong and Zhengyu Ying and Liang He and Xipeng Qiu},
  year={2023}
}
```
