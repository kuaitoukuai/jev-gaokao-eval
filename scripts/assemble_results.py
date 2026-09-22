# -*- coding: utf-8 -*-
"""
装配: 把外部跑分结果按「题干文本」对齐到本项目的真题库索引

用途: 当结果是在别处(如临时脚本)跑出来的, 用本脚本把它标准化为本项目格式,
      确保 idx / subject / year / index / score 等字段与 data/items.json 严格对应。

用法:
    python assemble_results.py --items data/items.json \
        --raw ../../nanojev/full_results.json --out results/jev_results.json
"""
import argparse, json, math, os, re, sys


def fix_excel_escape(s: str) -> str:
    """
    两侧统一归一化 —— 上游数据把 LaTeX `\\bar` 的 `\\b` 误存为退格符 U+0008,
    官方 JSON 保留退格符, Excel 导出则写成 `_x005f_x0008_`。两种形态都还原为 `\\b`。
    """
    BS = chr(92)
    s = str(s or '')
    s = s.replace('_x005f_x0008_', BS + 'b')
    s = s.replace(chr(8), BS + 'b')
    s = s.replace('_x005f_', '_')
    return re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), s)


def norm(s):
    return re.sub(r'\s+', '', fix_excel_escape(s))


def entropy(p):
    return -sum(v * math.log(v) for v in p.values() if v > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--items', default='data/items.json')
    ap.add_argument('--raw', required=True)
    ap.add_argument('--out', default='results/jev_results.json')
    args = ap.parse_args()

    with open(args.items, encoding='utf-8') as f:
        items = json.load(f)
    with open(args.raw, encoding='utf-8') as f:
        raw = [r for r in json.load(f) if r.get('ok')]

    # 用归一化题干做索引
    index = {}
    for i, it in enumerate(items):
        index.setdefault(norm(it['stem']), []).append(i)

    out, matched, miss = [None] * len(items), 0, []
    for r in raw:
        key = norm(r.get('stem'))
        cands = index.get(key)
        if not cands:
            miss.append(r.get('row') or r.get('stem', '')[:40])
            continue
        i = cands.pop(0)
        it = items[i]
        probs = {k: float(v) for k, v in (r.get('probs') or r.get('probabilities') or {}).items()}
        out[i] = dict(
            idx=i, ok=True,
            subject=it['subject'], year=it['year'], category=it['category'],
            index=it['index'], score=it['score'], source=it['src'],
            stem=it['stem'], opts=it['opts'], gold=it['gold'],
            pick=r.get('pick'), correct=(r.get('pick') == it['gold']),
            confidence=r.get('conf', r.get('confidence')),
            probabilities=probs,
            p_gold=probs.get(it['gold'], 0),
            entropy=entropy(probs) if probs else None,
            latency=r.get('latency'),
            input_tokens=r.get('in_tokens', r.get('input_tokens')),
            output_tokens=r.get('out_tokens', r.get('output_tokens')),
            model=r.get('model'),
        )
        matched += 1

    results = [x for x in out if x is not None]
    print('项目题库 %d 题, 原始结果 %d 条' % (len(items), len(raw)))
    print('  成功对齐 %d 条' % matched)
    print('  未对齐   %d 条' % len(miss))
    if miss:
        print('    样例: %s' % miss[:5])
    print('  最终结果 %d 条' % len(results))

    ok = [r for r in results if r.get('ok')]
    nr = sum(1 for r in ok if r['correct'])
    print('  准确率 %.2f%% (%d/%d)' % (nr / max(len(ok), 1) * 100, nr, len(ok)))

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print('  已保存: %s' % args.out)


if __name__ == '__main__':
    main()
