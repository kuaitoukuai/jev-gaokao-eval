# -*- coding: utf-8 -*-
"""
02 · 把 GAOKAO-Bench 客观题转成 Jev systemone 请求体

核心难点 —— 选项格式在源数据里有 4 种写法:
    ① 换行分隔      A. xxx \n B. xxx \n ...
    ② 同行空格分隔  A. xxx B. xxx
    ③ 半角点号      A. / B. / C. / D.
    ④ 全角点号      A． / B．(生物、化学题常见)
所以正则必须同时支持 . ． 、 三种标点, 且不要求行首;
再用「A→B→C→D 严格递增」筛出真正的选项标记, 规避题干正文里的假标记。

分类口径 (官方 1781 题):
    - 单选 (答案单字母 A/B/C/D)      1503 题   <-- 可用 choice 单选格式测
    - 题组 (answer 多元素, 如完形填空) 255 题   <-- 一次问多个小题, 不适合单选格式
    - 多选 (answer 单元素但多字母 'AC') 23 题   <-- 物理多选题

用法:
    python 02_convert_to_jev_format.py --data data/official --out data
输出:
    data/items.json      题库记录 (含正确答案, 仅供本地比对)
    data/requests.json   纯请求体 (零答案字段, 用于实际调用)
    data/parse_report.txt
"""
import argparse, json, os, re, sys, collections

TARGET = ['A', 'B', 'C', 'D']
OPT_MARK = re.compile(r'([A-D])\s*[\.．、]\s*')
INSTRUCTIONS = ('Read the question carefully and choose the single correct option. '
                'Mathematical formulas are written in LaTeX ($...$). '
                'Return the option that answers the question correctly.')


def parse_question(q: str):
    """切分题干与四个选项。返回 (stem, {A..D}) 或 None"""
    if not q:
        return None
    ms = [(m.start(), m.end(), m.group(1)) for m in OPT_MARK.finditer(q)]
    ti, chosen = 0, []
    for s, e, letter in ms:
        if ti < 4 and letter == TARGET[ti]:
            chosen.append((s, e, letter))
            ti += 1
    if ti != 4:
        return None
    stem = q[:chosen[0][0]].strip()
    opts = {}
    for i, (s, e, letter) in enumerate(chosen):
        end = chosen[i + 1][0] if i + 1 < 4 else len(q)
        opts[letter] = q[e:end].strip()
    return stem, opts


def to_request(stem: str, opts: dict) -> dict:
    """转成 Jev systemone 请求体 —— 只含题干与四个选项, 绝不含答案"""
    return {
        "model": "jev-latest",
        "state": stem,
        "questions": {
            "answer": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": {k: opts[k] for k in TARGET},
            }
        },
    }


def fix_excel_escape(s: str) -> str:
    """
    修复 LaTeX 反斜杠被误解析的问题。

    上游数据存在一个编码缺陷: 原 LaTeX `\\bar` 里的 `\\b` 被某处理流程当成转义序列,
    变成了退格符 U+0008。于是同一份文本会出现两种形态:

        官方 JSON 里:      $z\\cdot<0x08>ar{z}$          (字面退格符)
        Excel 导出后:      $z\\cdot_x005f_x0008_ar{z}$   (Excel 把退格符转义成 _x0008_)

    两者都需要归一化回 `\\bar`, 否则同题在两侧的题干文本不相等, 无法对齐。

    注意: `'\\b'` 这种写法在源码里极易与退格符混淆, 这里统一用 chr(92) 显式构造反斜杠。
    """
    BS = chr(92)                                  # 字面反斜杠
    s = s.replace('_x005f_x0008_', BS + 'b')      # Excel 转义形态 -> \b
    s = s.replace(chr(8), BS + 'b')               # 上游退格符     -> \b
    s = s.replace('_x005f_', '_')                 # Excel 保护性下划线转义
    return re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), s)


