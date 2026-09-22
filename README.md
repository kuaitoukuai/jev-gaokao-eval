# Jev × GAOKAO-Bench 客观题评测

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Dataset: GAOKAO-Bench](https://img.shields.io/badge/Dataset-GAOKAO--Bench-blue.svg)](https://github.com/OpenLMLab/GAOKAO-Bench)
[![Dataset License: Apache 2.0](https://img.shields.io/badge/Dataset%20License-Apache--2.0-green.svg)](https://github.com/OpenLMLab/GAOKAO-Bench/blob/main/LICENSE)

用 [GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench) 的客观题，评测 [Jev](https://typesafe.ai/)（TypeSafe AI 的 System One 决策模型）在中文高考选择题上的**准确率、置信度校准与响应耗时**。

> **一句话结论**：Jev 在 1497 道可测试的高考单选题上准确率 **90.85%**，平均每题 **0.827 秒**，全部 1497 题总成本约 **$0.0317**；其自报置信度在高分区校准良好，但仍存在少量高置信错误。

---

## 核心结果

| 指标 | 数值 |
|---|---|
| 测试题数 | 1497 |
| 答对 | 1360 |
| **准确率** | **90.85%** |
| 期望校准误差 (ECE) | 0.0710 |
| 平均耗时 | 0.827 秒/题 |
| 最快 / 最慢 | 0.584 / 3.898 秒 |
| 全部耗时 | 1238 秒（约 20.6 分钟） |
| 输入 tokens | 753822 |
| **预估成本** | **$0.03166** |
| 模型版本 | `jev-1.13.0` |

```
准确率  █████████████████████████░░░  90.85%  (1360/1497)
GPT-4*  ████████████████████░░░░░░░░  72.20%  ← GAOKAO-Bench 官方 README 数值
        *口径不同, 不可直接比较, 详见下文「关于 GPT-4 基线」
```

> 📊 更细的多维拆解（按年份/分值/题干长度、混淆矩阵、错误模式、置信度闸门收益）
> 见 **[docs/analysis.md](docs/analysis.md)**。

## 分学科表现

| 学科 | 题数 | 答对 | 准确率 | 平均置信度 | 平均耗时(秒) |
|---|---|---|---|---|---|
| 政治 | 316 | 307 | **97.2%** | 0.924 | 0.781 |
| 历史 | 287 | 261 | **90.9%** | 0.865 | 0.859 |
| 数学 I | 214 | 184 | **86.0%** | 0.765 | 0.898 |
| 数学 II | 217 | 176 | **81.1%** | 0.723 | 0.788 |
| 生物 | 150 | 145 | **96.7%** | 0.928 | 0.758 |
| 化学 | 123 | 109 | **88.6%** | 0.816 | 0.848 |
| 英语 | 105 | 101 | **96.2%** | 0.854 | 0.897 |
| 物理 | 41 | 36 | **87.8%** | 0.817 | 0.760 |
| 语文 | 44 | 41 | **93.2%** | 0.690 | 0.868 |

## 置信度校准

Jev 每次决策都会返回一个概率分布与置信度。下表检验「它自报的置信度」与「实际正确率」是否吻合——这是决策型模型能否用于自动化的关键。

| 置信度区间 | 题数 | 平均置信度 | 实际正确率 | 偏差 |
|---|---|---|---|---|
| [0.00, 0.40) | 109 | 0.272 | 45.0% | +0.177 |
| [0.40, 0.60) | 140 | 0.502 | 70.0% | +0.198 |
| [0.60, 0.70) | 71 | 0.643 | 76.1% | +0.117 |
| [0.70, 0.80) | 88 | 0.746 | 90.9% | +0.163 |
| [0.80, 0.90) | 144 | 0.850 | 95.1% | +0.102 |
| [0.90, 0.95) | 150 | 0.921 | 98.7% | +0.066 |
| [0.95, 1.00) | 795 | 0.984 | 99.9% | +0.015 |

> 偏差 = 实际正确率 − 平均置信度。正值表示模型**低估**自己（偏保守），负值表示**高估**自己。

## 耗时分布

| 统计量 | 数值(秒) |
|---|---|
| 全局平均 | 0.827 |
| 全局最快 | 0.584 |
| 全局最慢 | 3.898 |
| 学科间最快均值 | 0.758 |
| 学科间最慢均值 | 0.898 |
| 吞吐 | 约 1.2 题/秒（串行） |

## 错题分析

共 **137 道错题**（错误率 9.15%），其中 **60 道属于「高置信错误」**——置信度 ≥0.5 却答错。这类错误是自动化场景下最需要防范的。

| 学科 | 年份 | 正确答案 | Jev 答案 | 置信度 | 正确项概率 | 性质 |
|---|---|---|---|---|---|---|
| 化学 | 2016 | D | C | 0.950 | 0.030 | ⚠️ 高置信错误 |
| 数学 I | 2014 | B | D | 0.920 | 0.040 | ⚠️ 高置信错误 |
| 数学 II | 2018 | C | A | 0.910 | 0.050 | ⚠️ 高置信错误 |
| 历史 | 2014 | C | B | 0.890 | 0.050 | ⚠️ 高置信错误 |
| 历史 | 2019 | B | A | 0.880 | 0.080 | ⚠️ 高置信错误 |
| 政治 | 2020 | C | A | 0.870 | 0.070 | ⚠️ 高置信错误 |
| 历史 | 2010 | C | A | 0.860 | 0.060 | ⚠️ 高置信错误 |
| 数学 II | 2019 | D | B | 0.860 | 0.000 | ⚠️ 高置信错误 |
| 数学 II | 2020 | B | D | 0.800 | 0.110 | ⚠️ 高置信错误 |
| 数学 I | 2019 | D | B | 0.800 | 0.000 | ⚠️ 高置信错误 |
| 数学 II | 2013 | A | B | 0.790 | 0.140 | ⚠️ 高置信错误 |
| 数学 II | 2013 | B | A | 0.770 | 0.150 | ⚠️ 高置信错误 |
| 数学 II | 2021 | C | B | 0.750 | 0.180 | ⚠️ 高置信错误 |
| 化学 | 2017 | B | A | 0.740 | 0.180 | ⚠️ 高置信错误 |
| 化学 | 2013 | A | B | 0.730 | 0.140 | ⚠️ 高置信错误 |
| 历史 | 2019 | D | C | 0.730 | 0.200 | ⚠️ 高置信错误 |
| 数学 II | 2014 | D | B | 0.710 | 0.100 | ⚠️ 高置信错误 |
| 数学 II | 2017 | B | D | 0.710 | 0.180 | ⚠️ 高置信错误 |
| 生物 | 2014 | B | A | 0.690 | 0.200 | ⚠️ 高置信错误 |
| 历史 | 2022 | A | D | 0.670 | 0.040 | ⚠️ 高置信错误 |

> 上表仅列出置信度最高的 20 道（共 137 道错题）。完整清单见 [`results/jev_gaokao_results.xlsx`](results/jev_gaokao_results.xlsx) 的「汇总统计」工作表，或 [`results/jev_results.json`](results/jev_results.json)。

## 关于 GPT-4 基线（务必阅读）

GAOKAO-Bench 官方 README 给出 GPT-4 客观题得分率 **72.2%%**。这个数字**不能**与本项目结果直接相减比较：

| 维度 | 官方基线 | 本项目 |
|---|---|---|
| 题集 | 全部 1781 题（含 255 道题组） | 1503 道单选题 |
| 输出形式 | 生成式模型生成答案 + **规则抽取**（有格式解析损耗） | 结构化 choice 输入（无格式损耗） |
| 模型范式 | 生成式 LLM | 非自回归逐候选打分决策模型 |

三者叠加意味着口径完全不同，**两个数字只可作量级参考**。
要严格对比，需让基线模型也走「结构化四选一打分」的口径重跑。

## 快速开始

```bash
# 1. 安装依赖 (仅 Excel 导出需要 openpyxl)
python -m pip install -r requirements.txt

# 2. 下载 GAOKAO-Bench 官方客观题数据
python scripts/01_download_official_data.py --out data/official

# 3. 转成 Jev 请求体 (含答案泄漏自检)
python scripts/02_convert_to_jev_format.py --data data/official --out data

# 4. 跑分 (支持断点续跑)
export JEV_API_KEY=your_key_here
python scripts/03_run_evaluation.py --requests data/requests.json \
       --items data/items.json --out results/jev_results.json

# 5. 分析与导出 Excel
python scripts/04_analyze_and_export.py --results results/jev_results.json \
       --outdir results
```

全流程约 25 分钟（1497 题 × 0.83 秒），成本约 $0.0317。

## 仓库结构

```
jev-gaokao-eval/
├── README.md
├── LICENSE                     MIT (代码)；数据为 Apache-2.0
├── requirements.txt
├── scripts/
│   ├── 01_download_official_data.py   下载官方数据 (14 文件 / 1781 题)
│   ├── 02_convert_to_jev_format.py    格式转换 + 答案泄漏自检
│   ├── 03_run_evaluation.py           调用 Jev API (断点续跑)
│   ├── 04_analyze_and_export.py       统计 + 导出 Excel/Markdown
│   ├── 05_build_readme.py             由 summary.json 生成本文件
│   ├── 06_create_and_push.py          创建 GitHub 仓库并推送
│   └── 07_deep_analysis.py            深度分析 -> docs/analysis.md
├── data/                      运行后生成: items.json / requests.json
│   └── official/              官方原始数据 (不纳入版本控制)
├── results/
│   ├── jev_results.json       逐题原始结果
│   ├── jev_gaokao_results.xlsx  三工作表 Excel
│   ├── summary.json           全部统计量
│   └── analysis_report.md     Markdown 分析报告
└── docs/
    ├── methodology.md         完整方法论与局限说明
    └── analysis.md            深度分析 (多维拆解/混淆矩阵/错误模式/闸门收益)
```

## 数据与口径说明

### 官方 1781 题的构成

| 类型 | 判定 | 题量 | 是否纳入本次测试 |
|---|---|---|---|
| 单选 | `answer` 单元素且内容为单字母 | 1503 | ✅ 是 |
| 题组 | `answer` 多元素（完形填空、阅读理解等） | 255 | ❌ 一次含多个小题 |
| 多选 | `answer` 单元素但内容多字母，如 `["AC"]` | 23 | ❌ 需多标签输出 |

> ⚠️ `["AC"]` 的 `len(answer) == 1`，极易被误判为单选题。判断单选必须同时检查**元素内容长度**。

覆盖情况：官方 1503 道单选题中，6 道因题干或选项为**图片**无法用文本 API 处理，实际测试 **1497 道（99.6%）**。

### 答案泄漏防护

发给模型的请求体**只含题干与四个选项**，不含任何答案字段。已做四层校验，其中**重组完整性校验**是决定性证据：把 `state + A + B + C + D` 拼回后与官方原始 `question` 逐字比较——若插入过内容会变长、若丢失内容会变短，两侧同时卡死。

详见 [docs/methodology.md](docs/methodology.md)。

### 已知局限

1. **数据污染无法排除**：2010–2022 高考题在互联网上公开流传，无法确认模型训练语料是否覆盖。本项目已排除「位置记忆」，但无法排除「题目记忆」。
2. **中文场景**：Jev 官方模型卡说明其英文表现优于非英文，结果不能外推到英文任务。
3. **模型版本会漂移**：`jev-latest` 是别名，复现时建议锁定具体版本号。
4. **无温度控制**：API 未暴露采样参数，同一输入重复调用存在轻微概率抖动（置信度越低抖动越大）。

## 引用

如果本项目对你有帮助，请同时引用数据集原论文：

```bibtex
@inproceedings{Zhang2023EvaluatingTP,
  title={Evaluating the Performance of Large Language Models on GAOKAO Benchmark},
  author={Xiaotian Zhang and Chunyang Li and Yi Zong and Zhengyu Ying and Liang He and Xipeng Qiu},
  year={2023}
}
```

## 许可

- 本项目代码：[MIT](LICENSE)
- 数据集 [GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench)：Apache-2.0（不随本仓库分发）

---

*生成时间：2026-09-22 17:31 ｜ 全部数据来自真实 API 调用，无模拟值。*