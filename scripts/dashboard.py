#!/usr/bin/env python3
"""Public-data-only GitHub README dashboard. Python 3.10+, no dependencies."""
import argparse
import collections
import concurrent.futures
import datetime as dt
from html import escape
from html.parser import HTMLParser
import json
import io
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
API = 'https://api.github.com'
CYAN, VIOLET, TEXT, MUTED = '#39e3ee', '#b69aff', '#eef4ff', '#a5b3c9'


def request(url, token=None, raw=False, missing_ok=False, binary=False):
    headers = {'User-Agent': 'public-profile-mission-control', 'Accept': 'application/vnd.github+json'}
    # Credentials are never forwarded to raw content or HTML endpoints.
    if token and url.startswith(API + '/'):
        headers['Authorization'] = 'Bearer ' + token
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as response:
                body = response.read()
            if binary:
                return body
            body = body.decode('utf-8')
            return body if raw else json.loads(body)
        except urllib.error.HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f'GitHub request failed ({exc.code}); dashboard not replaced') from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError('GitHub connection failed; dashboard not replaced') from None
        time.sleep(2 ** attempt)


def pages(path, token):
    result = []
    for page in range(1, 101):
        separator = '&' if '?' in path else '?'
        batch = request(f'{API}{path}{separator}per_page=100&page={page}', token)
        if not isinstance(batch, list):
            raise ValueError('Expected public repository list')
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise ValueError('Repository pagination exceeded safety limit')


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells, self.counts = {}, {}
        self.tip, self.words = None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('data-date') and a.get('id'):
            self.cells[a['id']] = a['data-date']
        if tag == 'tool-tip' and a.get('for'):
            self.tip, self.words = a['for'], []

    def handle_data(self, data):
        if self.tip:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == 'tool-tip' and self.tip:
            label = ''.join(self.words).strip()
            match = re.match(r'(No|[\d,]+) contributions? on ', label)
            if match:
                self.counts[self.tip] = 0 if match[1] == 'No' else int(match[1].replace(',', ''))
            self.tip = None


def calendar(username, today):
    """Use the PUBLIC GitHub calendar, including anonymous counts the user publishes.

    Deliberately unauthenticated: private repository names and owner-only counts
    cannot enter the generated dataset, even when the workflow has a broad token.
    """
    start = today - dt.timedelta(days=364)
    found = {}
    # The HTML endpoint treats from/to as a calendar-year selector, rather than
    # an arbitrary rolling window. Fetch each touched year and slice explicitly.
    for year in range(start.year, today.year + 1):
        query = urllib.parse.urlencode({'from': f'{year}-01-01', 'to': f'{year}-12-31'})
        parser = CalendarParser()
        parser.feed(request(f'https://github.com/users/{username}/contributions?{query}', raw=True))
        found.update({date: parser.counts[key] for key, date in parser.cells.items() if key in parser.counts})
    dates = [str(start + dt.timedelta(days=i)) for i in range(365)]
    if any(date not in found for date in dates):
        raise ValueError('Public contribution calendar incomplete or markup changed; keeping last successful dashboard')
    return [{'date': date, 'count': found[date]} for date in dates]


def streaks(days):
    longest = run = 0
    for day in days:
        run = run + 1 if day['count'] else 0
        longest = max(longest, run)
    # An unfinished today with zero contributions does not break yesterday's streak.
    tail = days if days[-1]['count'] else days[:-1]
    current = 0
    for day in reversed(tail):
        if not day['count']:
            break
        current += 1
    return current, longest


