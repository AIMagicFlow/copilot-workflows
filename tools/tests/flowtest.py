"""Helpers for tests that inspect built flow JSON. Import with: from flowtest import ..."""
import json
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402

TR = "trend-researcher"


@lru_cache(maxsize=None)
def _render(locale):
    return build.render_solution(build.Vertical(build.ROOT, TR), locale)


def load_built(locale, filename):
    """Return the parsed flow JSON as built for `locale`. `filename` is the zip entry, e.g. Workflows/X-GUID.json."""
    files = _render(locale)
    if filename not in files:
        raise KeyError(f"{filename} not in built solution ({locale})")
    return json.loads(files[filename].decode("utf-8").lstrip("﻿"))


def built_text(locale, filename):
    return _render(locale)[filename].decode("utf-8")


def _children(action):
    """Yield (branch suffix, actions dict) for every nested action container of an action."""
    if "actions" in action:
        yield "", action["actions"]
    if "else" in action:
        yield "/else", action["else"].get("actions", {})
    for case_name, case in action.get("cases", {}).items():
        yield f"/case:{case_name}", case.get("actions", {})
    if "default" in action:
        yield "/default", action["default"].get("actions", {})


def _search(actions, name, trail):
    for key, action in actions.items():
        if key == name:
            return action, trail
        for suffix, inner in _children(action):
            found = _search(inner, name, trail + [key + suffix])
            if found:
                return found
    return None


def _find(doc, name):
    found = _search(doc["properties"]["definition"].get("actions", {}), name, [])
    if not found:
        raise KeyError(name)
    return found


def find_action(doc, name):
    return _find(doc, name)[0]


def params(doc, name):
    return find_action(doc, name).get("inputs", {}).get("parameters", {})


def run_after(doc, name):
    return find_action(doc, name).get("runAfter", {})


def path_to(doc, name):
    """Names of the enclosing actions, outermost first; branches carry /else or /case:<x>."""
    return _find(doc, name)[1]
