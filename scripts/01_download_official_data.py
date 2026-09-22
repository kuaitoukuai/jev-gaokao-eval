# -*- coding: utf-8 -*-
"""
01 · 下载 GAOKAO-Bench 官方客观题数据

数据来源: https://github.com/OpenLMLab/GAOKAO-Bench  (Apache-2.0)
         Data/Objective_Questions/*.json  共 14 个文件, 1781 道客观题

用法:
    python 01_download_official_data.py [--out data/official]
"""
import argparse, json, os, sys, time
import urllib.request

REPO = 'OpenLMLab/GAOKAO-Bench'
BRANCH = 'main'
SUBDIR = 'Data/Objective_Questions'
FILES = [
    '2010-2013_English_MCQs.json',
    '2010-2022_Biology_MCQs.json',
    '2010-2022_Chemistry_MCQs.json',
    '2010-2022_Chinese_Lang_and_Usage_MCQs.json',
    '2010-2022_Chinese_Modern_Lit.json',
    '2010-2022_English_Fill_in_Blanks.json',
    '2010-2022_English_Reading_Comp.json',
    '2010-2022_Geography_MCQs.json',
    '2010-2022_History_MCQs.json',
    '2010-2022_Math_II_MCQs.json',
    '2010-2022_Math_I_MCQs.json',
    '2010-2022_Physics_MCQs.json',
    '2010-2022_Political_Science_MCQs.json',
    '2012-2022_English_Cloze_Test.json',
]


def fetch(fn: str, pat: str | None = None) -> tuple[str, str]:
    """先走 jsDelivr CDN, 失败回退 GitHub API (可选带 token)"""
    for host in ('cdn.jsdelivr.net', 'fastly.jsdelivr.net'):
        url = f'https://{host}/gh/{REPO}@{BRANCH}/{SUBDIR}/{fn}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'gaokao-bench-jev'})
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=90) as r:
                return r.read().decode('utf-8', 'replace'), host
        except Exception:
            continue
    # 回退: GitHub API (base64)
    import base64
    for att in range(3):
        try:
            url = f'https://api.github.com/repos/{REPO}/contents/{SUBDIR}/{fn}'
            hdr = {'Accept': 'application/vnd.github+json', 'User-Agent': 'gaokao-bench-jev'}
            if pat:
                hdr['Authorization'] = 'token ' + pat
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=120) as r:
                d = json.loads(r.read().decode())
            return base64.b64decode(d['content']).decode('utf-8', 'replace'), 'api.github.com'
        except Exception:
            if att == 2:
                raise
            time.sleep(2)
    raise RuntimeError('all mirrors failed')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='data/official')
    ap.add_argument('--token', default=os.environ.get('GITHUB_TOKEN', ''), help='可选, 走 API 回退时用')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print('=' * 78)
    print('  下载 GAOKAO-Bench 官方客观题数据')
    print('  仓库: %s (%s) 许可: Apache-2.0' % (REPO, BRANCH))
    print('=' * 78)

    total, ok = 0, 0
    for fn in FILES:
        try:
            txt, src = fetch(fn, args.token or None)
            d = json.loads(txt)
            n = len(d.get('example') or [])
            with open(os.path.join(args.out, fn), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False)
            print('  %-46s %4d 题  (%s)' % (fn, n, src))
            total += n
            ok += 1
        except Exception as e:
            print('  %-46s 失败: %s' % (fn, str(e)[:60]))
        time.sleep(0.3)
    print('-' * 78)
    print('  成功 %d/%d 个文件, 共 %d 道客观题' % (ok, len(FILES), total))
    print('  已保存到: %s' % os.path.abspath(args.out))


if __name__ == '__main__':
    main()