# Evidence is retained as public repository + file/topic, rather than inferred
# from a language. Each technology is counted at most once per repository.
DEPENDENCIES = {
    'fastapi': ('Frameworks', 'FastAPI'), 'django': ('Frameworks', 'Django'),
    'flask': ('Frameworks', 'Flask'), 'spring-boot': ('Frameworks', 'Spring Boot'),
    'react': ('Frameworks', 'React'), 'next': ('Frameworks', 'Next.js'),
    'vue': ('Frameworks', 'Vue'), 'express': ('Frameworks', 'Express'),
    'svelte': ('Frameworks', 'Svelte'), 'streamlit': ('Frameworks', 'Streamlit'),
    'psycopg': ('Databases', 'PostgreSQL'), 'psycopg2': ('Databases', 'PostgreSQL'),
    'psycopg2-binary': ('Databases', 'PostgreSQL'), 'pg': ('Databases', 'PostgreSQL'),
    'asyncpg': ('Databases', 'PostgreSQL'), 'pymongo': ('Databases', 'MongoDB'),
    'mongoose': ('Databases', 'MongoDB'), 'mongodb': ('Databases', 'MongoDB'),
    'redis': ('Databases', 'Redis'), 'mysql2': ('Databases', 'MySQL'),
    'mysql-connector-python': ('Databases', 'MySQL'),
    'better-sqlite3': ('Databases', 'SQLite'), 'sqlite3': ('Databases', 'SQLite'),
    'boto3': ('Infrastructure', 'AWS SDK'), 'aws-sdk': ('Infrastructure', 'AWS SDK'),
    'kubernetes': ('Infrastructure', 'Kubernetes'),
}
MANIFESTS = {'package.json', 'requirements.txt', 'pyproject.toml', 'Pipfile', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'Gemfile', 'Cargo.toml', 'go.mod'}
SKIP_PARTS = {'node_modules', 'vendor', '.venv', 'venv', '.git', 'dist', 'build'}


