#!/usr/bin/env python3
"""Fetch live GitHub stats and render animated SVG cards for the profile README.

Renders assets/stats.svg (stats + streak) and assets/langs.svg (top languages).
Data comes from the GitHub GraphQL API. Token is read from GH_TOKEN / GITHUB_TOKEN.
Stats are exact and include private aggregate contributions (needs a token with
repo + read:user scope; the default Actions token only sees public data).
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime

LOGIN = os.environ.get("PROFILE_LOGIN", "Mohammad99Shweiki")
EXCLUDE_REPOS = set()  # exact: no repos excluded
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

# tokyonight palette
C = {
    "bg": "#161a26",
    "border": "#232842",
    "blue": "#7aa2f7",
    "purple": "#bb9af7",
    "orange": "#ff9e64",
    "pink": "#f7768e",
    "cyan": "#7dcfff",
    "green": "#9ece6a",
    "text": "#a9b1d6",
    "bright": "#c0caf5",
    "muted": "#787c99",
    "track": "#222638",
}
LANG_COLOR = {
    "TypeScript": C["blue"],
    "JavaScript": C["orange"],
    "Python": C["cyan"],
    "Java": C["orange"],
    "C++": C["purple"],
    "C": C["muted"],
    "HTML": C["pink"],
    "CSS": C["blue"],
    "Shell": C["green"],
    "Dockerfile": C["cyan"],
    "Go": C["cyan"],
}


def graphql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


QUERY = """
query($login:String!){
  user(login:$login){
    pullRequests{totalCount}
    repositoriesContributedTo(includeUserRepositories:false,
      contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY,PULL_REQUEST_REVIEW]){totalCount}
    contributionsCollection{
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false){
      nodes{
        name stargazerCount
        languages(first:10, orderBy:{field:SIZE,direction:DESC}){
          edges{ size node{ name } }
        }
      }
    }
  }
}
"""


def fetch():
    data = graphql(QUERY, {"login": LOGIN})["user"]
    repos = data["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)

    langs = {}
    for r in repos:
        if r["name"] in EXCLUDE_REPOS:
            continue
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]

    cc = data["contributionsCollection"]
    days = []
    for w in cc["contributionCalendar"]["weeks"]:
        days.extend(w["contributionDays"])
    days.sort(key=lambda d: d["date"])

    # current streak: walk back from the most recent day; today counts as
    # "not yet broken" if it has 0 contributions.
    cur = 0
    today = date.today().isoformat()
    for i in range(len(days) - 1, -1, -1):
        c = days[i]["contributionCount"]
        if c > 0:
            cur += 1
        elif days[i]["date"] == today:
            continue
        else:
            break
    # longest streak
    longest = run = 0
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    return {
        "stars": stars,
        "commits": cc["totalCommitContributions"]
        + cc.get("restrictedContributionsCount", 0),
        "prs": data["pullRequests"]["totalCount"],
        "contrib_to": data["repositoriesContributedTo"]["totalCount"],
        "streak_cur": cur,
        "streak_total": cc["contributionCalendar"]["totalContributions"],
        "streak_longest": longest,
        "langs": langs,
    }


def human(n):
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def render_stats(d):
    rows = [
        ("M2 1 L0 1 M1 0 L1 2", "star", "Total Stars Earned", human(d["stars"])),
        ("commits", "commits", "Commits (last year)", human(d["commits"])),
        ("prs", "prs", "Pull Requests", human(d["prs"])),
        ("contrib", "contrib", "Contributed to", human(d["contrib_to"])),
    ]
    # streak ring geometry
    R = 61
    circ = 2 * 3.14159 * R
    pct = min(d["streak_cur"] / 30.0, 1.0) if d["streak_cur"] else 0.04
    offset = circ * (1 - pct)

    icon = {
        "star": '<path d="M0 -7 L2 -2 L7 -2 L3 1 L4 6 L0 3 L-4 6 L-3 1 L-7 -2 L-2 -2 Z" fill="{0}"/>',
        "commits": '<circle r="3" fill="none" stroke="{0}" stroke-width="2"/><path d="M-7 0 H-3 M3 0 H7" stroke="{0}" stroke-width="2"/>',
        "prs": '<circle cx="-5" cy="-4" r="2.3" fill="none" stroke="{0}" stroke-width="1.8"/><circle cx="-5" cy="4" r="2.3" fill="none" stroke="{0}" stroke-width="1.8"/><circle cx="5" cy="4" r="2.3" fill="none" stroke="{0}" stroke-width="1.8"/><path d="M-5 -2 V2 M-5 2 H5 V2" fill="none" stroke="{0}" stroke-width="1.8"/>',
        "contrib": '<circle r="6.5" fill="none" stroke="{0}" stroke-width="1.8"/><path d="M0 0 L0 -6.5 A6.5 6.5 0 0 1 5 4" fill="none" stroke="{0}" stroke-width="1.8"/>',
    }

    row_svg = ""
    for i, (_, key, label, val) in enumerate(rows):
        y = 86 + i * 34
        delay = f"{i * 0.09:.2f}s"
        row_svg += f"""
    <g class="row" style="animation-delay:{delay}" transform="translate(0 {y})">
      <g transform="translate(22 -4)">{icon[key].format(C["purple"])}</g>
      <text x="46" y="0" class="lbl">{label}</text>
      <text x="430" y="0" class="val" text-anchor="end">{val}</text>
    </g>"""

    return f'''<svg width="840" height="232" viewBox="0 0 840 232" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif">
  <style>
    .lbl{{fill:{C["text"]};font-size:15px}}
    .val{{fill:{C["bright"]};font-size:15px;font-weight:700}}
    .title{{fill:{C["blue"]};font-size:17px;font-weight:700}}
    .meta{{fill:{C["muted"]};font-size:12px}} .metab{{fill:{C["bright"]};font-weight:700}}
    .row{{opacity:1;animation:enter .7s ease}}
    @keyframes enter{{from{{opacity:0}}to{{opacity:1}}}}
    .blink{{animation:blink 1.6s ease-in-out infinite}}
    @keyframes blink{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
    .flame{{transform-origin:center bottom;animation:flick 1.6s ease-in-out infinite}}
    @keyframes flick{{0%,100%{{transform:scale(1) rotate(-3deg)}}50%{{transform:scale(1.16) rotate(3deg)}}}}
    .num{{animation:nglow 1.6s ease-in-out infinite}}
    @keyframes nglow{{0%,100%{{opacity:.82}}50%{{opacity:1}}}}
    .gring{{transform-origin:709px 120px;animation:spin 6s linear infinite}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    .draw{{stroke-dasharray:{circ:.0f};animation:draw 1.4s ease .2s}}
    @keyframes draw{{from{{stroke-dashoffset:{circ:.0f}}}}}
    .shimmer{{animation:sh 3s linear infinite}}
    @keyframes sh{{from{{transform:translateX(-840px)}}to{{transform:translateX(840px)}}}}
  </style>
  <defs>
    <linearGradient id="sg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{C["blue"]}" stop-opacity="0"/>
      <stop offset="0.5" stop-color="{C["blue"]}" stop-opacity="0.7"/>
      <stop offset="1" stop-color="{C["blue"]}" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{C["orange"]}" stop-opacity="0.5"/>
      <stop offset="1" stop-color="{C["orange"]}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="card"><rect x="1" y="1" width="838" height="230" rx="15"/></clipPath>
  </defs>
  <rect x="1" y="1" width="838" height="230" rx="15" fill="{C["bg"]}" stroke="{C["border"]}" stroke-width="1.5"/>
  <g clip-path="url(#card)"><rect class="shimmer" x="0" y="0" width="260" height="232" fill="url(#sg)" opacity="0.5"/></g>

  <circle class="blink" cx="44" cy="46" r="5" fill="{C["blue"]}"/>
  <text x="60" y="51" class="title">GitHub Stats</text>
  {row_svg}

  <line x1="520" y1="40" x2="520" y2="192" stroke="{C["border"]}"/>

  <!-- streak ring -->
  <circle class="gring" cx="709" cy="120" r="74" fill="url(#glow)"/>
  <circle cx="709" cy="120" r="{R}" fill="none" stroke="{C["track"]}" stroke-width="9"/>
  <circle class="draw" cx="709" cy="120" r="{R}" fill="none" stroke="{C["orange"]}" stroke-width="9"
          stroke-linecap="round" stroke-dashoffset="{offset:.1f}" transform="rotate(-90 709 120)"/>
  <g class="flame" transform="translate(709 92)">
    <path d="M0 -12 C6 -6 9 -2 9 4 C9 11 4 15 0 15 C-4 15 -9 11 -9 4 C-9 -1 -5 -3 -3 -7 C-2 -3 0 -3 0 -6 Z" fill="{C["orange"]}"/>
    <path d="M0 -2 C3 1 4 3 4 6 C4 9 2 11 0 11 C-2 11 -4 9 -4 6 C-4 3 -2 2 -1 -1 Z" fill="{C["pink"]}"/>
  </g>
  <text class="num" x="709" y="135" text-anchor="middle" fill="{C["orange"]}" font-size="40" font-weight="800">{d["streak_cur"]}</text>
  <text x="709" y="152" text-anchor="middle" fill="{C["muted"]}" font-size="10" letter-spacing="1.5">DAY STREAK</text>
  <text x="709" y="212" text-anchor="middle" class="meta">Total <tspan class="metab">{d["streak_total"]}</tspan>  ·  Longest <tspan class="metab">{d["streak_longest"]}</tspan></text>
</svg>'''


def render_langs(d):
    items = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in items) or 1
    rows = ""
    y0 = 76
    for i, (name, size) in enumerate(items):
        pct = size / total * 100
        y = y0 + i * 36
        col = LANG_COLOR.get(name, C["blue"])
        w = max(pct / 100 * 560, 0.5)
        delay = f"{i * 0.1:.2f}s"
        rows += f'''
  <text x="34" y="{y + 4}" fill="{C["bright"]}" font-size="14">{name}</text>
  <rect x="170" y="{y - 6}" width="560" height="9" rx="4.5" fill="{C["track"]}"/>
  <g clip-path="url(#b{i})">
    <rect class="bar" style="animation-delay:{delay}" x="170" y="{y - 6}" width="{w:.1f}" height="9" rx="4.5" fill="{col}"/>
    <rect class="shine" style="animation-delay:{delay}" x="0" y="{y - 6}" width="80" height="9" fill="#ffffff" opacity="0.25"/>
  </g>
  <clipPath id="b{i}"><rect x="170" y="{y - 6}" width="{w:.1f}" height="9" rx="4.5"/></clipPath>
  <text x="800" y="{y + 4}" text-anchor="end" fill="{C["muted"]}" font-size="13">{pct:.0f}%</text>'''
    h = y0 + len(items) * 36 + 6
    return f'''<svg width="840" height="{h}" viewBox="0 0 840 {h}" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif">
  <style>
    .bar{{transform-origin:170px 0;animation:grow 1s ease}}
    @keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
    .shine{{transform:translateX(170px);animation:shine 2.2s linear infinite}}
    @keyframes shine{{from{{transform:translateX(120px)}}to{{transform:translateX(760px)}}}}
    .blink{{animation:blink 1.6s ease-in-out infinite}}
    @keyframes blink{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
  </style>
  <rect x="1" y="1" width="838" height="{h - 2}" rx="15" fill="{C["bg"]}" stroke="{C["border"]}" stroke-width="1.5"/>
  <circle class="blink" cx="44" cy="40" r="5" fill="{C["blue"]}"/>
  <text x="60" y="45" fill="{C["blue"]}" font-size="17" font-weight="700">Most Used Languages</text>
  {rows}
</svg>'''


def main():
    if not TOKEN:
        print("ERROR: set GH_TOKEN or GITHUB_TOKEN", file=sys.stderr)
        sys.exit(1)
    d = fetch()
    print("data:", json.dumps(d)[:400])
    with open("assets/stats.svg", "w") as f:
        f.write(render_stats(d))
    with open("assets/langs.svg", "w") as f:
        f.write(render_langs(d))
    print("wrote assets/stats.svg, assets/langs.svg")


if __name__ == "__main__":
    main()
