# -*- coding: utf-8 -*-
"""
03 · 调用 Jev API 跑分

特性:
  - 断点续跑: 每 N 题增量落盘, 重跑自动跳过已完成题
  - 完整记录: 耗时 / 结果 / 置信度 / 四选项概率 / 熵 / token

用法:
    export JEV_API_KEY=apikey_xxx
    python 03_run_evaluation.py --requests data/requests.json --out results/jev_results.json
"""
import argparse, json, math, os, sys, time, urllib.error, urllib.request

DEFAULT_URL = 'https://api.typesafe.ai/v1/systemone'


def call_jev(body, key, url, retries=4, timeout=180):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    last = None
    for att in range(retries):
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Authorization', 'Bearer ' + key)
        req.add_header('Content-Type', 'application/json')
        # 直连: 绕过本机 http_proxy 环境变量
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            t = time.time()
            with op.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode()), time.time() - t, None
        except urllib.error.HTTPError as e:
            txt = e.read().decode()[:300]
            last = 'HTTP %d: %s' % (e.code, txt)
            if e.code in (429, 529):
                time.sleep(2 ** att * 2); continue
            return None, 0, last
        except Exception as e:
            last = str(e)[:200]
            time.sleep(2 ** att)
    return None, 0, last


def entropy(p):
    return -sum(v * math.log(v) for v in p.values() if v > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--requests', default='data/requests.json')
    ap.add_argument('--items', default='data/items.json')
    ap.add_argument('--out', default='results/jev_results.json')
    ap.add_argument('--url', default=os.environ.get('JEV_BASE_URL', DEFAULT_URL))
    ap.add_argument('--save-every', type=int, default=25)
    ap.add_argument('--sleep', type=float, default=0.08)
    args = ap.parse_args()

    key = os.environ.get('JEV_API_KEY', '')
    if not key:
        sys.exit('请先设置环境变量 JEV_API_KEY')

    with open(args.requests, encoding='utf-8') as f:
        requests = json.load(f)
    with open(args.items, encoding='utf-8') as f:
        items = json.load(f)
    assert len(requests) == len(items)

    done = {}
    if os.path.exists(args.out):
        try:
            with open(args.out, encoding='utf-8') as f:
                for r in json.load(f):
                    done[r['idx']] = r
        except Exception:
            pass

    todo = [i for i in range(len(items)) if i not in done]
    print('=' * 78)
    print('  Jev × GAOKAO-Bench ｜ 总 %d 题, 已完成 %d, 待跑 %d'
          % (len(items), len(done), len(todo)))
    print('=' * 78)

    results = list(done.values())
    t0 = time.time()
    n_new = 0
    for k, idx in enumerate(todo, 1):
        it = items[idx]
        resp, el, err = call_jev(requests[idx], key, args.url)
        if resp is None:
            print('  [%d/%d] #%d 失败: %s' % (k, len(todo), idx, err))
            results.append(dict(idx=idx, ok=False, error=err))
            continue
        a = resp['answers']['answer']
        p = a.get('probabilities') or {}
        u = resp.get('usage') or {}
        results.append(dict(
            idx=idx, ok=True,
            subject=it['subject'], year=it['year'], category=it['category'],
            index=it['index'], score=it['score'], source=it['src'],
            stem=it['stem'], opts=it['opts'], gold=it['gold'],
            pick=a.get('choice'), correct=(a.get('choice') == it['gold']),
            confidence=a.get('confidence'), probabilities=p,
            p_gold=p.get(it['gold'], 0), entropy=entropy(p),
            latency=el, input_tokens=u.get('input_tokens'),
            output_tokens=u.get('output_tokens'), model=resp.get('model'),
        ))
        n_new += 1
        if n_new % args.save_every == 0:
            os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
            with open(args.out, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=1)
            el_all = time.time() - t0
            eta = el_all / n_new * (len(todo) - n_new)
            print('  已跑 %d/%d  已用 %.0fs  预计剩余 %.0fs' % (n_new, len(todo), el_all, eta))
        time.sleep(args.sleep)

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    ok = [r for r in results if r.get('ok')]
    nr = sum(1 for r in ok if r['correct'])
    print()
    print('  完成: 成功 %d / %d, 答对 %d (%.1f%%)'
          % (len(ok), len(results), nr, nr / max(len(ok), 1) * 100))
    print('  本次新增 %d 题, 总耗时 %.0f 秒' % (n_new, time.time() - t0))
    print('  已保存: %s' % args.out)


if __name__ == '__main__':
    main()
