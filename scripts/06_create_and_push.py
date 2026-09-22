# -*- coding: utf-8 -*-
"""
06 · 创建 GitHub 仓库并推送

认证方式:
  - 创建仓库: 需要 PAT (GitHub API)
  - 推送代码: 优先 SSH (已在 ~/.ssh/id_rsa 配置), 失败回退 HTTPS+PAT

用法:
    export GITHUB_TOKEN=ghp_xxx
    python 06_create_and_push.py --repo jev-gaokao-eval --desc "..." [--dry-run]
"""
import argparse, json, os, subprocess, sys, urllib.error, urllib.request

OWNER = os.environ.get('GITHUB_OWNER', 'kuaitoukuai')


def api(path, token, method='GET', body=None):
    url = 'https://api.github.com' + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'token ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'gaokao-bench-jev')
    if body:
        req.add_header('Content-Type', 'application/json')
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, timeout=60) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, 'HTTP %d: %s' % (e.code, e.read().decode()[:300])


def run(cmd, cwd=None, check=True):
    print('  $ %s' % ' '.join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8')
    if r.stdout.strip():
        print('    ' + r.stdout.strip()[:400].replace('\n', '\n    '))
    if r.stderr.strip():
        print('    [stderr] ' + r.stderr.strip()[:300].replace('\n', '\n    '))
    if check and r.returncode != 0:
        raise RuntimeError('命令失败 (exit=%d): %s' % (r.returncode, ' '.join(cmd)))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--desc', default='')
    ap.add_argument('--root', default='.')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--skip-create', action='store_true')
    args = ap.parse_args()

    token = os.environ.get('GITHUB_TOKEN', '')
    root = os.path.abspath(args.root)
    print('=' * 78)
    print('  发布到 GitHub: %s/%s' % (OWNER, args.repo))
    print('  本地目录: %s' % root)
    print('=' * 78)

    # ---------- 1. 创建远程仓库 ----------
    if not args.skip_create:
        if not token:
            sys.exit('未设置 GITHUB_TOKEN, 无法通过 API 创建仓库')
        print('\n[1/4] 创建远程仓库')
        existing, err = api('/repos/%s/%s' % (OWNER, args.repo), token)
        if existing:
            print('  仓库已存在, 跳过创建: %s' % existing['html_url'])
        else:
            if args.dry_run:
                print('  [dry-run] 将创建 public 仓库 %s' % args.repo)
            else:
                d, err = api('/user/repos', token, 'POST', {
                    'name': args.repo, 'description': args.desc,
                    'private': False, 'auto_init': False, 'has_issues': True,
                    'has_wiki': False, 'license_template': 'mit',
                })
                if err:
                    sys.exit('  创建失败: %s' % err)
                print('  已创建: %s' % d['html_url'])
    else:
        print('\n[1/4] 跳过创建 (--skip-create)')

    # ---------- 2. git 初始化与提交 ----------
    print('\n[2/4] 初始化本地仓库并提交')
    if not os.path.isdir(os.path.join(root, '.git')):
        run(['git', 'init', '-b', 'main'], cwd=root)
    run(['git', 'config', 'user.name', OWNER], cwd=root)
    run(['git', 'config', 'user.email', '417139320@qq.com'], cwd=root)
    run(['git', 'add', '-A'], cwd=root)
    st = run(['git', 'status', '--porcelain'], cwd=root)
    if not st.stdout.strip():
        print('  无变更, 跳过提交')
    else:
        n = len([x for x in st.stdout.strip().split('\n') if x.strip()])
        print('  待提交文件: %d 个' % n)
        if not args.dry_run:
            run(['git', 'commit', '-m',
                 'Initial commit: Jev × GAOKAO-Bench objective-question evaluation'], cwd=root)
        else:
            print('  [dry-run] 跳过提交')

    # ---------- 3. 关联远程 ----------
    print('\n[3/4] 关联远程 (SSH 优先)')
    remote = 'git@github.com:%s/%s.git' % (OWNER, args.repo)
    r = run(['git', 'remote'], cwd=root, check=False)
    if 'origin' in r.stdout:
        run(['git', 'remote', 'set-url', 'origin', remote], cwd=root)
    else:
        run(['git', 'remote', 'add', 'origin', remote], cwd=root)
    print('  remote = %s' % remote)

    # ---------- 4. 推送 ----------
    print('\n[4/4] 推送')
    if args.dry_run:
        print('  [dry-run] 跳过推送')
        return
    r = run(['git', 'push', '-u', 'origin', 'main'], cwd=root, check=False)
    if r.returncode != 0:
        print('  SSH 推送失败, 回退 HTTPS + PAT')
        if not token:
            sys.exit('  无 PAT, 无法回退')
        https = 'https://%s:%s@github.com/%s/%s.git' % (OWNER, token, OWNER, args.repo)
        run(['git', 'remote', 'set-url', 'origin', https], cwd=root)
        run(['git', 'push', '-u', 'origin', 'main'], cwd=root)
        # 推送后移除 URL 中的凭据
        run(['git', 'remote', 'set-url', 'origin',
             'https://github.com/%s/%s.git' % (OWNER, args.repo)], cwd=root)
        print('  已移除 URL 中的 PAT')
    print('\n  完成: https://github.com/%s/%s' % (OWNER, args.repo))


if __name__ == '__main__':
    main()
