# -*- coding: utf-8 -*-
"""
04 · 结果分析 + 导出 Excel

产出:
    results/jev_gaokao_results.xlsx   三个工作表: 逐题明细 / 汇总统计 / 答题口径说明
    results/summary.json              全部统计量 (供报告脚本消费)
    results/analysis_report.md        可直接阅读的 Markdown 分析报告

用法:
    python 04_analyze_and_export.py --results results/jev_results.json
"""
import argparse, collections, json, math, os, statistics as st

CN = {'Math_I': '数学 I', 'Math_II': '数学 II', 'Biology': '生物', 'Chemistry': '化学',
      'Physics': '物理', 'English': '英语', 'Chinese_Lang_and_Usage': '语文',
      'History': '历史', 'Political_Science': '政治'}
ORDER = ['政治', '历史', '数学 I', '数学 II', '生物', '化学', '英语', '物理', '语文']
KEYS = ['A', 'B', 'C', 'D']
BUCKETS = [(0, .4), (.4, .6), (.6, .7), (.7, .8), (.8, .9), (.9, .95), (.95, 1.01)]


def load(path):
    with open(path, encoding='utf-8') as f:
        rows = json.load(f)
    ok = [r for r in rows if r.get('ok')]
    for r in ok:
        r['subject_cn'] = CN.get(r['subject'], r['subject'])
    return rows, ok


def ece(rs):
    total, e = len(rs), 0.0
    for lo, hi in BUCKETS:
        b = [r for r in rs if lo <= (r['confidence'] or 0) < hi]
        if not b:
            continue
        acc = sum(1 for r in b if r['correct']) / len(b)
        mc = st.mean([r['confidence'] or 0 for r in b])
        e += len(b) / total * abs(acc - mc)
    return e


def summarize(rows, ok):
    n, nr = len(ok), sum(1 for r in ok if r['correct'])
    lat = [r['latency'] for r in ok]
    tin = sum(r['input_tokens'] or 0 for r in ok)
    s = dict(
        n_total=len(rows), n_ok=n, n_correct=nr,
        accuracy=nr / max(n, 1), ece=ece(ok),
        latency_mean=st.mean(lat), latency_min=min(lat), latency_max=max(lat),
        latency_total=sum(lat),
        input_tokens=tin, output_tokens=sum(r['output_tokens'] or 0 for r in ok),
        cost_usd=tin / 1e6 * 0.042,
        model=ok[0].get('model') if ok else None,
    )
    # 分学科
    by = collections.defaultdict(list)
    for r in ok:
        by[r['subject_cn']].append(r)
    s['by_subject'] = []
    for k in ORDER:
        rs = by.get(k)
        if not rs:
            continue
        c = sum(1 for r in rs if r['correct'])
        s['by_subject'].append(dict(
            subject=k, n=len(rs), correct=c, accuracy=c / len(rs),
            mean_confidence=st.mean([r['confidence'] or 0 for r in rs]),
            mean_latency=st.mean([r['latency'] for r in rs]),
            mean_score=st.mean([r['score'] or 0 for r in rs]),
        ))
    # 按年份
    byy = collections.defaultdict(list)
    for r in ok:
        try:
            byy[int(r['year'])].append(r)
        except Exception:
            pass
    s['by_year'] = []
    for y in sorted(byy):
        rs = byy[y]
        c = sum(1 for r in rs if r['correct'])
        s['by_year'].append(dict(year=y, n=len(rs), correct=c,
                                 accuracy=c / len(rs),
                                 mean_confidence=st.mean([r['confidence'] or 0 for r in rs])))
    # 置信度分档
    s['calibration'] = []
    for lo, hi in BUCKETS:
        b = [r for r in ok if lo <= (r['confidence'] or 0) < hi]
        if not b:
            continue
        acc = sum(1 for r in b if r['correct']) / len(b)
        mc = st.mean([r['confidence'] or 0 for r in b])
        s['calibration'].append(dict(lo=lo, hi=min(hi, 1.0), n=len(b),
                                     mean_confidence=mc, accuracy=acc, gap=acc - mc))
    # 错题 / 高置信错误
    wrong = [r for r in ok if not r['correct']]
    s['n_wrong'] = len(wrong)
    s['overconfident'] = [r for r in wrong if (r['confidence'] or 0) >= 0.5]
    s['n_overconfident'] = len(s['overconfident'])
    # 混淆矩阵: 正确答案 x 预测
    cm = collections.Counter((r['gold'], r['pick']) for r in ok)
    s['confusion'] = {'%s->%s' % k: v for k, v in cm.most_common()}
    return s


