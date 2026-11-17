"""Render the player-profile README panels.

Every panel is a self-contained SVG with its slice of the background photo
baked in, because GitHub strips CSS from README HTML and has no page
background. Run from the repo root:  python scripts/readme.py
Set GITHUB_TOKEN for live stats; without it the last cached stats are used.
"""
import base64
import datetime as dt
import io
import json
import math
import os
import re
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERNAME = "calebluh"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
YEAR = dt.date.today().year

HUD = "assets/hud"
ITEMS_DIR = "assets/items"
STATS_CACHE = "assets/hud/stats.json"
TICKETS = "tickets.json"
CRAFT_STATE = "assets/crafting_state.json"
GUESTBOOK = "assets/guestbook.json"

BG_SRC = "assets/bryce-canyon-apr-2021-03.webp"
# (file, left-eye px, right-eye px) measured on the source images
FACE_A = ("assets/HeroSection1.webp", (466, 307), (544, 309))
FACE_B = ("assets/HeroSection-lacrosse-aligned.webp", (1612, 1042), (1987, 1056))

SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace"
W = 850
GAP = 8

# Virtual canvas: where each panel sits in the 850px column, so the photo
# slices line up from one image to the next.
LAYOUT = {
    "header": (0, 0, 850, 214),
    "showcase": (0, 222, 561, 262),
    "sidebar": (569, 222, 281, 262),
    "activity": (0, 492, 850, 244),
    "portal-vibehash": (0, 744, 420, 150),
    "portal-luhlabs": (430, 744, 420, 150),
    "guestbook": (0, 902, 850, 212),
    "crafting": (0, 1122, 850, 120),
}
CANVAS_H = 1242

PROFILE = {
    "name": "Caleb Luh",
    "tagline": "Schmaleb · Network Administrator @ J.F. Ahern",
    "bio": ["roses are red", "tickets are closed"],
    "building": ("Currently Building", "VibeHash multi-node testnet"),
    "featured_cert": ("SEC+", "CompTIA Security+", "#7F1D1D", "#F59E0B", "#FDE68A"),
    "certs": [
        ("NET+", "#0C4A6E", "#38BDF8", "#E0F2FE"),
        ("SEC+", "#7F1D1D", "#F59E0B", "#FDE68A"),
        ("SECAI+", "#3B0764", "#C084FC", "#F3E8FF"),
    ],
}

# Showcase tiles: (label, caption, border, fill, text)
SHOWCASE = [
    ("VH", "vibehash", "#4B69FF", "#0B1220", "#93C5FD"),
    ("EH", "evohash", "#4B69FF", "#0B1220", "#93C5FD"),
    ("SL", "statlab", "#8847FF", "#150B20", "#C4B5FD"),
    ("PS1", "intune-kit", "#5E9832", "#0B1A10", "#86EFAC"),
    ("LC", "luh-calm", "#B0A040", "#1A1408", "#FDE68A"),
    (".com", "calebluh.com", "#D32CE6", "#1A0B14", "#F0ABFC"),
    ("LLC", "luhlabs", "#4B69FF", "#0B1220", "#93C5FD"),
]

ROCKET_TARGET = 1000  # points to reach Mars in a calendar year


def p(*parts):
    return os.path.join(ROOT, *parts)


# ---------------------------------------------------------------- data

def gh_get(url, raw=False):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-readme-renderer")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp if raw else json.loads(resp.read().decode())


def count_via_link(url):
    """Count list items with per_page=1 by reading the Link header's last page."""
    resp = gh_get(url + ("&" if "?" in url else "?") + "per_page=1", raw=True)
    link = resp.headers.get("Link", "")
    m = re.search(r'[?&]page=(\d+)>; rel="last"', link)
    if m:
        return int(m.group(1))
    return len(json.loads(resp.read().decode()))