def classify(answer) -> str:
    a = [str(x).strip().upper() for x in (answer or [])]
    if len(a) == 1 and len(a[0]) == 1 and a[0] in 'ABCD':
        return 'single'
    if len(a) == 1:
        return 'multi_one'      # ['AC']
    if len(a) > 1:
        return 'group'          # ['B','C']
    return 'empty'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data/official')
    ap.add_argument('--out', default='data')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    log = []

    def w(s=''):
        log.append(str(s)); print(s, flush=True)

    w('=' * 78)
    w('  GAOKAO-Bench 客观题 → Jev 请求体')
    w('=' * 78)

    rows = []
    for fn in sorted(os.listdir(args.data)):
        if not fn.endswith('.json'):
            continue
        with open(os.path.join(args.data, fn), encoding='utf-8') as f:
            dd = json.load(f)
        subj = (fn.replace('2010-2022_', '').replace('2010-2013_', '')
                  .replace('2012-2022_', '').replace('_MCQs.json', '').replace('.json', ''))
        for i, e in enumerate(dd.get('example') or []):
            rows.append(dict(src=fn, subject=subj, year=e.get('year'),
                             category=e.get('category'), index=e.get('index', i),
                             score=e.get('score'),
                             question=fix_excel_escape(e.get('question') or ''),
                             answer=e.get('answer') or [],
                             kind=classify(e.get('answer'))))

    w('  载入官方客观题: %d 题' % len(rows))
    for k, v in collections.Counter(r['kind'] for r in rows).most_common():
        w('     %-10s %4d' % (k, v))
    w()

    single = [r for r in rows if r['kind'] == 'single']
    items, requests, skipped = [], [], []
    for r in single:
        p = parse_question(r['question'])
        if p is None:
            skipped.append((r, '选项标记不足4个')); continue
        stem, opts = p
        if any(not opts[k].strip() for k in TARGET):
            skipped.append((r, '存在空选项')); continue
        # 只跳过「选项含图片」—— 候选无法比较;
        # 题干含图片的题仍可测(模型看不到图, 属公平性问题而非格式问题), 会在结果里标注
        if any('![' in opts[k] or 'mathpix' in opts[k] for k in TARGET):
            skipped.append((r, '选项含图片')); continue
        gold = str(r['answer'][0]).strip().upper()
        items.append(dict(subject=r['subject'], year=r['year'], category=r['category'],
                          index=r['index'], score=r['score'], src=r['src'],
                          stem=stem, opts=opts, gold=gold))
        requests.append(to_request(stem, opts))

    w('  单选题 %d → 成功转换 %d 题, 跳过 %d 题' % (len(single), len(items), len(skipped)))
    for r, why in skipped:
        w('     跳过 [%s] %s年 %s: %s' % (r['src'][:26], r['year'], why, r['question'][:60].replace('\n', ' ')))
    w()
    w('  分学科可测题数:')
    for s, v in sorted(collections.Counter(i['subject'] for i in items).items(), key=lambda kv: -kv[1]):
        w('     %-26s %4d' % (s, v))
    w()

    # ---- 完整性自检: state + 四选项 拼回必须等于原题干 (证明零添加零丢失) ----
    w('  [自检] 重组完整性 —— state + 四选项 与官方原始 question 逐字比较')
    src_map = {}
    for r in single:
        src_map[(r['src'], r['index'])] = r['question']

    def norm(s):
        return re.sub(r'\s+', '', str(s)).replace('．', '.').replace('、', '.')

    ok_n, longer, shorter = 0, [], []
    for it in items:
        raw = src_map.get((it['src'], it['index']))
        if raw is None:
            continue
        recon = norm(it['stem'] + 'A.' + it['opts']['A'] + 'B.' + it['opts']['B']
                     + 'C.' + it['opts']['C'] + 'D.' + it['opts']['D'])
        orig = norm(raw)
        if recon == orig:
            ok_n += 1
        elif len(recon) > len(orig):
            longer.append(it)
        else:
            shorter.append(it)
    w('     逐字一致 %d / %d' % (ok_n, len(items)))
    w('     重组变长(疑似插入内容) %d 题' % len(longer))
    w('     重组变短(疑似丢失内容) %d 题' % len(shorter))
    if not longer and not shorter:
        w('     ✅ 零添加、零丢失 —— 答案列从未被写入请求体')
    w()

    with open(os.path.join(args.out, 'items.json'), 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, 'requests.json'), 'w', encoding='utf-8') as f:
        json.dump(requests, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, 'parse_report.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(log))
    w('  已保存: items.json (%d 题, 含答案标注) / requests.json (%d 条纯请求体)'
      % (len(items), len(requests)))


if __name__ == '__main__':
    main()