def write_excel(ok, s, path):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    HDR = PatternFill('solid', fgColor='1F4E79')
    HF = Font(color='FFFFFF', bold=True, size=10.5)
    THIN = Side(style='thin', color='BFBFBF')
    BD = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    GREEN = PatternFill('solid', fgColor='C6EFCE')
    RED = PatternFill('solid', fgColor='FFC7CE')
    YEL = PatternFill('solid', fgColor='FFEB9C')
    GREY = PatternFill('solid', fgColor='F2F2F2')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '逐题明细'
    heads = ['序号', '学科', '年份', '卷别', '题号', '分值', '题干',
             '选项A', '选项B', '选项C', '选项D', '正确答案', 'Jev答案', '是否正确',
             '置信度', '正确项概率', '概率A', '概率B', '概率C', '概率D', '熵',
             '耗时(秒)', '输入tokens', '输出tokens', '模型版本', '备注']
    ws.append(heads)
    for c in range(1, len(heads) + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = HDR; cell.font = HF; cell.border = BD
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for i, r in enumerate(sorted(ok, key=lambda x: (x['subject'], x['year'], x['index'])), 1):
        p = r['probabilities'] or {}
        note = ''
        if not r['correct'] and (r['confidence'] or 0) >= 0.5:
            note = '⚠️ 高置信错误'
        elif not r['correct']:
            note = '答错(低置信)'
        elif (r['confidence'] or 0) < 0.5:
            note = '答对但低置信'
        ws.append([i, r['subject_cn'], r['year'], r['category'], r['index'], r['score'], r['stem'],
                   r['opts']['A'], r['opts']['B'], r['opts']['C'], r['opts']['D'],
                   r['gold'], r['pick'], '对' if r['correct'] else '错',
                   r['confidence'], r['p_gold'],
                   p.get('A'), p.get('B'), p.get('C'), p.get('D'), r['entropy'],
                   round(r['latency'], 3), r['input_tokens'], r['output_tokens'],
                   r['model'], note])
        row = ws.max_row
        for c in range(1, len(heads) + 1):
            ws.cell(row=row, column=c).border = BD
        cc = ws.cell(row=row, column=14)
        cc.font = Font(bold=True, color='006100' if r['correct'] else '9C0006')
        cc.fill = GREEN if r['correct'] else RED
        cc.alignment = Alignment(horizontal='center')
        if note.startswith('⚠️'):
            ws.cell(row=row, column=26).fill = YEL
            ws.cell(row=row, column=26).font = Font(bold=True, color='9C6500')
    for i, wd in enumerate([5, 8, 7, 12, 6, 6, 58, 20, 20, 20, 20, 8, 8, 8,
                            9, 10, 8, 8, 8, 8, 7, 9, 10, 10, 12, 14], 1):
        ws.column_dimensions[get_column_letter(i)].width = wd
    ws.freeze_panes = 'G2'
    ws.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(heads)), ws.max_row)

    # ---- 汇总统计 ----
    ws2 = wb.create_sheet('汇总统计')
    r = 1
    ws2.cell(row=r, column=1, value='Jev × GAOKAO-Bench 客观题实测汇总').font = Font(bold=True, size=13, color='1F4E79')
    r += 2
    kpis = [
        ('数据集', 'GAOKAO-Bench 客观题（OpenLMLab, Apache-2.0）'),
        ('测试口径', '全部可转格式的单选题'),
        ('题目总数', s['n_ok']),
        ('答对', s['n_correct']),
        ('准确率', '%.2f%%' % (s['accuracy'] * 100)),
        ('期望校准误差 ECE', round(s['ece'], 4)),
        ('平均耗时(秒)', round(s['latency_mean'], 3)),
        ('最快 / 最慢(秒)', '%.3f / %.3f' % (s['latency_min'], s['latency_max'])),
        ('输入 tokens 合计', s['input_tokens']),
        ('输出 tokens 合计', s['output_tokens']),
        ('预估成本(USD)', '%.5f' % s['cost_usd']),
        ('模型', s['model']),
    ]
    for k, v in kpis:
        ws2.cell(row=r, column=1, value=k).fill = GREY
        ws2.cell(row=r, column=1).border = BD
        c2 = ws2.cell(row=r, column=2, value=v)
        c2.border = BD; c2.font = Font(bold=True)
        r += 1
    r += 1
    ws2.cell(row=r, column=1, value='分学科').font = Font(bold=True, size=11); r += 1
    for j, h in enumerate(['学科', '题数', '答对', '准确率', '平均置信度', '平均耗时(秒)'], 1):
        c2 = ws2.cell(row=r, column=j, value=h)
        c2.fill = HDR; c2.font = HF; c2.border = BD
        c2.alignment = Alignment(horizontal='center')
    r += 1
    for x in s['by_subject']:
        vals = [x['subject'], x['n'], x['correct'], '%.1f%%' % (x['accuracy'] * 100),
                round(x['mean_confidence'], 3), round(x['mean_latency'], 3)]
        for j, v in enumerate(vals, 1):
            c2 = ws2.cell(row=r, column=j, value=v)
            c2.border = BD
            c2.alignment = Alignment(horizontal='left' if j == 1 else 'center')
        if x['correct'] == x['n']:
            for j in range(1, 7):
                ws2.cell(row=r, column=j).fill = GREEN
        r += 1
    r += 1
    ws2.cell(row=r, column=1, value='置信度分档校准').font = Font(bold=True, size=11); r += 1
    for j, h in enumerate(['置信度区间', '题数', '平均置信度', '实际正确率', '偏差'], 1):
        c2 = ws2.cell(row=r, column=j, value=h)
        c2.fill = HDR; c2.font = HF; c2.border = BD
        c2.alignment = Alignment(horizontal='center')
    r += 1
    for x in s['calibration']:
        vals = ['[%.2f, %.2f)' % (x['lo'], x['hi']), x['n'], round(x['mean_confidence'], 3),
                '%.1f%%' % (x['accuracy'] * 100), '%+.3f' % x['gap']]
        for j, v in enumerate(vals, 1):
            c2 = ws2.cell(row=r, column=j, value=v)
            c2.border = BD
            c2.alignment = Alignment(horizontal='left' if j == 1 else 'center')
        if abs(x['gap']) > 0.15:
            ws2.cell(row=r, column=5).fill = YEL
        r += 1
    r += 1
    ws2.cell(row=r, column=1, value='错题清单').font = Font(bold=True, size=11); r += 1
    for j, h in enumerate(['学科', '年份', '正确答案', 'Jev答案', '置信度',
                           '正确项概率', '耗时(秒)', '四选项概率分布'], 1):
        c2 = ws2.cell(row=r, column=j, value=h)
        c2.fill = HDR; c2.font = HF; c2.border = BD
        c2.alignment = Alignment(horizontal='center')
    r += 1
    for x in sorted([y for y in ok if not y['correct']], key=lambda z: -(z['confidence'] or 0)):
        dist = ' '.join('%s %.2f' % (k, (x['probabilities'] or {}).get(k, 0)) for k in KEYS)
        vals = [x['subject_cn'], x['year'], x['gold'], x['pick'], x['confidence'],
                x['p_gold'], round(x['latency'], 3), dist]
        for j, v in enumerate(vals, 1):
            c2 = ws2.cell(row=r, column=j, value=v)
            c2.border = BD
            c2.alignment = Alignment(horizontal='center' if j <= 7 else 'left')
        if (x['confidence'] or 0) >= 0.5:
            ws2.cell(row=r, column=5).fill = YEL
        r += 1
    for i, wd in enumerate([34, 10, 10, 12, 12, 12, 12, 34], 1):
        ws2.column_dimensions[get_column_letter(i)].width = wd

    # ---- 答题口径说明 ----
    ws3 = wb.create_sheet('评测口径说明')
    lines = [
        'GAOKAO-Bench × Jev 评测口径说明', '',
        '【数据来源】',
        '  仓库: github.com/OpenLMLab/GAOKAO-Bench (Apache-2.0)',
        '  目录: Data/Objective_Questions/  共 14 个文件, 1781 道客观题',
        '',
        '【官方 1781 题的构成】',
        '  单选 (答案单字母 A/B/C/D)        1503 题  <- 本题库测试范围',
        '  题组 (answer 多元素, 如完形填空)  255 题  <- 一次含多个小题, 不适合 choice 单选',
        '  多选 (answer 形如 "AC")            23 题  <- 全部在物理, 需多标签输出',
        '',
        '【本次测试范围】',
        '  官方 1503 道单选题, 其中 6 题因题干/选项为图片无法用文本 API 处理,',
        '  实际测试 %d 题。' % s['n_ok'],
        '',
        '【与官方基线的可比性 —— 重要提醒】',
        '  GAOKAO-Bench README 给出的 GPT-4 客观题得分率 72.2%%, 其口径与本次不同:',
        '    - 官方对 1781 题 (含 255 道题组) 评分, 本题库仅覆盖 1503 道单选题',
        '    - 官方对生成式模型用「规则抽取答案」, 存在格式解析损耗;',
        '      本题库对 Jev 用结构化 choice 输入, 无格式损耗',
        '    - Jev 是逐候选打分的决策模型, 不是生成式模型',
        '  因此两个数字不能直接相减比较, 仅可作量级参考。',
        '',
        '【答案泄漏防护】',
        '  请求体只含 state(题干) 与 criteria(四个选项), 不含任何答案字段。',
        '  已做全量重组完整性校验: state + 四选项 拼回后与官方原始 question 逐字一致。',
        '',
        '【成本口径】',
        '  输入 $0.042 / 1M tokens (TypeSafe 官方标价), 仅按 input_tokens 估算。',
    ]
    rr = 1
    for ln in lines:
        ws3.cell(row=rr, column=1, value=ln)
        if ln.startswith('【'):
            ws3.cell(row=rr, column=1).font = Font(bold=True, size=11, color='1F4E79')
        rr += 1
    ws3.column_dimensions['A'].width = 100

    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    wb.save(path)


