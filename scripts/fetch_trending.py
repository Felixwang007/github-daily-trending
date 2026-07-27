#!/usr/bin/env python3
"""
GitHub Trending Scraper
Fetches trending repos from GitHub (no API key needed).
Generates JSON data and a static HTML site.
"""

import urllib.request
import urllib.error
import json
import re
import os
import html
import datetime
import sys
from html.parser import HTMLParser


class TrendingParser(HTMLParser):
    """Minimal parser to extract trending repo data from GitHub's HTML."""
    
    def __init__(self):
        super().__init__()
        self.repos = []
        self.current_repo = None
        self.in_article = False
        self.in_h2 = False
        self.in_desc = False
        self.in_lang = False
        self.in_stars = False
        self.in_today_stars = False
        self.tag_stack = []
        self.current_text = ""
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Detect article tags (GitHub uses <article> for each repo)
        if tag == 'article':
            self.in_article = True
            self.current_repo = {
                'name': '',
                'description': '',
                'language': '',
                'stars': '',
                'forks': '',
                'today_stars': '',
                'url': ''
            }
            return
            
        if not self.in_article:
            return
            
        if tag == 'h2':
            self.in_h2 = True
            self.current_text = ""
            return
            
        if tag == 'p' and not self.in_h2:
            self.in_desc = True
            self.current_text = ""
            return
            
        # Language span
        if tag == 'span' and 'class' in attrs_dict:
            if 'd-inline-block' in attrs_dict.get('class', ''):
                self.in_lang = True
                self.current_text = ""
                return
                
        # Stars link
        if tag == 'a' and self.in_article:
            href = attrs_dict.get('href', '')
            if '/stargazers' in href:
                self.in_stars = True
                return
                
        # Today stars
        if tag == 'span' and 'class' in attrs_dict:
            cls = attrs_dict.get('class', '')
            if 'float-sm-right' in cls or 'd-inline-block' in cls:
                # Check for 'today' text
                pass
                
    def handle_data(self, data):
        if not self.in_article:
            return
            
        if self.in_h2:
            self.current_text += data
            # Extract repo link from h2
            match = re.search(r'/([^/]+)/([^/\s]+)', data)
            if match:
                owner = match.group(1).strip()
                repo = match.group(2).strip()
                self.current_repo['name'] = f"{owner}/{repo}"
                self.current_repo['url'] = f"https://github.com/{owner}/{repo}"
            return
            
        if self.in_desc:
            self.current_text += data
            return
            
        if self.in_lang:
            self.current_text += data
            return
            
    def handle_endtag(self, tag):
        if tag == 'article':
            if self.current_repo and self.current_repo['name']:
                self.repos.append(self.current_repo)
            self.in_article = False
            self.current_repo = None
            return
            
        if not self.in_article:
            return
            
        if tag == 'h2':
            self.in_h2 = False
            return
            
        if tag == 'p' and self.in_desc:
            self.in_desc = False
            self.current_repo['description'] = self.current_text.strip()
            return
            
        if tag == 'span' and self.in_lang:
            self.in_lang = False
            self.current_repo['language'] = self.current_text.strip()
            return
            
    def handle_startendtag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'img' and self.in_article:
            if 'alt' in attrs_dict and 'star' in attrs_dict.get('alt', '').lower():
                pass  # star icon


