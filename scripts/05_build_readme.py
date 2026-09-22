# -*- coding: utf-8 -*-
"""
05 · 根据 summary.json 生成 README.md

用法:
    python 05_build_readme.py --summary results/summary.json --out README.md
"""
import argparse, json, os, datetime

OFFICIAL_TOTAL = 1781
OFFICIAL_SINGLE = 1503
OFFICIAL_GROUP = 255
OFFICIAL_MULTI = 23
GPT4_OBJ = 72.2      # GAOKAO-Bench README 给出的 GPT-4 客观题得分率
WRONG_SHOW = 20      # README 中错题表展示条数 (完整清单见 results/)

CN = {'Math_I': '数学 I', 'Math_II': '数学 II', 'Biology': '生物', 'Chemistry': '化学',
      'Physics': '物理', 'English': '英语', 'Chinese_Lang_and_Usage': '语文',
      'History': '历史', 'Political_Science': '政治',
      'Chinese_Modern_Lit': '现代文阅读', 'English_Fill_in_Blanks': '英语填空',
      'English_Reading_Comp': '英语阅读', 'Geography': '地理', 'English_Cloze_Test': '英语完形'}


def bar(acc, width=28):
    filled = int(round(acc * width))
    return '█' * filled + '░' * (width - filled)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--summary', default='results/summary.json')
    ap.add_argument('--out', default='README.md')
    args = ap.parse_args()

    with open(args.summary, encoding='utf-8') as f:
        s = json.load(f)

    acc = s['accuracy']
    L = []

    def w(s=''):
        L.append(str(s))

    w('# Jev × GAOKAO-Bench 客观题评测')
    w()
    w('[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)')
    w('[![Dataset: GAOKAO-Bench](https://img.shields.io/badge/Dataset-GAOKAO--Bench-blue.svg)](https://github.com/OpenLMLab/GAOKAO-Bench)')
    w('[![Dataset License: Apache 2.0](https://img.shields.io/badge/Dataset%20License-Apache--2.0-green.svg)](https://github.com/OpenLMLab/GAOKAO-Bench/blob/main/LICENSE)')
    w()
    w('用 [GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench) 的客观题，评测 '
      '[Jev](https://typesafe.ai/)（TypeSafe AI 的 System One 决策模型）在中文高考选择题上的'
      '**准确率、置信度校准与响应耗时**。')
    w()
    w('> **一句话结论**：Jev 在 %d 道可测试的高考单选题上准确率 **%.2f%%**，'
      '平均每题 **%.3f 秒**，全部 %d 题总成本约 **$%.4f**；'
      '其自报置信度在高分区校准良好，但仍存在少量高置信错误。'
      % (s['n_ok'], acc * 100, s['latency_mean'], s['n_ok'], s['cost_usd']))
    w()
    w('---')
    w()
    w('## 核心结果')
    w()
    w('| 指标 | 数值 |')
    w('|---|---|')
    w('| 测试题数 | %d |' % s['n_ok'])
    w('| 答对 | %d |' % s['n_correct'])
    w('| **准确率** | **%.2f%%** |' % (acc * 100))
    w('| 期望校准误差 (ECE) | %.4f |' % s['ece'])
    w('| 平均耗时 | %.3f 秒/题 |' % s['latency_mean'])
    w('| 最快 / 最慢 | %.3f / %.3f 秒 |' % (s['latency_min'], s['latency_max']))
    w('| 全部耗时 | %.0f 秒（约 %.1f 分钟） |' % (s['latency_total'], s['latency_total'] / 60))
    w('| 输入 tokens | %d |' % s['input_tokens'])
    w('| **预估成本** | **$%.5f** |' % s['cost_usd'])
    w('| 模型版本 | `%s` |' % s['model'])
    w()
    w('```')
    w('准确率  %s  %.2f%%  (%d/%d)' % (bar(acc), acc * 100, s['n_correct'], s['n_ok']))
    w('GPT-4*  %s  %.2f%%  ← GAOKAO-Bench 官方 README 数值' % (bar(GPT4_OBJ / 100), GPT4_OBJ))
    w('        *口径不同, 不可直接比较, 详见下文「关于 GPT-4 基线」')
    w('```')
    w()
    w('> 📊 更细的多维拆解（按年份/分值/题干长度、混淆矩阵、错误模式、置信度闸门收益）')
    w('> 见 **[docs/analysis.md](docs/analysis.md)**。')
    w()
    w('## 分学科表现')
    w()
    w('| 学科 | 题数 | 答对 | 准确率 | 平均置信度 | 平均耗时(秒) |')
    w('|---|---|---|---|---|---|')
    for x in s['by_subject']:
        w('| %s | %d | %d | **%.1f%%** | %.3f | %.3f |'
          % (x['subject'], x['n'], x['correct'], x['accuracy'] * 100,
             x['mean_confidence'], x['mean_latency']))
    w()
    w('## 置信度校准')
    w()
    w('Jev 每次决策都会返回一个概率分布与置信度。下表检验「它自报的置信度」与「实际正确率」是否吻合——'
      '这是决策型模型能否用于自动化的关键。')
    w()
    w('| 置信度区间 | 题数 | 平均置信度 | 实际正确率 | 偏差 |')
    w('|---|---|---|---|---|')
    for x in s['calibration']:
        w('| [%.2f, %.2f) | %d | %.3f | %.1f%% | %+.3f |'
          % (x['lo'], x['hi'], x['n'], x['mean_confidence'], x['accuracy'] * 100, x['gap']))
    w()
    w('> 偏差 = 实际正确率 − 平均置信度。正值表示模型**低估**自己（偏保守），负值表示**高估**自己。')
    w()
    w('## 耗时分布')
    w()
    w('| 统计量 | 数值(秒) |')
    w('|---|---|')
    lat = [x['mean_latency'] for x in s['by_subject']]
    w('| 全局平均 | %.3f |' % s['latency_mean'])
    w('| 全局最快 | %.3f |' % s['latency_min'])
    w('| 全局最慢 | %.3f |' % s['latency_max'])
    w('| 学科间最快均值 | %.3f |' % min(lat))
    w('| 学科间最慢均值 | %.3f |' % max(lat))
    w('| 吞吐 | 约 %.1f 题/秒（串行） |' % (1 / s['latency_mean']))
    w()
    w('## 错题分析')
    w()
    w('共 **%d 道错题**（错误率 %.2f%%），其中 **%d 道属于「高置信错误」**——'
      '置信度 ≥0.5 却答错。这类错误是自动化场景下最需要防范的。'
      % (s['n_wrong'], s['n_wrong'] / s['n_ok'] * 100, s['n_overconfident']))
    w()
    w('| 学科 | 年份 | 正确答案 | Jev 答案 | 置信度 | 正确项概率 | 性质 |')
    w('|---|---|---|---|---|---|---|')
    with open(os.path.join(os.path.dirname(args.summary), 'jev_results.json'), encoding='utf-8') as f:
        allr = [r for r in json.load(f) if r.get('ok')]
    wrong_all = sorted([y for y in allr if not y['correct']],
                       key=lambda z: -(z['confidence'] or 0))
    for r in wrong_all[:WRONG_SHOW]:
        over = (r['confidence'] or 0) >= 0.5
        w('| %s | %s | %s | %s | %.3f | %.3f | %s |'
          % (CN.get(r['subject'], r['subject']), r['year'], r['gold'], r['pick'],
             r['confidence'] or 0, r['p_gold'], '⚠️ 高置信错误' if over else '低置信'))
    if len(wrong_all) > WRONG_SHOW:
        w()
        w('> 上表仅列出置信度最高的 %d 道（共 %d 道错题）。完整清单见 '
          '[`results/jev_gaokao_results.xlsx`](results/jev_gaokao_results.xlsx) 的「汇总统计」工作表，'
          '或 [`results/jev_results.json`](results/jev_results.json)。'
          % (WRONG_SHOW, len(wrong_all)))
    w()
    w('## 关于 GPT-4 基线（务必阅读）')
    w()
    w('GAOKAO-Bench 官方 README 给出 GPT-4 客观题得分率 **72.2%%**。这个数字**不能**与本项目结果直接相减比较：')
    w()
    w('| 维度 | 官方基线 | 本项目 |')
    w('|---|---|---|')
    w('| 题集 | 全部 1781 题（含 255 道题组） | 1503 道单选题 |')
    w('| 输出形式 | 生成式模型生成答案 + **规则抽取**（有格式解析损耗） | 结构化 choice 输入（无格式损耗） |')
    w('| 模型范式 | 生成式 LLM | 非自回归逐候选打分决策模型 |')
    w()
    w('三者叠加意味着口径完全不同，**两个数字只可作量级参考**。')
    w('要严格对比，需让基线模型也走「结构化四选一打分」的口径重跑。')
    w()
    w('## 快速开始')
    w()
    w('```bash')
    w('# 1. 安装依赖 (仅 Excel 导出需要 openpyxl)')
    w('python -m pip install -r requirements.txt')
    w()
    w('# 2. 下载 GAOKAO-Bench 官方客观题数据')
    w('python scripts/01_download_official_data.py --out data/official')
    w()
    w('# 3. 转成 Jev 请求体 (含答案泄漏自检)')
    w('python scripts/02_convert_to_jev_format.py --data data/official --out data')
    w()
    w('# 4. 跑分 (支持断点续跑)')
    w('export JEV_API_KEY=your_key_here')
    w('python scripts/03_run_evaluation.py --requests data/requests.json \\')
    w('       --items data/items.json --out results/jev_results.json')
    w()
    w('# 5. 分析与导出 Excel')
    w('python scripts/04_analyze_and_export.py --results results/jev_results.json \\')
    w('       --outdir results')
    w('```')
    w()
    w('全流程约 25 分钟（%d 题 × %.2f 秒），成本约 $%.4f。'
      % (s['n_ok'], s['latency_mean'], s['cost_usd']))
    w()
    w('## 仓库结构')
    w()
    w('```')
    w('jev-gaokao-eval/')
    w('├── README.md')
    w('├── LICENSE                     MIT (代码)；数据为 Apache-2.0')
    w('├── requirements.txt')
    w('├── scripts/')
    w('│   ├── 01_download_official_data.py   下载官方数据 (14 文件 / 1781 题)')
    w('│   ├── 02_convert_to_jev_format.py    格式转换 + 答案泄漏自检')
    w('│   ├── 03_run_evaluation.py           调用 Jev API (断点续跑)')
    w('│   ├── 04_analyze_and_export.py       统计 + 导出 Excel/Markdown')
    w('│   ├── 05_build_readme.py             由 summary.json 生成本文件')
    w('│   ├── 06_create_and_push.py          创建 GitHub 仓库并推送')
    w('│   └── 07_deep_analysis.py            深度分析 -> docs/analysis.md')
    w('├── data/                      运行后生成: items.json / requests.json')
    w('│   └── official/              官方原始数据 (不纳入版本控制)')
    w('├── results/')
    w('│   ├── jev_results.json       逐题原始结果')
    w('│   ├── jev_gaokao_results.xlsx  三工作表 Excel')
    w('│   ├── summary.json           全部统计量')
    w('│   └── analysis_report.md     Markdown 分析报告')
    w('└── docs/')
    w('    ├── methodology.md         完整方法论与局限说明')
    w('    └── analysis.md            深度分析 (多维拆解/混淆矩阵/错误模式/闸门收益)')
    w('```')
    w()
    w('## 数据与口径说明')
    w()
    w('### 官方 1781 题的构成')
    w()
    w('| 类型 | 判定 | 题量 | 是否纳入本次测试 |')
    w('|---|---|---|---|')
    w('| 单选 | `answer` 单元素且内容为单字母 | %d | ✅ 是 |' % OFFICIAL_SINGLE)
    w('| 题组 | `answer` 多元素（完形填空、阅读理解等） | %d | ❌ 一次含多个小题 |' % OFFICIAL_GROUP)
    w('| 多选 | `answer` 单元素但内容多字母，如 `["AC"]` | %d | ❌ 需多标签输出 |' % OFFICIAL_MULTI)
    w()
    w('> ⚠️ `["AC"]` 的 `len(answer) == 1`，极易被误判为单选题。判断单选必须同时检查**元素内容长度**。')
    w()
    w('覆盖情况：官方 %d 道单选题中，6 道因题干或选项为**图片**无法用文本 API 处理，'
      '实际测试 **%d 道（%.1f%%）**。'
      % (OFFICIAL_SINGLE, s['n_ok'], s['n_ok'] / OFFICIAL_SINGLE * 100))
    w()
    w('### 答案泄漏防护')
    w()
    w('发给模型的请求体**只含题干与四个选项**，不含任何答案字段。已做四层校验，'
      '其中**重组完整性校验**是决定性证据：把 `state + A + B + C + D` 拼回后与官方原始 '
      '`question` 逐字比较——若插入过内容会变长、若丢失内容会变短，两侧同时卡死。')
    w()
    w('详见 [docs/methodology.md](docs/methodology.md)。')
    w()
    w('### 已知局限')
    w()
    w('1. **数据污染无法排除**：2010–2022 高考题在互联网上公开流传，无法确认模型训练语料是否覆盖。'
      '本项目已排除「位置记忆」，但无法排除「题目记忆」。')
    w('2. **中文场景**：Jev 官方模型卡说明其英文表现优于非英文，结果不能外推到英文任务。')
    w('3. **模型版本会漂移**：`jev-latest` 是别名，复现时建议锁定具体版本号。')
    w('4. **无温度控制**：API 未暴露采样参数，同一输入重复调用存在轻微概率抖动（置信度越低抖动越大）。')
    w()
    w('## 引用')
    w()
    w('如果本项目对你有帮助，请同时引用数据集原论文：')
    w()
    w('```bibtex')
    w('@inproceedings{Zhang2023EvaluatingTP,')
    w('  title={Evaluating the Performance of Large Language Models on GAOKAO Benchmark},')
    w('  author={Xiaotian Zhang and Chunyang Li and Yi Zong and Zhengyu Ying and Liang He and Xipeng Qiu},')
    w('  year={2023}')
    w('}')
    w('```')
    w()
    w('## 许可')
    w()
    w('- 本项目代码：[MIT](LICENSE)')
    w('- 数据集 [GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench)：Apache-2.0（不随本仓库分发）')
    w()
    w('---')
    w()
    w('*生成时间：%s ｜ 全部数据来自真实 API 调用，无模拟值。*'
      % datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))

    with open(args.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    print('README 已生成: %s (%d 行)' % (args.out, len(L)))


if __name__ == '__main__':
    main()