def write_markdown(ok, s, path):
    L = []

    def w(s=''):
        L.append(str(s))
    w('# Jev × GAOKAO-Bench 客观题实测报告')
    w()
    w('> 数据来源：[OpenLMLab/GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench)（Apache-2.0）')
    w('> 模型：`%s` ｜ endpoint：`POST https://api.typesafe.ai/v1/systemone`' % s['model'])
    w('> 测试范围：官方 %d 道单选题中的 %d 道（6 道因图片无法文本化）' % (s['n_ok'] + 6, s['n_ok']))
    w()
    w('## 一、总体结果')
    w()
    w('| 指标 | 数值 |')
    w('|---|---|')
    w('| 测试题数 | %d |' % s['n_ok'])
    w('| 答对 | %d |' % s['n_correct'])
    w('| **准确率** | **%.2f%%** |' % (s['accuracy'] * 100))
    w('| 期望校准误差 ECE | %.4f |' % s['ece'])
    w('| 平均耗时 | %.3f 秒/题 |' % s['latency_mean'])
    w('| 最快 / 最慢 | %.3f / %.3f 秒 |' % (s['latency_min'], s['latency_max']))
    w('| 输入 tokens | %d |' % s['input_tokens'])
    w('| 预估成本 | $%.5f |' % s['cost_usd'])
    w()
    w('## 二、分学科')
    w()
    w('| 学科 | 题数 | 答对 | 准确率 | 平均置信度 | 平均耗时(秒) |')
    w('|---|---|---|---|---|---|')
    for x in s['by_subject']:
        w('| %s | %d | %d | %.1f%% | %.3f | %.3f |'
          % (x['subject'], x['n'], x['correct'], x['accuracy'] * 100,
             x['mean_confidence'], x['mean_latency']))
    w()
    w('## 三、置信度校准')
    w()
    w('| 置信度区间 | 题数 | 平均置信度 | 实际正确率 | 偏差 |')
    w('|---|---|---|---|---|')
    for x in s['calibration']:
        w('| [%.2f, %.2f) | %d | %.3f | %.1f%% | %+.3f |'
          % (x['lo'], x['hi'], x['n'], x['mean_confidence'], x['accuracy'] * 100, x['gap']))
    w()
    w('## 四、错题')
    w()
    w('共 %d 道错题，其中 **%d 道属于「高置信错误」**（置信度 ≥0.5 仍答错）。'
      % (s['n_wrong'], s['n_overconfident']))
    w()
    w('| 学科 | 年份 | 正确答案 | Jev答案 | 置信度 | 正确项概率 |')
    w('|---|---|---|---|---|---|')
    for x in sorted([y for y in ok if not y['correct']], key=lambda z: -(z['confidence'] or 0)):
        w('| %s | %s | %s | %s | %.3f | %.3f |'
          % (x['subject_cn'], x['year'], x['gold'], x['pick'], x['confidence'] or 0, x['p_gold']))
    w()
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default='results/jev_results.json')
    ap.add_argument('--outdir', default='results')
    args = ap.parse_args()
    rows, ok = load(args.results)
    print('载入 %d 条记录, 有效 %d 条' % (len(rows), len(ok)))
    s = summarize(rows, ok)
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=1, default=str)
    write_excel(ok, s, os.path.join(args.outdir, 'jev_gaokao_results.xlsx'))
    write_markdown(ok, s, os.path.join(args.outdir, 'analysis_report.md'))
    print('  准确率 %.2f%%  (%d/%d)' % (s['accuracy'] * 100, s['n_correct'], s['n_ok']))
    print('  平均耗时 %.3f 秒  ECE %.4f  高置信错误 %d 道'
          % (s['latency_mean'], s['ece'], s['n_overconfident']))
    print('  已导出: summary.json / jev_gaokao_results.xlsx / analysis_report.md')


if __name__ == '__main__':
    main()