def fetch_trending(language='', since='weekly'):
    """Fetch trending repos from GitHub."""
    url = 'https://github.com/trending'
    if language:
        url += f'/{language}'
    url += f'?since={since}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_content = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"ERROR fetching {url}: {e}", file=sys.stderr)
        return []
    
    # Fallback: simple regex-based extraction (more reliable than parser for GitHub's HTML)
    repos = []
    
    # Find all repo article blocks
    pattern = r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>'
    articles = re.findall(pattern, html_content, re.DOTALL)
    
    for article_html in articles:
        repo = {}
        
        # h2 contains the repo name and link
        h2_match = re.search(r'<h2[^>]*>.*?<a[^>]*href="/([^/]+)/([^"/]+)"', article_html, re.DOTALL)
        if h2_match:
            owner = h2_match.group(1)
            name = h2_match.group(2).rstrip('/')
            repo['name'] = f"{owner}/{name}"
            repo['url'] = f"https://github.com/{owner}/{name}"
        else:
            continue
        
        # Description
        desc_match = re.search(r'<p[^>]*class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', article_html, re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip()
            desc = re.sub(r'<[^>]+>', '', desc)
            desc = html.unescape(desc)
            repo['description'] = desc
        else:
            repo['description'] = ''
        
        # Language
        lang_match = re.search(r'<span[^>]*itemprop="programmingLanguage"[^>]*>(.*?)</span>', article_html, re.DOTALL)
        if lang_match:
            repo['language'] = lang_match.group(1).strip()
        else:
            repo['language'] = 'Unknown'
        
        # Stars (total)
        stars_match = re.search(r'<a[^>]*href="/[^/]+/[^/"]+/stargazers"[^>]*>\s*<svg[^>]*>.*?</svg>\s*(.*?)\s*</a>', article_html, re.DOTALL)
        if stars_match:
            repo['stars'] = stars_match.group(1).strip()
        else:
            repo['stars'] = '0'
            
        # Forks
        forks_match = re.search(r'<a[^>]*href="/[^/]+/[^/"]+/forks"[^>]*>\s*<svg[^>]*>.*?</svg>\s*(.*?)\s*</a>', article_html, re.DOTALL)
        if forks_match:
            repo['forks'] = forks_match.group(1).strip()
        else:
            repo['forks'] = ''
        
        # Today's stars - strip SVG, keep just the text
        today_match = re.search(r'<span[^>]*class="[^"]*d-inline-block[^"]*float-sm-right[^"]*"[^>]*>\s*(.*?)\s*</span>', article_html, re.DOTALL)
        if today_match:
            raw = today_match.group(1).strip()
            clean = re.sub(r'<[^>]+>', '', raw)
            clean = re.sub(r'\s+', ' ', clean).strip()
            repo['today_stars'] = clean
        else:
            # Fallback: try to find today-stars text directly
            today_match2 = re.search(r'(\d[\d,]*)\s*stars?\s*(?:today|this\s+week)', article_html)
            if today_match2:
                repo['today_stars'] = today_match2.group(0).strip()
            else:
                repo['today_stars'] = ''
        
        repos.append(repo)
    
    return repos


def generate_site_json(all_repos, output_dir, languages=None):
    """Generate JSON data file and static HTML."""
    os.makedirs(output_dir, exist_ok=True)
    
    if languages is None:
        languages = {
            '': 'All Languages',
            'python': 'Python',
            'javascript': 'JavaScript',
            'typescript': 'TypeScript',
            'rust': 'Rust',
            'go': 'Go',
            'java': 'Java',
            'c++': 'C++',
            'ruby': 'Ruby',
            'swift': 'Swift',
            'kotlin': 'Kotlin',
        }
    
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    # Save data as JSON
    data = {
        'updated_at': now,
        'repos': all_repos.get('', []),
        'languages': {}
    }
    
    for lang_key in languages:
        if lang_key != '':
            data['languages'][lang_key] = all_repos.get(lang_key, [])
    
    with open(os.path.join(output_dir, 'trending.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Generate HTML
    html_content = generate_html(all_repos, languages, now)
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Site generated in {output_dir}")
    print(f"   - trending.json ({len(all_repos.get('', []))} repos)")
    print(f"   - index.html")
    
    return len(all_repos.get('', []))


def generate_html(all_repos, languages, updated_at):
    """Generate a beautiful static HTML page."""
    repos = all_repos.get('', [])
    
    def star_count(s):
        s = s.strip().lower().replace(',', '')
        if 'k' in s:
            return int(float(s.replace('k', '')) * 1000)
        try:
            return int(s)
        except:
            return 0
    
    repos_sorted = sorted(repos, key=lambda r: star_count(r.get('stars', '0')), reverse=True)
    
    repo_rows = ''
    for i, repo in enumerate(repos_sorted[:50], 1):
        name = repo.get('name', 'unknown/unknown')
        desc = repo.get('description', 'No description')
        lang = repo.get('language', '')
        stars = repo.get('stars', '0')
        forks = repo.get('forks', '')
        today = repo.get('today_stars', '')
        url = repo.get('url', f'https://github.com/{name}')
        
        today_cleaned = re.sub(r'\s+', ' ', today).strip()
        stars_clean = re.sub(r'\s+', ' ', stars).strip()
        
        lang_color = {
            'Python': '#3572A5',
            'JavaScript': '#F7DF1E',
            'TypeScript': '#3178C6',
            'Rust': '#DEA584',
            'Go': '#00ADD8',
            'Java': '#B07219',
            'C++': '#F34B7D',
            'Ruby': '#701516',
            'Swift': '#F05138',
            'Kotlin': '#A97BFF',
        }.get(lang, '#6e7681')
        
        lang_badge = f'<span class="lang-dot" style="background:{lang_color}"></span><span class="lang">{lang}</span>' if lang else ''
        
        today_num = re.sub(r'[^\d,.]', '', today_cleaned.split()[0]) if today_cleaned else ''
        today_badge = f' <span class="today-stars">⭐ {today_cleaned}</span>' if today_cleaned else ''
        
        repo_rows += f'''
        <tr>
          <td class="rank">{i}</td>
          <td class="repo-cell">
            <a href="{url}" target="_blank" rel="noopener" class="repo-name">{name}</a>
            <div class="repo-desc">{html.escape(desc[:200])}</div>
            <div class="repo-meta">
              {lang_badge}
              <span class="stat"><svg class="icon" viewBox="0 0 16 16" width="14" height="14"><path fill="currentColor" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"></path></svg> {stars_clean}</span>
              {f'<span class="stat"><svg class="icon" viewBox="0 0 16 16" width="14" height="14"><path fill="currentColor" d="M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75v-.878a2.25 2.25 0 111.682 2.117l-2.164.602a3.25 3.25 0 01-2.436 0l-2.164-.602A2.25 2.25 0 115 5.372zm7.25 1.903a.75.75 0 00-.25.586v2.955A2.25 2.25 0 019.75 13h-3.5a2.25 2.25 0 01-2.25-2.25V7.86a.75.75 0 00-.25-.586l-1.388-1.13a.75.75 0 00-.112.103L.818 6.374a.75.75 0 00.416 1.28l4.21.612 1.882 3.815a.75.75 0 001.348 0l1.882-3.815 4.21-.612a.75.75 0 00.416-1.28l-2.446-2.386a.75.75 0 00-.112-.103L12.25 7.275z"></path></svg> {forks}</span>' if forks else ''}
              {today_badge}
            </div>
          </td>
        </tr>'''
    
    today_str = re.sub(r'\s+', ' ', updated_at)
    
    html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitHub Trending Daily - 每日趋势</title>
<meta name="description" content="GitHub Trending 每日自动更新，追踪最热门的开源项目。Zero API, fully automated.">
<style>
:root {{
  --bg: #0d1117;
  --card: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --text-secondary: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --rank-bg: #1f2937;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; }}
.container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}
header {{ padding: 30px 0 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }}
header h1 {{ font-size: 28px; font-weight: 700; }}
header h1 span {{ color: var(--accent); }}
header .subtitle {{ color: var(--text-secondary); font-size: 14px; margin-top: 6px; }}
header .update-badge {{ display: inline-block; background: var(--green); color: #000; font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600; margin-top: 8px; }}
.support-bar {{ background: #21262d; border: 1px solid var(--border); border-radius: 8px; padding: 14px 20px; margin-bottom: 24px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.support-bar .label {{ color: var(--text-secondary); font-size: 13px; }}
.support-bar a {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; text-decoration: none; transition: opacity .2s; }}
.support-bar a:hover {{ opacity: .85; }}
.btn-sponsor {{ background: #bf4b8a; color: #fff; }}
.btn-coffee {{ background: #FF813F; color: #fff; }}
.btn-star {{ background: #238636; color: #fff; }}
table {{ width: 100%; border-collapse: collapse; }}
thead th {{ text-align: left; font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .05em; padding: 8px 12px; border-bottom: 1px solid var(--border); }}
.rank {{ width: 40px; text-align: center; font-size: 14px; font-weight: 700; color: var(--text-secondary); }}
.repo-cell {{ padding: 14px 12px; border-bottom: 1px solid var(--border); }}
.repo-name {{ color: var(--accent); font-size: 15px; font-weight: 600; text-decoration: none; }}
.repo-name:hover {{ text-decoration: underline; }}
.repo-desc {{ color: var(--text-secondary); font-size: 13px; margin: 4px 0 8px; line-height: 1.5; }}
.repo-meta {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 12px; }}
.lang-dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
.lang {{ color: var(--text-secondary); vertical-align: middle; }}
.stat {{ color: var(--text-secondary); display: inline-flex; align-items: center; gap: 3px; }}
.stat .icon {{ vertical-align: middle; }}
.today-stars {{ color: #d29922; font-weight: 600; }}
footer {{ text-align: center; padding: 30px 0; color: var(--text-secondary); font-size: 12px; border-top: 1px solid var(--border); margin-top: 40px; }}
footer a {{ color: var(--accent); text-decoration: none; }}
.loading {{ text-align: center; padding: 60px; color: var(--text-secondary); font-size: 16px; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🔥 GitHub <span>Trending</span> Daily</h1>
    <div class="subtitle">自动采集 · 每日更新 · 零API依赖 · 全GitHub自动化</div>
    <div class="update-badge">🔄 {today_str}</div>
  </header>

  <div class="support-bar">
    <span class="label">💖 支持这个项目：</span>
    <a href="https://github.com/sponsors/Felixwang007" class="btn-sponsor" target="_blank" rel="noopener">❤️ GitHub Sponsors</a>
    <a href="https://ko-fi.com/felixwang007" class="btn-coffee" target="_blank" rel="noopener">☕ Buy me a coffee</a>
    <a href="https://github.com/Felixwang007/github-daily-trending" class="btn-star" target="_blank" rel="noopener">⭐ Star on GitHub</a>
  </div>

  <table>
    <thead>
      <tr>
        <th class="rank">#</th>
        <th>Repository</th>
      </tr>
    </thead>
    <tbody>
      {repo_rows if repo_rows else '<tr><td colspan="2" style="text-align:center;padding:40px;color:var(--text-secondary)">⏳ 等待首次数据采集...</td></tr>'}
    </tbody>
  </table>

  <footer>
    <p>由 GitHub Actions 自动驱动 · 数据来源 <a href="https://github.com/trending" target="_blank">GitHub Trending</a></p>
    <p style="margin-top:4px"><a href="https://github.com/Felixwang007/github-daily-trending">Felixwang007/github-daily-trending</a></p>
  </footer>
</div>
</body>
</html>'''
    
    return html_template


def main():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'site')
    
    languages = {
        '': 'All Languages',
        'python': 'Python',
        'javascript': 'JavaScript',
        'typescript': 'TypeScript',
        'rust': 'Rust',
        'go': 'Go',
    }
    
    all_repos = {}
    
    for lang_key in languages:
        print(f"Fetching trending for {languages[lang_key]}...")
        repos = fetch_trending(lang_key)
        print(f"  → {len(repos)} repos found")
        all_repos[lang_key] = repos
    
    count = generate_site_json(all_repos, output_dir, languages)
    print(f"\n🎉 Done! {count} trending repos collected.")
    
    # Also output as JSON summary for GitHub Actions
    summary = {
        'total_repos': count,
        'updated_at': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
        'languages': {v: len(all_repos.get(k, [])) for k, v in languages.items()},
        'repos': all_repos.get('', [])[:5]  # top 5 for summary
    }
    
    summary_path = os.path.join(output_dir, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # Write GitHub Actions step summary
    github_output = os.environ.get('GITHUB_STEP_SUMMARY')
    if github_output:
        with open(github_output, 'a', encoding='utf-8') as f:
            f.write(f"## 🔥 GitHub Trending Update\n")
            f.write(f"- **{count}** trending repos collected\n")
            f.write(f"- Languages: {', '.join(f'{v}={len(all_repos.get(k, []))}' for k, v in languages.items())}\n")


if __name__ == '__main__':
    main()