def fetch_stats():
    since = f"{YEAR}-01-01"
    user = gh_get(f"https://api.github.com/users/{USERNAME}")
    repos = gh_get(f"https://api.github.com/users/{USERNAME}/repos?sort=pushed&per_page=30")
    repos = [r for r in repos if not r.get("fork") and r["name"].lower() != USERNAME]
    commits_year = gh_get(
        f"https://api.github.com/search/commits?q=author:{USERNAME}+author-date:>={since}"
    )["total_count"]
    prs_year = gh_get(
        f"https://api.github.com/search/issues?q=author:{USERNAME}+type:pr+is:merged+merged:>={since}"
    )["total_count"]
    recent = None
    if repos:
        r = repos[0]
        base = f"https://api.github.com/repos/{r['owner']['login']}/{r['name']}/commits?author={USERNAME}"
        recent = {
            "name": r["name"],
            "pushed": r["pushed_at"][:10],
            "commits_total": count_via_link(base),
            "commits_year": count_via_link(base + f"&since={since}T00:00:00Z"),
        }
    return {
        "year": YEAR,
        "public_repos": user.get("public_repos", 0),
        "commits_year": commits_year,
        "merged_prs_year": prs_year,
        "recent": recent,
        "fetched": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
    }


def load_stats():
    cached = load_json(STATS_CACHE, {})
    try:
        stats = fetch_stats()
    except (urllib.error.URLError, KeyError, TimeoutError, ValueError) as e:
        print(f"GitHub API unavailable ({e}); using cached stats")
        stats = cached or {
            "year": YEAR, "public_repos": 0, "commits_year": 0,
            "merged_prs_year": 0, "recent": None, "fetched": "never",
        }
    save_json(STATS_CACHE, stats)
    return stats


def load_json(path, default):
    try:
        with open(p(path), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(p(path)) or ".", exist_ok=True)
    with open(p(path), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def level_for(stats):
    xp = stats["commits_year"] + 10 * stats["merged_prs_year"] + 20 * stats["public_repos"]
    return 1 + int(math.sqrt(xp / 8)), xp


# ---------------------------------------------------------------- images

_canvas = None


def canvas():
    global _canvas
    if _canvas is None:
        im = Image.open(p(BG_SRC)).convert("RGB")
        s = max(W / im.width, CANVAS_H / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x0 = (im.width - W) // 2
        _canvas = im.crop((x0, 0, x0 + W, CANVAS_H))
    return _canvas


def data_uri(im, fmt="JPEG", quality=72):
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        mime = "image/jpeg"
    else:
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def bg_slice(key):
    x, y, w, h = LAYOUT[key]
    return canvas().crop((x, y, x + w, y + h)), (w, h)


def aligned_face(spec, size=320, eye_y=0.5, eye_dist=0.26):
    """Similarity-transform a portrait so both eyes land on fixed points."""
    path, e1, e2 = spec
    im = Image.open(p(path)).convert("RGBA")
    t1 = (size * (0.5 - eye_dist / 2), size * eye_y)
    span = size * eye_dist
    a = (e2[0] - e1[0]) / span
    b = (e2[1] - e1[1]) / span
    c = e1[0] - a * t1[0] + b * t1[1]
    f = e1[1] - b * t1[0] - a * t1[1]
    return im.transform((size, size), Image.AFFINE, (a, -b, c, b, a, f), resample=Image.BICUBIC)


def avatar_layers(size=320):
    """Two aligned faces composited on the canyon behind the avatar frame."""
    x, y, _, _ = LAYOUT["header"]
    ax, ay, aw = 27, 27, 160  # avatar box inside the header (px at 850 scale)
    back = canvas().crop((x + ax, y + ay, x + ax + aw, y + ay + aw)).resize((size, size), Image.LANCZOS)
    out = []
    for spec in (FACE_A, FACE_B):
        layer = back.copy().convert("RGBA")
        layer.alpha_composite(aligned_face(spec, size))
        out.append(data_uri(layer, quality=80))
    return out, (ax, ay, aw)


def panel(key, body, dim=0.78, extra_defs=""):
    slice_im, (w, h) = bg_slice(key)
    href = data_uri(slice_im)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<defs>{extra_defs}</defs>"
        f'<image width="{w}" height="{h}" preserveAspectRatio="none" href="{href}" xlink:href="{href}"/>'
        f'<rect width="{w}" height="{h}" fill="#000" opacity="{dim}"/>'
        f"{body}</svg>\n"
    )


def write(name, svg):
    os.makedirs(p(HUD), exist_ok=True)
    with open(p(HUD, name), "w", encoding="utf-8") as f:
        f.write(svg)


def t(x, y, s, size=15, fill="#FFFFFF", anchor="start", weight="400", font=SANS, extra=""):
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="{font}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" {extra}>{escape(str(s))}</text>'
    )


