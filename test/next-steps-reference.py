#!/usr/bin/env python3
"""Reference implementation of index.html's parseNextSteps, kept line-for-line
equivalent to the JS so its output can be diffed against the real page.

Why this exists: the algorithm was designed empirically against the live
Work Packages files of every dashboard project (some items ran to 4,483
characters), and the tuning constants below are the result of that fitting,
not arbitrary. If you change parseNextSteps in index.html, mirror it here and
re-run to see exactly which project cards change.

    python3 test/next-steps-reference.py            # print current output
    python3 test/next-steps-reference.py --check    # diff against the snapshot

Requires `gh` authenticated against the zowen22 org.
"""
import base64, re, subprocess, sys, pathlib

REPOS = ['1.-Autonomous-UAVs', '6.-Curriculum-Tool', '7.-Golf-Shot-Dispersion-Tool',
         '8.-Magic-Band', '9.-High-Ground-Coffee-Club', '3.-Better-Golf-League-Tracker',
         'X.-Claude-Project-Dashboard']
WP_PATH = '1. Project Management/3. Work Packages.md'
SNAPSHOT = pathlib.Path(__file__).parent / 'expected-next-steps.txt'

BUDGET, CAP, MIN, MIN_COLON = 95, 90, 12, 18
DEAD = re.compile(r'\b(complete|completed|done|skipped|paused|deferred'
                  r'|on hold|abandoned|dropped|archived)\b', re.I)
ALIVE = re.compile(r'\bin progress\b', re.I)


def fetch(repo):
    p = subprocess.run(['gh', 'api', f'repos/zowen22/{repo}/contents/{WP_PATH}',
                        '--jq', '.content'], capture_output=True, text=True)
    return base64.b64decode(p.stdout).decode('utf-8', 'replace') if p.returncode == 0 else None


def heading_verdict(heading):
    m = re.search(r'\*\(([\s\S]*)$', heading) or re.search(r'\(([^()]*)\)\s*$', heading)
    if not m:
        return None  # no marker of its own -- inherit from the parent heading
    if ALIVE.search(m.group(1)):
        return False
    if DEAD.search(m.group(1)):
        return True
    return None


def tidy(s):
    while s.count('(') > s.count(')'):
        s = s[:s.rfind('(')]
    return re.sub(r'[\s,;:—–-]+$', '', s)


def step_headline(body):
    m = re.match(r'^((?:@[\w/]+[\s/]*)+?)-\s*([\s\S]*)$', body)
    pre = m.group(1).strip() + ' - ' if m else ''
    rest = re.sub(r'\s+', ' ', re.sub(r'[*`]', '', m.group(2) if m else body)).strip()

    if len(pre) + len(rest) <= BUDGET:
        return pre + rest
    rest = re.sub(r'\s*\([^()]{0,60}\)', '', rest)
    if len(pre) + len(rest) <= BUDGET:
        return pre + tidy(rest)

    cuts = [mm.start() for pat in (' — ', ' – ', ' -- ') for mm in re.finditer(re.escape(pat), rest)]
    cuts += [mm.start() for mm in re.finditer(': ', rest) if mm.start() >= MIN_COLON]
    for pos in sorted(cuts):
        if pos < MIN:
            continue
        cut = tidy(rest[:pos])
        if len(cut) >= MIN:
            return pre + cut
    hard = rest[:CAP]
    sp = hard.rfind(' ')
    return pre + tidy(hard[:sp] if sp > 0 else hard) + ' …'


def next_steps(text, max_n=5):
    live, stack = [], []  # stack: [{'level': int, 'dead': bool}, ...], shallowest first
    for line in text.split('\n'):
        hm = re.match(r'^(#{2,4})\s+(.*)$', line)
        if hm:
            level = len(hm.group(1))
            while stack and stack[-1]['level'] >= level:
                stack.pop()
            verdict = heading_verdict(hm.group(2).strip())
            parent_dead = stack[-1]['dead'] if stack else False
            stack.append({'level': level, 'dead': parent_dead if verdict is None else verdict})
        elif line.startswith('- [ ] ') and not (stack and stack[-1]['dead']):
            live.append(line[6:])
    seen, out = set(), []
    for body in reversed(live):
        if len(out) == max_n:
            break
        h = step_headline(body)
        if h.lower() in seen:
            continue
        seen.add(h.lower())
        out.append(h)
    return list(reversed(out))


def render():
    lines = []
    for repo in REPOS:
        text = fetch(repo)
        lines.append(f'### {repo}')
        if text is None:
            lines.append('  (unreachable — private repo or missing Work Packages file)')
            continue
        for step in next_steps(text):
            lines.append(f'  [{len(step):3d}] {step}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    out = render()
    if '--check' in sys.argv:
        want = SNAPSHOT.read_text() if SNAPSHOT.exists() else ''
        if out == want:
            print('OK — output matches snapshot')
        else:
            print('DRIFT — output differs from snapshot.\n')
            import difflib
            sys.stdout.writelines(difflib.unified_diff(
                want.splitlines(True), out.splitlines(True),
                fromfile='expected', tofile='actual'))
            sys.exit(1)
    else:
        print(out, end='')
