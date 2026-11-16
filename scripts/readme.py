import json
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont

USERNAME = "calebluh"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HUD_DIR = "assets/hud"
os.makedirs(HUD_DIR, exist_ok=True)


def gh_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


# 1. Fetch live data & stats
user_data = gh_get(f"https://api.github.com/users/{USERNAME}/repos?sort=pushed&per_page=30")
repos = [r for r in user_data if not r.get("fork")]

# Calculate language/skill weights based on actual public repos
lang_counts = {}
for r in repos:
    lang = r.get("language")
    if lang:
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

# Read ticket count
tickets_msg = "2,140+"
if os.path.exists("tickets.json"):
    with open("tickets.json") as f:
        tickets_msg = json.load(f).get("message", "2,140+").split(" ")[0]

# 2. Generate Tickets Closed Banner (.png)
ticket_img = Image.new("RGB", (920, 110), color="#062C22")
draw = ImageDraw.Draw(ticket_img)

# Draw dark sci-fi border & tech lines
draw.rectangle([2, 2, 917, 107], outline="#34D399", width=2)
draw.text((460, 24), "ALL-TIME IT TICKETS RESOLVED // ENTERPRISE & MUNICIPAL", fill="#6EE7B7", anchor="mm")
draw.text((460, 68), f"{tickets_msg}", fill="#FFFFFF", anchor="mm")
draw.text((460, 93), "VERIFIED J.F. AHERN COUNT + PRE-AHERN INTERNSHIP ESTIMATE", fill="#A7F3D0", anchor="mm")
ticket_img.save(f"{HUD_DIR}/tickets-closed-banner.png")


# 3. Generate Top Skills Mastered Card (.png)
skills_img = Image.new("RGB", (450, 180), color="#0F172A")
draw = ImageDraw.Draw(skills_img)
draw.rectangle([2, 2, 447, 177], outline="#10B981", width=2)
draw.text((225, 24), "TOP MASTERED SKILLS // CODE & RESUME", fill="#34D399", anchor="mm")

# Skill bars based on actual domains
skills = [
    ("Enterprise IT & Intune Automation", 0.92, "#10B981"),
    ("Distributed Systems & PyTorch", 0.85, "#3B82F6"),
    ("Full-Stack Web (React / Next.js)", 0.78, "#A855F7"),
]

y_offset = 55
for name, pct, color in skills:
    draw.text((25, y_offset), name, fill="#F8FAFC", anchor="lm")
    draw.rectangle([25, y_offset + 14, 425, y_offset + 24], fill="#090D16")
    draw.rectangle([25, y_offset + 14, int(25 + 400 * pct), y_offset + 24], fill=color)
    y_offset += 42

skills_img.save(f"{HUD_DIR}/top-skills-card.png")
print("Successfully generated dynamic HUD stat images!")