def hexbadge(cx, cy, label, fill, stroke, ink, r=26, size=11):
    pts = " ".join(
        f"{cx + r * math.cos(math.radians(a)):.1f},{cy + r * math.sin(math.radians(a)):.1f}"
        for a in (-90, -30, 30, 90, 150, 210)
    )
    return (
        f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>'
        + t(cx, cy + 4, label, size, ink, "middle", "800", MONO)
    )


def bar(x, y, w, frac, color="#1A6FBF"):
    frac = max(0.0, min(1.0, frac))
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="8" rx="4" fill="#1F2937"/>'
        f'<rect x="{x}" y="{y}" width="{max(8, w * frac):.0f}" height="8" rx="4" fill="{color}"/>'
    )


def section_head(w, title, count=None):
    s = f'<rect width="{w}" height="42" fill="#000" opacity=".5"/>' + t(16, 28, title, 18)
    if count is not None:
        s = s.replace(f">{escape(title)}<", f">{escape(title)} <tspan fill=\"#9CA3AF\" font-weight=\"300\">{count}</tspan><")
    return s


# ---------------------------------------------------------------- panels

def render_header(stats, tickets):
    level, xp = level_for(stats)
    (face_a, face_b), (ax, ay, aw) = avatar_layers()
    mid = ax + aw / 2
    # landonorris-style split: the divider sweeps across and reveals the helmet side
    wipe = f"{mid};{ax + aw * 0.22};{ax + aw * 0.22};{ax + aw * 0.78};{ax + aw * 0.78};{mid}"
    kt = "0;0.2;0.42;0.62;0.84;1"
    defs = (
        f'<clipPath id="av"><rect x="{ax}" y="{ay}" width="{aw}" height="{aw}"/></clipPath>'
        f'<clipPath id="wipe"><rect x="{mid}" y="{ay}" width="{aw}" height="{aw}">'
        f'<animate attributeName="x" values="{wipe}" keyTimes="{kt}" dur="9s" repeatCount="indefinite"/></rect></clipPath>'
    )
    fc = PROFILE["featured_cert"]
    body = (
        f'<rect x="{ax - 3}" y="{ay - 3}" width="{aw + 6}" height="{aw + 6}" fill="#E5E7EB"/>'
        f'<g clip-path="url(#av)">'
        f'<image x="{ax}" y="{ay}" width="{aw}" height="{aw}" href="{face_a}" xlink:href="{face_a}"/>'
        f'<image x="{ax}" y="{ay}" width="{aw}" height="{aw}" href="{face_b}" xlink:href="{face_b}" clip-path="url(#wipe)"/>'
        f'<line x1="{mid}" y1="{ay}" x2="{mid}" y2="{ay + aw}" stroke="#FFFFFF" stroke-width="2" opacity=".9">'
        f'<animate attributeName="x1" values="{wipe}" keyTimes="{kt}" dur="9s" repeatCount="indefinite"/>'
        f'<animate attributeName="x2" values="{wipe}" keyTimes="{kt}" dur="9s" repeatCount="indefinite"/></line>'
        f"</g>"
        + t(218, 70, PROFILE["name"], 34)
        + t(220, 100, PROFILE["tagline"], 15, "#D6DEE4")
        + t(220, 140, PROFILE["bio"][0], 15, "#E5E7EB")
        + t(220, 162, PROFILE["bio"][1], 15, "#E5E7EB")
        + t(604, 68, "Level", 30)
        + f'<circle cx="710" cy="58" r="21" fill="#000" fill-opacity=".35" stroke="#E5484D" stroke-width="2.5"/>'
        + t(710, 65, level, 19 if level < 100 else 15, "#FFFFFF", "middle")
        + t(742, 64, f"{xp:,} XP", 12, "#D1D5DB", font=MONO)
        + '<rect x="598" y="92" width="232" height="70" fill="#000" opacity=".55"/>'
        + hexbadge(634, 127, fc[0], fc[2], fc[3], fc[4], r=24)
        + t(670, 122, fc[1], 15, "#FFFFFF", weight="600")
        + t(670, 144, "Featured certification", 13, "#B8C4CC")
        + '<rect x="598" y="172" width="128" height="30" fill="#000" opacity=".72"/>'
        + t(662, 192, "View résumé", 14, "#FFFFFF", "middle")
    )
    write("header.svg", panel("header", body, dim=0.42, extra_defs=defs))


