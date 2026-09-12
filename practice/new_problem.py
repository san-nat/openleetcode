#!/usr/bin/env python3
"""Create a blank starter file for a problem from its manifest.

    python3 practice/new_problem.py top-k-frequent-elements --day 1
    python3 practice/new_problem.py --id 23 --day 3

Writes practice/dayNN/<snake_case_slug>.py with the right signature, the
constraints you need, and nothing else - no hints, no skeleton of the answer.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade import find_problem  # noqa: E402

PRACTICE = os.path.dirname(os.path.abspath(__file__))

PY_TYPE = {
    "int": "int",
    "long": "int",
    "float": "float",
    "double": "float",
    "bool": "bool",
    "string": "str",
    "char": "str",
    "list_node": "Optional[ListNode]",
    "tree_node": "Optional[TreeNode]",
}


def annotate(spec):
    spec = spec or {}
    kind = spec.get("type")
    if kind == "array":
        return "List[%s]" % annotate(spec.get("items"))
    return PY_TYPE.get(kind, "Any")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("title", nargs="?", help="problem slug")
    parser.add_argument("--id", type=int, help="problem id")
    parser.add_argument("--day", type=int, required=True, help="practice day number")
    parser.add_argument("--force", action="store_true", help="overwrite an existing starter file")
    args = parser.parse_args()

    problem_dir = find_problem(args.id, args.title)
    if problem_dir is None:
        print("no manifest found for %s" % (args.title or args.id))
        return 2

    with open(os.path.join(problem_dir, "manifest.yaml"), encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)

    entry = manifest["entry"]
    params = entry.get("params") or {}
    call = entry["call"]["python3"]
    order = re.findall(r"\{(\w+)\}", call)
    method = re.search(r"Solution\(\)\.(\w+)", call)
    method = method.group(1) if method else "solve"

    def param_type(name):
        # Some manifests do the node conversion inside the call itself
        # (e.g. mergeKLists([to_list_node(l) for l in {lists}])), so the
        # declared param type is the JSON shape, not what your method receives.
        for node, wrapper in (("ListNode", "to_list_node("), ("TreeNode", "to_tree_node(")):
            if wrapper in call and re.search(r"for \w+ in \{%s\}" % re.escape(name), call):
                return "List[Optional[%s]]" % node
            if "%s{%s}" % (wrapper, name) in call:
                return "Optional[%s]" % node
        return annotate(params.get(name))

    def return_type():
        if call.startswith("list_node_to_array("):
            return "Optional[ListNode]"
        if call.startswith("tree_node_to_array("):
            return "Optional[TreeNode]"
        for case in manifest.get("tests") or []:
            if "out" not in case:
                continue
            out = case["out"]
            if isinstance(out, bool):
                return "bool"
            if isinstance(out, int):
                return "int"
            if isinstance(out, float):
                return "float"
            if isinstance(out, str):
                return "str"
            if isinstance(out, list):
                if out and isinstance(out[0], list):
                    return "List[List[Any]]"
                if out and isinstance(out[0], str):
                    return "List[str]"
                return "List[int]"
        return "Any"

    signature = ", ".join("%s: %s" % (name, param_type(name)) for name in order)
    needs_node = "Node" in signature or "Node" in return_type()

    slug = entry["title"]
    day_dir = os.path.join(PRACTICE, "day%02d" % args.day)
    os.makedirs(day_dir, exist_ok=True)
    path = os.path.join(day_dir, slug.replace("-", "_") + ".py")
    if os.path.exists(path) and not args.force:
        print("%s already exists (pass --force to overwrite)" % path)
        return 1

    node_note = ""
    if needs_node:
        node_note = (
            "# ListNode / TreeNode are provided by the grader - do not redefine them.\n"
        )

    body = '''"""%(id)s. %(slug)s

Run it:
    python3 practice/grade.py %(rel)s --id %(id)s

%(cases)d test cases, %(limit)d ms budget per case.
"""

%(node_note)sfrom typing import Any, List, Optional


class Solution:
    def %(method)s(self, %(signature)s) -> %(returns)s:
        # your solution here
        pass
''' % {
        "id": entry["id"],
        "slug": slug,
        "rel": os.path.relpath(path, os.path.dirname(PRACTICE)),
        "cases": len(manifest.get("tests") or []),
        "limit": (manifest.get("limits") or {}).get("time_ms", 1000),
        "node_note": node_note,
        "method": method,
        "signature": signature,
        "returns": return_type(),
    }
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    print("created %s" % os.path.relpath(path, os.path.dirname(PRACTICE)))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, PRACTICE)
    sys.exit(main())