def detect_dependencies(path, content):
    if Path(path).name == 'package.json':
        obj = json.loads(content)
        deps = set()
        for section in ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'):
            deps.update(obj.get(section, {}))
        if any(name.startswith('@aws-sdk/') for name in deps):
            deps.add('aws-sdk')
        return {DEPENDENCIES[name] for name in deps if name in DEPENDENCIES}
    # Match package identifiers, not arbitrary substring mentions (e.g. flasker).
    return {value for name, value in DEPENDENCIES.items()
            if re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', content, re.I)}


def inspect_repo(repo, token):
    if repo.get('private') is not False or repo.get('visibility', 'public') != 'public':
        raise ValueError('Refusing a non-public repository')
    full = repo['full_name']
    languages = request(f'{API}/repos/{full}/languages', token)
    evidence = collections.defaultdict(set)
    sha = repo['default_branch']
    if repo['size']:
        branch = urllib.parse.quote(sha, safe='')
        tree = request(f'{API}/repos/{full}/git/trees/{branch}?recursive=1', token, missing_ok=True)
        archive_files = None
        if tree is None:
            # Some public Git-data endpoints return 404 while the public source
            # archive is available. Read that same branch without credentials.
            blob = request(f'https://codeload.github.com/{full}/zip/refs/heads/{branch}', binary=True)
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                archive_files = {item.filename.split('/', 1)[1]: archive.read(item)
                                 for item in archive.infolist() if not item.is_dir()}
            tree = {'tree': [{'path': path, 'type': 'blob'} for path in archive_files]}
        if tree.get('truncated'):
            raise ValueError(f'Public tree truncated for {full}; refusing incomplete technology counts')
        paths = [x['path'] for x in tree['tree'] if x['type'] == 'blob'
                 and not (set(x['path'].split('/')) & SKIP_PARTS)]
        for path in paths:
            base = Path(path).name
            if base.startswith('Dockerfile') or base in ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'):
                evidence[('Infrastructure', 'Docker')].add(path)
            if path.startswith('.github/workflows/') and path.endswith(('.yml', '.yaml')):
                evidence[('Infrastructure', 'GitHub Actions')].add(path)
            if path.endswith('.tf'):
                evidence[('Infrastructure', 'Terraform')].add(path)
            if base in MANIFESTS or re.fullmatch(r'requirements[-\w]*\.txt', base):
                url = f'https://raw.githubusercontent.com/{full}/{branch}/{urllib.parse.quote(path)}'
                content = archive_files[path].decode('utf-8') if archive_files is not None else request(url, raw=True)
                for tech in detect_dependencies('requirements.txt' if base.startswith('requirements') else path, content):
                    evidence[tech].add(path)
            # Explicit Kubernetes kind evidence, not just a folder name.
            if path.endswith(('.yml', '.yaml')) and ('k8s/' in path or 'kubernetes/' in path):
                content = archive_files[path].decode('utf-8') if archive_files is not None else request(f'https://raw.githubusercontent.com/{full}/{branch}/{urllib.parse.quote(path)}', raw=True)
                if re.search(r'^kind:\s*(Deployment|Service|StatefulSet|DaemonSet|Ingress|Job)\s*$', content, re.M):
                    evidence[('Infrastructure', 'Kubernetes')].add(path)
    topic_map = dict(DEPENDENCIES)
    topic_map.update({'docker': ('Infrastructure', 'Docker'), 'terraform': ('Infrastructure', 'Terraform'),
                      'postgresql': ('Databases', 'PostgreSQL'), 'nextjs': ('Frameworks', 'Next.js')})
    for topic in repo.get('topics', []):
        if topic in topic_map:
            evidence[topic_map[topic]].add('topic:' + topic)
    return {'name': repo['name'], 'url': repo['html_url'], 'languages': languages,
            'technologies': [{'category': cat, 'name': name, 'evidence': sorted(files)}
                             for (cat, name), files in sorted(evidence.items())]}


def safe_url(value):
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in ('https', 'http', 'mailto'):
        return value
    return None


def collect(config, token):
    username = config['username']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', username):
        raise ValueError('Invalid GitHub username')
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    user = request(f'{API}/users/{username}', token)
    # This endpoint only lists owned PUBLIC repositories, regardless of token scopes.
    repos = pages(f'/users/{username}/repos?type=owner', token)
    repos = [r for r in repos if r.get('private') is False and r['owner']['login'].lower() == username.lower()]
    included = sorted([r for r in repos if (config['include_forks'] or not r['fork'])
                       and (config['include_archived'] or not r['archived'])], key=lambda r: r['name'].lower())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        scans = list(pool.map(lambda r: inspect_repo(r, token), included))
    days = calendar(username, today)
    languages = collections.Counter()
    techs = {}
    for scan in scans:
        languages.update(scan['languages'])
        for tech in scan['technologies']:
            key = (tech['category'], tech['name'])
            techs.setdefault(key, []).append({'repo': scan['name'], 'evidence': tech['evidence']})
    by_name = {r['name'].lower(): r for r in repos}
    scan_map = {r['name']: r for r in scans}
    featured = []
    for item in config['featured'][:4]:
        name = item['repo'].split('/')[-1]
        if name.lower() not in by_name:
            raise ValueError('Featured repository must be an owned public repository: ' + name)
        r = by_name[name.lower()]
        scan = scan_map.get(r['name'])
        if scan is None:
            scan = inspect_repo(r, token)
        stack = [t['name'] for t in scan['technologies'] if t['category'] == 'Frameworks']
        stack = ([r['language']] if r.get('language') else []) + stack
        featured.append({'name': r['name'], 'url': r['html_url'], 'stars': r['stargazers_count'],
                         'description': item.get('description') or r['description'] or 'Explore the repository.',
                         'stack': stack[:4], 'demo': safe_url(item.get('demo') or r.get('homepage'))})
    events = request(f'{API}/users/{username}/events/public?per_page=100', token)
    recent = []
    # Public events endpoint can include public work outside owned repos.
    for event in events:
        if not event.get('public'):
            continue
        kind, payload, full = event['type'], event.get('payload', {}), event['repo']['name']
        if full.lower() == f'{username}/{username}'.lower():
            continue  # Do not advertise automated dashboard refreshes as engineering work.
        if kind == 'ReleaseEvent':
            release = payload['release']
            recent.append({'date': event['created_at'], 'label': f'Release · {full} · {release["tag_name"]}', 'url': release['html_url']})
        elif kind == 'PullRequestEvent':
            pr = payload['pull_request']
            recent.append({'date': event['created_at'], 'label': f'PR {payload["action"]} · {full} #{pr["number"]}',
                           'url': f'https://github.com/{full}/pull/{pr["number"]}'})
    for r in repos:
        if r['name'].lower() != username.lower():
            recent.append({'date': r['pushed_at'] or r['updated_at'], 'label': 'Repository update · ' + r['name'], 'url': r['html_url']})
    recent.sort(key=lambda x: x['date'], reverse=True)
    seen, unique = set(), []
    for event in recent:
        key = (event['url'], event['label'])
        if key not in seen:
            unique.append(event)
            seen.add(key)
    current, longest = streaks(days)
    return {'username': username, 'name': user['name'] or username,
            'synced_at': now.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'created_at': user['created_at'], 'days_on_github': (today - dt.date.fromisoformat(user['created_at'][:10])).days,
            'public_repos': len(repos), 'total_repos': '?', 'private_repos': '?',
            'total_stars': sum(r['stargazers_count'] for r in repos),
            'contributions': days, 'current_streak': current, 'longest_streak': longest,
            'contributions_total': sum(d['count'] for d in days),
            'languages': dict(languages.most_common()), 'included_repos': scans,
            'technologies': [{'category': cat, 'name': name, 'count': len(evidence), 'repositories': evidence}
                             for (cat, name), evidence in sorted(techs.items())],
            'featured': featured, 'recent': unique[:5]}


class SVG:
    def __init__(self, width, title):
        self.w, self.title, self.parts = width, title, []
    def rect(self, x, y, w, h, fill='#101a29', stroke='#243247', radius=8, extra='', title=None):
        end = f'><title>{escape(title)}</title></rect>' if title else '/>'
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" {extra}{end}')
    def text(self, x, y, value, size=14, color=TEXT, weight=400, extra=''):
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" {extra}>{escape(str(value))}</text>')
    def line(self, x1, y1, x2, y2, color='#243247', extra=''):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" {extra}/>')
    def wrapped(self, x, y, value, columns, size=15, color=MUTED, max_lines=None):
        lines = textwrap.wrap(value, width=columns, break_long_words=True) or ['']
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1][:-1] + '…'
        for i, line in enumerate(lines):
            self.text(x, y + i * (size + 8), line, size, color)
        return y + len(lines) * (size + 8)
    def header(self, number, label, note=None):
        self.text(24, 34, f'{number} / {label.upper()}', 14, CYAN, 600)
        if note:
            self.wrapped(24, 59, note, int((self.w-48)/7.2), 12, MUTED)
    def save(self, path, height):
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{height}" viewBox="0 0 {self.w} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(self.title)}</title><desc id="desc">Generated from public GitHub data. Full values and evidence are in assets/dashboard.json and the README.</desc>
<defs><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M 32 0 L 0 0 0 32" fill="none" stroke="#182336" stroke-width="0.5"/></pattern><linearGradient id="edge"><stop stop-color="{CYAN}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient></defs>
<rect x="0.5" y="0.5" width="{self.w-1}" height="{height-1}" rx="16" fill="#090f19" stroke="#27364c"/>
<rect x="1" y="1" width="{self.w-2}" height="{height-2}" rx="16" fill="url(#grid)"/>
<path d="M24 1 H{self.w-24}" stroke="url(#edge)" stroke-width="2"/>
<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{''.join(self.parts)}</g></svg>'''
        ET.fromstring(svg)
        path.write_text(svg + '\n')


def render_overview(d, c, w):
    s = SVG(w, f'{d["name"]}: GitHub mission control overview')
    mobile = w < 600
    s.text(24, 34, 'ENGINEERING / MISSION CONTROL', 13, CYAN, 600)
    s.rect(w-38, 23, 10, 10, CYAN, CYAN, 5)
    y = s.wrapped(24, 88, d['name'], 20 if mobile else 40, 30 if mobile else 42, TEXT)
    y = s.wrapped(24, y+12, c['headline'], 36 if mobile else 76, 15, TEXT)
    y = s.wrapped(24, y+8, c['focus'], 37 if mobile else 80, 13, VIOLET)
    y += 10
    metrics = [('TOTAL REPOS', '?'), ('PUBLIC REPOS', d['public_repos']), ('PRIVATE REPOS', '?'),
               ('DAYS ON GITHUB', f'{d["days_on_github"]:,}'), ('TOTAL STARS', d['total_stars'])]
    cols = 2 if mobile else 5
    cw = (w - 48 - (cols-1)*10)/cols
    for i, (label, value) in enumerate(metrics):
        x, cy = 24 + (i%cols)*(cw+10), y + (i//cols)*106
        s.rect(x, cy, cw, 94)
        s.text(x+12, cy+25, label, 11, MUTED)
        s.text(x+12, cy+67, value, 34, VIOLET if value == '?' else CYAN, 600)
    y += math.ceil(len(metrics)/cols)*106
    y = s.wrapped(24, y+13, f'Joined {d["created_at"][:10]} · private and total counts masked', 42 if mobile else 90, 12)
    y = s.wrapped(24, y+8, 'Last synced · '+d['synced_at'], 45 if mobile else 90, 12, CYAN)
    return s, y+18


def render_activity(d, c, w):
    mobile = w < 600
    s = SVG(w, '365-day contribution calendar and 30-day daily contributions')
    s.header('01', 'Daily activity', 'Public GitHub contribution calendar · UTC dates')
    y = 96
    stats = [(d['contributions_total'], 'CONTRIBUTIONS / 365D'), (d['current_streak'], 'CURRENT STREAK / DAYS'), (d['longest_streak'], 'LONGEST / 365D')]
    for i,(value,label) in enumerate(stats):
        x = 24 if mobile else 24+i*(w-48)/3
        cy = y+i*72 if mobile else y
        s.text(x, cy, f'{value:,}', 30, CYAN, 600)
        s.text(x, cy+23, label, 11, MUTED)
    y += 185 if mobile else 62
    days = d['contributions']
    start = dt.date.fromisoformat(days[0]['date'])
    offset = (start.weekday()+1)%7
    total_cols = math.ceil((offset+365)/7)
    chunks = [(0, 27),(27,total_cols)] if mobile else [(0,total_cols)]
    max_count = max(x['count'] for x in days)
    colors = ['#172437', '#185365', '#187f91', '#23afbd', CYAN]
    for lo, hi in chunks:
        cell = 11 if mobile else 12
        step = 13 if mobile else 14
        left = 44
        last_month = None
        for i,day in enumerate(days):
            date = dt.date.fromisoformat(day['date'])
            col, row = divmod(offset+i,7)
            if not lo <= col < hi:
                continue
            x, cy = left+(col-lo)*step, y+28+row*step
            if date.day <= 7 and date.month != last_month:
                s.text(x, y+14, date.strftime('%b'), 10, MUTED)
                last_month = date.month
            level = 0 if not day['count'] else max(1,min(4,math.ceil(day['count']/max(1,max_count)*4)))
            today = i == 364
            s.rect(x, cy, cell, cell, colors[level], VIOLET if today else colors[level], 2,
                   f'stroke-width="{2 if today else 0}"',
                   title=f'{day["date"]}: {day["count"]} contributions'+(' · today' if today else ''))
        for row,label in [(1,'M'),(3,'W'),(5,'F')]:
            s.text(24,y+37+row*step,label,10,MUTED)
        y += 137
    y = s.wrapped(24, y+4, f'{days[0]["date"]} → {days[-1]["date"]}', 45 if mobile else 90, 12, MUTED)
    s.text(24,y+6,'0',11,MUTED)
    for i,color in enumerate(colors): s.rect(42+i*18,y-5,12,12,color,color,2)
    s.text(139,y+6,str(max_count)+' max/day',11,MUTED)
    s.text(w-145,y+6,'□ TODAY',11,VIOLET)
    y += 48
    s.text(24,y,'DAILY CONTRIBUTIONS / LAST 30 DAYS',13,CYAN,600)
    y += 28
    thirty = days[-30:]
    peak = max(1,max(day['count'] for day in thirty))
    left, right, h = 43, w-24, 110
    for value in sorted(set([0, math.ceil(peak/2), peak])):
        cy = y+h-value/peak*h
        s.line(left,cy,right,cy)
        s.text(24,cy+4,value,10,MUTED)
    step = (right-left)/30
    for i,day in enumerate(thirty):
        x, bh = left+i*step+2, day['count']/peak*h
        s.rect(x, y+h-bh, max(2,step-4), max(1,bh), VIOLET if i == 29 else CYAN, 'none', 2,
               title=f'{day["date"]}: {day["count"]} contributions')
        if not mobile and day['count']:
            s.text(x+(step-4)/2,y+h-bh-7,day['count'],10,TEXT,extra='text-anchor="middle"')
        if i in (0,7,14,21,29):
            s.text(x,y+h+20,day['date'][5:],10,MUTED,extra='text-anchor="end"' if i == 29 else '')
    y += h+54
    y = s.wrapped(24,y,f'Today {days[-1]["date"]}: {days[-1]["count"]} · 30-day total: {sum(x["count"] for x in thirty):,}',42 if mobile else 90,12,TEXT)
    y = s.wrapped(24,y+5,'Streak continues through yesterday if today is still empty. Calendar may include anonymous private contributions you publish.',43 if mobile else 96,11)
    return s,y+16


def render_languages(d,c,w):
    s = SVG(w,'Language usage across included owned public repositories')
    s.header('02','Language telemetry','Aggregated bytes · owned public repositories')
    y, total = 95, sum(d['languages'].values())
    for i,(name,value) in enumerate(d['languages'].items()):
        color = [CYAN,VIOLET,'#68b7ff','#f1b771','#79ddaf'][i%5]
        s.text(24,y,name,15,TEXT,600)
        percent = '<0.1' if value/total*100 < 0.1 else f'{value/total*100:.1f}'
        s.text(w-24,y,f'{percent}% · {value:,} B',12,MUTED,extra='text-anchor="end"')
        s.rect(24,y+14,w-48,7,'#172437','none',3)
        s.rect(24,y+14,max(1,(w-48)*value/total),7,color,'none',3)
        y += 57
    if not total:
        y=s.wrapped(24,y,'No language bytes reported by GitHub.',40,14)
    y=s.wrapped(24,y+2,f'{len(d["included_repos"])} repos included · forks {"on" if c["include_forks"] else "off"} · archived {"on" if c["include_archived"] else "off"}',43 if w<600 else 90,12)
    return s,y+16


def render_technologies(d,c,w):
    s=SVG(w,'Frameworks, databases and infrastructure with public evidence')
    s.header('03','Technology signals','Public file and topic evidence · repository counts')
    y=96
    for cat in ('Frameworks','Databases','Infrastructure'):
        s.text(24,y,cat.upper(),13,VIOLET,600)
        y+=30
        techs=sorted([x for x in d['technologies'] if x['category']==cat],key=lambda x:(-x['count'],x['name']))
        for tech in techs:
            s.text(24,y,tech['name'],15,TEXT)
            s.text(w-24,y,f'{tech["count"]} repo'+('s' if tech['count']!=1 else ''),13,CYAN,extra='text-anchor="end"')
            y+=30
        if not techs:
            s.text(24,y,'No public evidence detected',13,MUTED)
            y+=30
        s.line(24,y-10,w-24,y-10)
        y+=24
    y=s.wrapped(24,y,'Evidence and included repositories: assets/dashboard.json',43 if w<600 else 90,12)
    return s,y+12


def render_projects(d,c,w):
    s=SVG(w,'Featured projects: manually selected public repositories')
    s.header('04','Selected work','A selection of my public repositories')
    y=83
    cols=1 if w<600 else 2
    cw=(w-48-(cols-1)*16)/cols
    row_heights=[]
    for row in range(math.ceil(len(d['featured'])/cols)):
        cards=[]
        for i,p in enumerate(d['featured'][row*cols:(row+1)*cols]):
            x=24+i*(cw+16)
            top=y
            # Draw the background before the card text, after measuring wrapped lines.
            height=230
            s.rect(x,top,cw,height)
            s.text(x+16,top+30,f'0{row*cols+i+1} / PUBLIC REPOSITORY',11,VIOLET)
            s.wrapped(x+16,top+63,p['name'],int((cw-32)/11),18,TEXT,max_lines=2)
            s.wrapped(x+16,top+112,p['description'],int((cw-32)/8.4),14,MUTED,max_lines=3)
            s.wrapped(x+16,top+186,' / '.join(p['stack']) or 'Stack not reported',int((cw-32)/7.2),12,CYAN,max_lines=1)
            s.text(x+16,top+211,f'{p["stars"]} stars · REPO'+(' + DEMO' if p['demo'] else ''),12,MUTED)
            cards.append(height)
        y+=max(cards)+16
    if not d['featured']:
        y=s.wrapped(24,y,'Select up to four public repos in dashboard.config.json.',42,14)
    return s,y+8


def render_recent(d,c,w):
    s=SVG(w,'Latest public updates and last successful sync')
    s.header('05','Public activity','Releases / pull requests / repository pushes')
    y=91
    for item in d['recent']:
        s.text(24,y,item['date'][:10],12,VIOLET)
        y=s.wrapped(24,y+26,item['label'],43 if w<600 else 88,14,TEXT)
        s.line(24,y-5,w-24,y-5)
        y+=25
    if not d['recent']:
        y=s.wrapped(24,y,'No public updates available.',42,14)
    y=s.wrapped(24,y,'Last successful sync · '+d['synced_at'],43 if w<600 else 90,12,CYAN)
    y=s.wrapped(24,y+8,'Hourly refresh requested · last good snapshot retained on failure',43 if w<600 else 90,11)
    return s,y+16


def md(value):
    return str(value).replace('\\','\\\\').replace('[','\\[').replace(']','\\]').replace('<','&lt;').replace('>','&gt;').replace('\n',' ')


def readme(d,c):
    def picture(name,alt):
        return f'<picture>\n  <source media="(max-width: 600px)" srcset="assets/{name}-mobile.svg">\n  <img src="assets/{name}.svg" alt="{escape(alt,quote=True)}" width="840">\n</picture>\n'
    lines=['<!-- Generated by scripts/dashboard.py. Edit dashboard.config.json instead. -->','',
           picture('overview',d['name']+' — engineering mission control'),
           ' · '.join(f'[{md(label)}]({safe_url(url)})' for label,url in c['links'].items() if safe_url(url)),
           '\n[Data & setup](docs/SETUP.md)',
           '\n## Daily activity\n',picture('activity','365-day contribution heatmap, 30-day chart and streaks'),
           '\n## Languages & technologies\n',picture('languages','Language byte breakdown across owned public repositories'),
           picture('technologies','Frameworks, databases and infrastructure with repository counts'),
           '\n<details>\n<summary>Repository scope and data sources</summary>\n',
           f'Language and technology totals include **{len(d["included_repos"])} owned public repositories**. Forks: **{c["include_forks"]}**. Archived: **{c["include_archived"]}**. These filters do not change the public overview counts.\n',
           ', '.join(f'[{md(r["name"])}]({r["url"]})' for r in d['included_repos'])+'.\n',
           'Languages use GitHub language bytes, not skill ratings. Technology detection checks dependency manifests, topics and configuration paths; it is evidence of repository usage, not production deployment. Full file-level evidence and every daily count: [public data snapshot](assets/dashboard.json).\n',
           'Contributions come from the **public GitHub contribution calendar**, which may include anonymous private contribution counts if enabled on the profile. No private repository metadata is fetched or published. Total and private repo counts stay masked to prevent subtraction. Stars cover all owned public repos. Dates are UTC; GitHub can delay contribution attribution.\n',
           '</details>\n']
    return '\n'.join(lines)


def generate(d,c,destination):
    (destination/'assets').mkdir(parents=True,exist_ok=True)
    renderers={'overview':render_overview,'activity':render_activity,'languages':render_languages,
               'technologies':render_technologies,'projects':render_projects,'recent':render_recent}
    for name,renderer in renderers.items():
        for width,suffix in [(840,''),(420,'-mobile')]:
            svg,height=renderer(d,c,width)
            svg.save(destination/'assets'/f'{name}{suffix}.svg',height)
    (destination/'assets/dashboard.json').write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
    (destination/'README.md').write_text(readme(d,c))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--render-only',action='store_true',help='Render the existing real-data snapshot without fetching')
    args=ap.parse_args()
    config=json.loads((ROOT/'dashboard.config.json').read_text())
    if len(config['featured'])>4:
        raise ValueError('Select at most four featured repositories')
    for key in ('include_forks','include_archived'):
        if not isinstance(config[key],bool):
            raise ValueError(key+' must be a JSON boolean')
    data=json.loads((ROOT/'assets/dashboard.json').read_text()) if args.render_only else collect(config,os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN'))
    # All fetching, validation and rendering finish in staging before live files
    # change. Actions commits nothing on failure, preserving the remote dashboard.
    with tempfile.TemporaryDirectory(prefix='github-dashboard-') as temp:
        stage=Path(temp)
        generate(data,config,stage)
        for path in (stage/'assets').iterdir():
            target=ROOT/'assets'/path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(path,target)
        shutil.copyfile(stage/'README.md',ROOT/'README.md')
    print('Dashboard generated successfully from public data; synced '+data['synced_at'])


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(f'Refresh failed: {error}',file=sys.stderr)
        sys.exit(1)