def render_showcase(tickets):
    w = LAYOUT["showcase"][2]
    tiles = []
    for i, (label, cap, border, fill, ink) in enumerate(SHOWCASE[:11]):
        col, row = i % 6, i // 6
        x, y = 16 + col * 88, 56 + row * 90
        tiles.append(
            f'<g transform="translate({x} {y})"><rect width="80" height="80" fill="{fill}" stroke="{border}"/>'
            + t(40, 44, label, 18 if len(label) < 4 else 14, ink, "middle", "800", MONO)
            + t(40, 70, cap, 9, "#9CA3AF", "middle", font=MONO)
            + "</g>"
        )
    n = len(SHOWCASE)
    slot = n if n < 12 else 11
    sx, sy = 16 + (slot % 6) * 88, 56 + (slot // 6) * 90
    tiles.append(
        f'<g transform="translate({sx} {sy})"><rect width="80" height="80" fill="#111" stroke="#3F3F46" stroke-dasharray="4 3"/>'
        + t(40, 48, "+", 22, "#52525B", "middle", font=MONO) + "</g>"
    )
    num_x = sx + 112
    body = (
        section_head(w, "Project Showcase")
        + "".join(tiles)
        + t(num_x, 194, tickets["display"], 48, "#FFFFFF", weight="300")
        + t(num_x + 2, 222, "IT Tickets Closed", 16, "#9CA3AF")
        + t(num_x + 2, 242, tickets["breakdown"], 10, "#6B7280", font=MONO)
    )
    write("showcase.svg", panel("showcase", body, dim=0.8))


def render_sidebar(stats):
    certs = PROFILE["certs"]
    badges = "".join(
        hexbadge(44 + i * 60, 140, c[0], c[1], c[2], c[3], size=10 if len(c[0]) < 5 else 9)
        for i, c in enumerate(certs)
    )
    head, sub = PROFILE["building"]
    body = (
        t(16, 36, head, 22, "#57CBDE")
        + t(16, 58, sub, 13, "#9CA3AF")
        + f'<text x="16" y="98" font-family="{SANS}" font-size="15" fill="#FFFFFF">Certifications '
        f'<tspan fill="#9CA3AF" font-size="22" font-weight="300">{len(certs)}</tspan></text>'
        + badges
        + f'<text x="16" y="206" font-family="{SANS}" font-size="15" fill="#FFFFFF">Repositories '
        f'<tspan fill="#9CA3AF" font-size="22" font-weight="300">{stats["public_repos"]}</tspan></text>'
        + f'<text x="16" y="242" font-family="{SANS}" font-size="15" fill="#FFFFFF">Commits in {stats["year"]} '
        f'<tspan fill="#9CA3AF" font-size="22" font-weight="300">{stats["commits_year"]:,}</tspan></text>'
    )
    write("sidebar.svg", panel("sidebar", body, dim=0.8))


def render_activity(stats):
    w = LAYOUT["activity"][2]
    entries = []
    r = stats.get("recent")
    if r:
        share = r["commits_year"] / stats["commits_year"] if stats["commits_year"] else 0
        initials = "".join(part[0] for part in re.split(r"[-_ ]+", r["name"]) if part)[:3].upper()
        pushed = dt.date.fromisoformat(r["pushed"]).strftime("%b %d").replace(" 0", " ")
        entries.append(
            '<rect x="10" y="10" width="120" height="56" fill="#1E0B33"/>'
            + t(70, 46, initials, 22, "#C084FC", "middle", "800", MONO)
            + t(146, 32, r["name"][:40], 16)
            + t(818, 32, f"{r['commits_total']:,} commits on record", 13, "#9CA3AF", "end")
            + t(818, 52, f"last pushed on {pushed}", 13, "#9CA3AF", "end")
            + t(12, 86, f"{r['commits_year']:,} of your {stats['commits_year']:,} commits in {stats['year']}", 13, "#E5E7EB")
            + bar(330, 78, 488, share)
        )
    score = stats["commits_year"] + 5 * stats["merged_prs_year"]
    frac = score / ROCKET_TARGET
    # rocket position along the thumbnail arc
    rx = 22 + 92 * min(frac, 1)
    ry = 48 - 34 * math.sin(math.pi * min(frac, 1))
    entries.append(
        '<rect x="10" y="10" width="120" height="56" fill="#060B1A"/>'
        '<path d="M22 48 Q68 -6 114 48" fill="none" stroke="#1E293B" stroke-width="2" stroke-dasharray="4 3"/>'
        '<circle cx="22" cy="48" r="7" fill="#1D4ED8"/><circle cx="114" cy="48" r="6" fill="#B91C1C"/>'
        f'<circle cx="{rx:.0f}" cy="{ry:.0f}" r="4" fill="#F43F5E"/>'
        + t(146, 32, "Orbital commit run · Earth → Mars", 16)
        + t(818, 32, f"commits + 5 × merged PRs · {stats['year']}", 13, "#9CA3AF", "end")
        + t(818, 52, "Mars → " + ("reached" if frac >= 1 else f"{ROCKET_TARGET - score:,} pts to go"), 13, "#9CA3AF", "end")
        + t(12, 86, f"{score:,} / {ROCKET_TARGET:,} pts", 13, "#E5E7EB")
        + bar(330, 78, 488, frac, "#3B82F6")
    )
    body = section_head(w, "Recent Activity")
    for i, e in enumerate(entries):
        body += f'<g transform="translate(16 {56 + i * 94})"><rect width="{w - 32}" height="84" fill="#000" opacity=".45"/>{e}</g>'
    write("activity.svg", panel("activity", body, dim=0.8))


def render_portal(key, title, url, status, frame_dark, frame_mid, swirl_a, swirl_b, accent):
    bs, cols, rows = 18, 4, 6
    ox, oy = 18, (150 - rows * bs) // 2
    cells = []
    for r in range(rows):
        for c in range(cols):
            x, y = ox + c * bs, oy + r * bs
            if r in (0, rows - 1) or c in (0, cols - 1):
                cells.append(
                    f'<rect x="{x}" y="{y}" width="{bs}" height="{bs}" fill="{frame_dark}"/>'
                    f'<rect x="{x + 3}" y="{y + 3}" width="{bs - 6}" height="{bs - 6}" fill="{frame_mid}"/>'
                )
            else:
                dur = 1.6 + ((r + c) % 3) * 0.45
                cells.append(
                    f'<rect x="{x}" y="{y}" width="{bs}" height="{bs}" fill="{swirl_a}">'
                    f'<animate attributeName="fill" values="{swirl_a};{swirl_b};{swirl_a}" dur="{dur}s" repeatCount="indefinite"/></rect>'
                )
    body = (
        "".join(cells)
        + t(112, 58, "PORTAL · ENTER", 11, accent, weight="700", font=MONO, extra='letter-spacing="1.5"')
        + t(112, 86, title, 22, "#FFFFFF", weight="600")
        + t(112, 110, f"{url} · {status}", 13, "#57CBDE")
        + f'<circle cx="388" cy="75" r="17" fill="none" stroke="{accent}" stroke-width="2"/>'
        + t(388, 80, "↗", 14, "#FFFFFF", "middle")
    )
    write(f"{key}.svg", panel(key, body, dim=0.8))


def render_guestbook():
    w = LAYOUT["guestbook"][2]
    entries = load_json(GUESTBOOK, {"entries": []})["entries"][-3:][::-1]
    body = (
        section_head(w, "Comments", len(load_json(GUESTBOOK, {"entries": []})["entries"]) or None)
        + '<rect x="16" y="54" width="818" height="36" rx="2" fill="#1F2023" stroke="#3F3F46"/>'
        + t(28, 77, "Add a comment → opens a GitHub issue titled COMMENT: your message", 14, "#8B8B93",
            extra='font-style="italic"')
    )
    if not entries:
        body += t(16, 132, "No comments yet. Be the first to sign the guestbook.", 14, "#9CA3AF")
    for i, e in enumerate(entries[:2] if len(entries) > 2 else entries):
        y = 104 + i * 52
        hue = sum(map(ord, e["user"])) % 360
        body += (
            f'<rect x="16" y="{y}" width="40" height="40" fill="hsl({hue},55%,38%)"/>'
            + t(36, y + 27, e["user"][:1].upper(), 18, "#FFFFFF", "middle", "700")
            + t(68, y + 15, "@" + e["user"], 14, "#FFFFFF")
            + t(68, y + 34, f"{e['date']} · {e['text']}", 13, "#C7CDD3")
        )
    write("guestbook.svg", panel("guestbook", body, dim=0.8))


# ---------------------------------------------------------------- crafting

ITEMS = {
    "iron_ingot": {"name": "Iron Ingot", "file": "assets/iron-ingot.webp"},
    "stick": {"name": "Stick", "file": "assets/stick.webp"},
    "gold_ingot": {"name": "Gold Ingot", "color": ("#FACC15", "#A16207")},
    "diamond": {"name": "Diamond", "color": ("#67E8F9", "#0E7490")},
    "redstone": {"name": "Redstone", "color": ("#EF4444", "#7F1D1D")},
    "planks": {"name": "Planks", "color": ("#B7894C", "#7A5528")},
    "cobblestone": {"name": "Cobblestone", "color": ("#9CA3AF", "#4B5563")},
    "string": {"name": "String", "color": ("#F3F4F6", "#9CA3AF")},
}

_ = None
RECIPES = [
    # (pattern row-major, result, unlock label, unlock url)
    (("iron_ingot",) * 3 + (_, "stick", _) * 2, "Iron Pickaxe", "VibeHash", "https://vibehash.org"),
    ((_, "iron_ingot", _) + (_, "stick", _) * 2, "Iron Shovel", "Luh Labs LLC", "https://luhlabs.com"),
    ((_, "diamond", _) * 2 + (_, "stick", _), "Diamond Sword", "the portfolio game", "https://calebluh.com/game"),
    ((_, "iron_ingot", _, "iron_ingot", "redstone", "iron_ingot", _, "iron_ingot", _), "Compass", "calebluh.com", "https://calebluh.com"),
    ((_, "gold_ingot", _, "gold_ingot", "redstone", "gold_ingot", _, "gold_ingot", _), "Clock", "the ticket counter source", "https://github.com/calebluh/calebluh/blob/main/tickets.json"),
    ((_, "stick", "string", "stick", _, "string", _, "stick", "string"), "Bow", "my repositories", "https://github.com/calebluh?tab=repositories"),
    (("planks",) * 4 + (_,) + ("planks",) * 4, "Chest", "this profile's source", "https://github.com/calebluh/calebluh"),
    (("cobblestone",) * 4 + (_,) + ("cobblestone",) * 4, "Furnace", "the crafting engine", "https://github.com/calebluh/calebluh/blob/main/scripts/crafting_engine.py"),
]

REPO_URL = f"https://github.com/{USERNAME}/{USERNAME}"


def item_icon(key, x, y, size):
    spec = ITEMS[key]
    if "file" in spec:
        im = Image.open(p(spec["file"])).convert("RGBA").resize((64, 64), Image.LANCZOS)
        href = data_uri(im, "PNG")
        return f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="{href}" xlink:href="{href}"/>'
    hi, lo = spec["color"]
    u = size / 8
    if key == "string":
        return f'<path d="M{x + u} {y + 6 * u} C{x + 3 * u} {y + u},{x + 5 * u} {y + 7 * u},{x + 7 * u} {y + 2 * u}" fill="none" stroke="{hi}" stroke-width="{u * .8}"/>'
    if key == "diamond":
        return f'<polygon points="{x + 4 * u},{y + u} {x + 7 * u},{y + 4 * u} {x + 4 * u},{y + 7 * u} {x + u},{y + 4 * u}" fill="{hi}" stroke="{lo}" stroke-width="{u * .6}"/>'
    if key == "redstone":
        return "".join(
            f'<rect x="{x + dx * u}" y="{y + dy * u}" width="{u * 1.4}" height="{u * 1.4}" fill="{hi if (dx + dy) % 2 else lo}"/>'
            for dx, dy in ((2, 3), (4, 2), (5, 4), (3, 5), (1, 5), (5, 6), (6, 2))
        )
    if key in ("planks", "cobblestone"):
        rows = "".join(
            f'<rect x="{x + u}" y="{y + (1 + 2 * i) * u}" width="{6 * u}" height="{1.7 * u}" fill="{hi if i % 2 else lo}"/>'
            for i in range(3)
        )
        return rows
    # ingot
    return f'<polygon points="{x + u},{y + 5 * u} {x + 3 * u},{y + 3 * u} {x + 7 * u},{y + 3 * u} {x + 6 * u},{y + 5 * u}" fill="{hi}" stroke="{lo}" stroke-width="{u * .5}"/>'


def write_cell_svgs():
    """One slot image per item plus an empty '+' slot; README links each cell."""
    os.makedirs(p(ITEMS_DIR), exist_ok=True)
    frame = '<rect width="64" height="64" fill="#8B8B8B"/><rect x="2" y="2" width="60" height="60" fill="#373737"/><rect x="4" y="4" width="58" height="58" fill="#5A5A5A"/>'
    head = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="64" height="64" viewBox="0 0 64 64">'
    with open(p(ITEMS_DIR, "empty.svg"), "w", encoding="utf-8") as f:
        f.write(head + frame + t(32, 41, "+", 24, "#8B8B8B", "middle", font=MONO) + "</svg>\n")
    for key in ITEMS:
        with open(p(ITEMS_DIR, f"{key}.svg"), "w", encoding="utf-8") as f:
            f.write(head + frame + item_icon(key, 10, 10, 44) + "</svg>\n")


def render_crafting_panel():
    state = load_crafting_state()
    w = LAYOUT["crafting"][2]
    found = state["discovered"]
    last = state["log"][-1] if state["log"] else None
    body = (
        t(16, 34, "Crafting Table", 20, "#FBBF24")
        + t(170, 34, f"{len(found)} / {len(RECIPES)} recipes discovered", 14, "#9CA3AF")
        + t(16, 62, "Click any slot below, change the item in the issue title, and submit.", 14, "#E5E7EB")
        + t(16, 84, "The bot places it, replies and closes the issue. Match a recipe to unlock something.", 14, "#C7CDD3")
        + t(16, 108, (f"last action: @{last['user']} · {last['text']}" if last else "No one has crafted yet."), 12, "#9CA3AF", font=MONO)
    )
    write("crafting.svg", panel("crafting", body, dim=0.8))


def load_crafting_state():
    return load_json(CRAFT_STATE, {"grid": [None] * 9, "discovered": [], "log": []})


def crafting_block():
    """HTML for the clickable 3x3 grid, written between README markers."""
    state = load_crafting_state()
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            i = r * 3 + c
            item = state["grid"][i]
            title = f"CRAFT: {item or 'iron_ingot'} -> {i + 1}"
            url = f"{REPO_URL}/issues/new?title={urllib.request.quote(title)}&body={urllib.request.quote(ISSUE_HELP)}"
            img = f"./{ITEMS_DIR}/{item or 'empty'}.svg"
            alt = ITEMS[item]["name"] if item else f"Empty slot {i + 1}"
            cells.append(f'<a href="{url}"><img src="{img}" width="64" height="64" alt="{alt}"/></a>')
        rows.append("".join(cells))
    lines = ["<!--START_CRAFTING-->", '<p align="center">', "<br/>\n".join(rows), "</p>"]
    if state["discovered"]:
        unlocked = []
        for name in state["discovered"]:
            rec = next((rc for rc in RECIPES if rc[1] == name), None)
            if rec:
                unlocked.append(f'<a href="{rec[3]}">{escape(name)} → {escape(rec[2])}</a>')
        lines.append('<p align="center"><sub>Unlocked: ' + " · ".join(unlocked) + "</sub></p>")
    lines.append("<!--END_CRAFTING-->")
    return "\n".join(lines)


ISSUE_HELP = (
    "Just submit this issue, the title does the work.\n\n"
    "Format: `CRAFT: <item> -> <slot 1-9>` (slots go left to right, top to bottom).\n"
    "Items: " + ", ".join(f"`{k}`" for k in ITEMS) + ", or `air` to clear a slot.\n"
)


def update_readme_block():
    path = p("README.md")
    with open(path, encoding="utf-8") as f:
        readme = f.read()
    new = re.sub(r"<!--START_CRAFTING-->.*?<!--END_CRAFTING-->", lambda _: crafting_block(), readme, flags=re.S)
    if new != readme:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)


# ---------------------------------------------------------------- main

def load_tickets():
    data = load_json(TICKETS, {"pre_ahern_estimate": 1350, "ahern_verified": 790})
    total = data["pre_ahern_estimate"] + data["ahern_verified"]
    return {
        "display": f"{total:,}+",
        "breakdown": f"~{data['pre_ahern_estimate']:,} est. + {data['ahern_verified']:,} Ahern verified",
    }


def main():
    stats = load_stats()
    tickets = load_tickets()
    render_header(stats, tickets)
    render_showcase(tickets)
    render_sidebar(stats)
    render_activity(stats)
    render_portal("portal-vibehash", "VibeHash", "vibehash.org", "Online",
                  "#0A0710", "#1E1030", "#7E22CE", "#C084FC", "#C084FC")
    render_portal("portal-luhlabs", "Luh Labs LLC", "luhlabs.com", "In development",
                  "#8A6A12", "#EAB308", "#1D4ED8", "#60A5FA", "#38BDF8")
    render_guestbook()
    write_cell_svgs()
    render_crafting_panel()
    update_readme_block()
    print(f"Rendered profile panels (stats fetched {stats['fetched']})")


if __name__ == "__main__":
    main()
