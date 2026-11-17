"""Handle CRAFT: and COMMENT: issues for the profile README.

Run by .github/workflows/crafting-game.yml when an issue is opened.
  CRAFT: <item> -> <slot 1-9>   places an item (or `air` to clear)
  COMMENT: <message>            signs the guestbook
The issue gets a reply and is closed; state lives in assets/*.json.
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import readme as r  # noqa: E402

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", f"{r.USERNAME}/{r.USERNAME}")
TITLE = os.environ.get("ISSUE_TITLE", "")
USER = os.environ.get("ISSUE_USER", "someone")
NUMBER = os.environ.get("ISSUE_NUMBER", "")

CRAFT_RE = re.compile(r"^\s*CRAFT:\s*([a-z_ ]+?)\s*(?:->|→|in|@|to)\s*(?:slot\s*|cell\s*)?([1-9])\s*$", re.I)
COMMENT_RE = re.compile(r"^\s*COMMENT:\s*(.+)$", re.I | re.S)
MAX_COMMENT = 70


def api(method, path, payload=None):
    if not (TOKEN and NUMBER):
        print(f"[dry run] {method} {path}: {payload}")
        return
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-crafting-engine")
    with urllib.request.urlopen(req, timeout=20):
        pass


def reply_and_close(text):
    api("POST", f"/issues/{NUMBER}/comments", {"body": text})
    api("PATCH", f"/issues/{NUMBER}", {"state": "closed", "state_reason": "completed"})


def clean(text):
    """Single line, printable, no markup characters, length-capped."""
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = re.sub(r"[<>`\[\]]", "", " ".join(text.split()))
    return text[:MAX_COMMENT].strip()


def today():
    return dt.date.today().strftime("%b %d, %Y").replace(" 0", " ")


def handle_comment(msg):
    msg = clean(msg)
    if not msg:
        reply_and_close("That comment was empty after cleanup, so nothing was added.")
        return
    book = r.load_json(r.GUESTBOOK, {"entries": []})
    book["entries"].append({"user": USER, "date": today(), "text": msg})
    book["entries"] = book["entries"][-50:]
    r.save_json(r.GUESTBOOK, book)
    r.render_guestbook()
    reply_and_close(f"Thanks @{USER}! Your comment is on the profile now:\n\n> {msg}")


def handle_craft(item, slot):
    item = item.strip().lower().replace(" ", "_")
    if item not in r.ITEMS and item != "air":
        reply_and_close(
            f"`{item}` isn't an item on this table.\n\n" + r.ISSUE_HELP
        )
        return
    state = r.load_crafting_state()
    state["grid"][slot - 1] = None if item == "air" else item
    placed = "cleared slot" if item == "air" else f"placed {r.ITEMS[item]['name']} in slot"
    message = f"@{USER} {placed} {slot}."
    entry = f"{placed} {slot}"

    pattern = tuple(state["grid"])
    match = next((rc for rc in r.RECIPES if rc[0] == pattern), None)
    if match:
        _, result, unlock, url = match
        state["grid"] = [None] * 9
        new = result not in state["discovered"]
        if new:
            state["discovered"].append(result)
        entry = f"crafted {result}"
        message = (
            f"@{USER} crafted **{result}**! "
            + ("New recipe discovered. " if new else "")
            + f"It unlocks [{unlock}]({url}). The table has been cleared for the next player."
        )

    state["log"] = (state["log"] + [{"user": USER, "date": today(), "text": entry}])[-20:]
    r.save_json(r.CRAFT_STATE, state)
    r.render_crafting_panel()
    r.update_readme_block()
    reply_and_close(message + f"\n\n[Back to the profile](https://github.com/{r.USERNAME})")


def main():
    m = COMMENT_RE.match(TITLE)
    if m:
        handle_comment(m.group(1))
        return
    m = CRAFT_RE.match(TITLE)
    if m:
        handle_craft(m.group(1), int(m.group(2)))
        return
    if TITLE.strip().upper().startswith("CRAFT:"):
        reply_and_close("I couldn't read that recipe step.\n\n" + r.ISSUE_HELP)
        return
    print("Not a game issue; nothing to do.")


if __name__ == "__main__":
    main()
