#!/usr/bin/env python3
"""Local, Docker-free grader for practice solutions.

Runs a Python solution against the manifests that already live in tests/,
using the same conventions as runtimes/python3 (to_list_node, to_tree_node,
to_json, judge types exact / ignore_order, and oracle checkers).

    python3 practice/grade.py practice/day01/top_k_frequent.py --title top-k-frequent-elements
    python3 practice/grade.py mysol.py --id 347 --all
"""

from __future__ import annotations

import argparse
import json
import copy
import os
import random
import re
import sys
import time
import traceback

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
UTILITIES = os.path.join(REPO, "runtimes", "python3", "utilities.py")

PREAMBLE = """
import sys, array, math, heapq, bisect, time, itertools, random, re
import operator, string, decimal, fractions, statistics, datetime, json
from typing import *
from collections import *
from dataclasses import *
from functools import *
from heapq import *
from bisect import *
try:
    from sortedcontainers import SortedDict, SortedList, SortedSet
except ImportError:
    pass
sys.setrecursionlimit(10 ** 6)
"""

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    ("\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m")
    if sys.stdout.isatty()
    else ("", "", "", "", "", "")
)


def find_problem(problem_id=None, title=None):
    """Locate a problem directory by numeric id or by slug."""
    for bucket in sorted(os.listdir(TESTS)):
        bucket_path = os.path.join(TESTS, bucket)
        if not os.path.isdir(bucket_path):
            continue
        for name in os.listdir(bucket_path):
            head, _, slug = name.partition(". ")
            if problem_id is not None and head == str(problem_id):
                return os.path.join(bucket_path, name)
            if title is not None and slug == title:
                return os.path.join(bucket_path, name)
    return None


def has_generator(value):
    if isinstance(value, dict):
        return "gen" in value or any(has_generator(v) for v in value.values())
    if isinstance(value, list):
        return any(has_generator(v) for v in value)
    return False


def materialize(spec, rng):
    """Turn a manifest input spec into a concrete Python value.

    Mirrors the generator shapes documented in TEST_FORMAT.md. Our RNG is not
    the runner's RNG, so generated cases are only used where the manifest
    checks them with an oracle rather than a recorded output.
    """
    if isinstance(spec, list):
        return [materialize(item, rng) for item in spec]
    if not isinstance(spec, dict):
        return spec
    if "gen" not in spec:
        if "value" in spec:
            return materialize(spec["value"], rng)
        return spec

    kind = spec["gen"]
    if kind == "int":
        return rng.randint(spec["min"], spec["max"])
    if kind == "float":
        precision = spec.get("precision", 0)
        value = rng.uniform(spec["min"], spec["max"])
        return round(value, precision) if precision else float(round(value))
    if kind == "bool":
        return rng.choice([True, False])
    if kind == "char":
        return rng.choice(spec["variety"])
    if kind == "str":
        length = materialize(spec["len"], rng)
        return "".join(rng.choice(spec["alphabet"]) for _ in range(length))
    if kind == "array":
        length = materialize(spec["len"], rng)
        of = spec["of"]
        if spec.get("distinct"):
            seen, items = set(), []
            guard = 0
            while len(items) < length and guard < length * 200 + 1000:
                guard += 1
                item = materialize(of, rng)
                key = json.dumps(item, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
        else:
            items = [materialize(of, rng) for _ in range(length)]
        if spec.get("sorted"):
            items.sort(key=lambda v: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v)
        return items
    raise ValueError("unsupported generator: %r" % kind)


def coerce(value, spec):
    """YAML types are looser than the manifest's declared param types.

    `s: 7` under a `string` param has to reach the solution as "7", the way the
    typed runtimes receive it.
    """
    spec = spec or {}
    kind = spec.get("type")
    if value is None:
        return None
    if kind in ("string", "char"):
        return value if isinstance(value, str) else json.dumps(value)
    if kind in ("int", "long") and isinstance(value, bool) is False and isinstance(value, (int, float)):
        return int(value)
    if kind in ("float", "double") and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if kind == "array" and isinstance(value, list):
        return [coerce(item, spec.get("items")) for item in value]
    return value


def build_namespace(solution_src, solution_path):
    ns = {"__name__": "__solution__", "__file__": solution_path}
    exec(compile(PREAMBLE, "<preamble>", "exec"), ns)
    with open(UTILITIES, encoding="utf-8") as handle:
        exec(compile(handle.read(), UTILITIES, "exec"), ns)
    exec(compile(solution_src, solution_path, "exec"), ns)
    return ns


def arg_expr(name, spec):
    """Mirror pythonExpr in core/Core/Test/Runner.hs."""
    kind = (spec or {}).get("type")
    if kind == "list_node":
        return "to_list_node(%s)" % name
    if kind == "tree_node":
        return "to_tree_node(%s)" % name
    return name


def render_call(template, params):
    def sub(match):
        name = match.group(1)
        return arg_expr(name, params.get(name))

    return re.sub(r"\{(\w+)\}", sub, template)


def canonical(value):
    """Sort nested lists so that ignore_order comparisons are stable."""
    if isinstance(value, list):
        inner = [canonical(v) for v in value]
        return sorted(inner, key=lambda v: json.dumps(v, sort_keys=True))
    return value


def close_enough(got, expected):
    """Structural equality, with 1e-5 tolerance on floats (LeetCode's rule)."""
    if isinstance(got, bool) or isinstance(expected, bool):
        return got == expected
    if isinstance(got, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(got) - float(expected)) <= 1e-5
    if isinstance(got, list) and isinstance(expected, list):
        return len(got) == len(expected) and all(close_enough(a, b) for a, b in zip(got, expected))
    return got == expected


def compare(judge_type, got_json, expected):
    expected_json = json.dumps(expected, separators=(",", ":"))
    if got_json == expected_json:
        return True
    # Some manifests store `out` as the raw JSON text the judge compares against
    # stdout (e.g. out: '"1219"' for a string answer), so accept a text match too.
    if isinstance(expected, str) and got_json == expected:
        return True
    # A few manifests record an empty linked list / tree as `null` while the
    # python3 serializers emit `[]` for the same answer.
    if expected is None and got_json == "[]":
        return True
    try:
        got = json.loads(got_json)
    except json.JSONDecodeError:
        return False
    if judge_type == "ignore_order":
        return close_enough(canonical(got), canonical(expected))
    return close_enough(got, expected)


def run_oracle(ns, oracle, case_inputs, result):
    checker_src = oracle.get("checker")
    call = oracle.get("call")
    if not checker_src or not call:
        return None, "manifest has no usable python3 oracle"
    local = dict(ns)
    exec(compile(checker_src, "<oracle>", "exec"), local)
    # The real runner checks the oracle in a separate program fed the solution's
    # printed JSON and a fresh copy of the inputs, so do the same here: the
    # checker must not see tuples, custom objects, or inputs the solution mutated.
    local.update(copy.deepcopy(case_inputs))
    local["__result__"] = json.loads(ns["to_json"](result))
    # Most manifests write oracle args as plain names, but some use the same
    # {placeholder} syntax as entry.call; left alone, "{height}" would evaluate
    # as a Python set literal.
    expr = re.sub(r"\{(\w+)\}", lambda m: "__result__" if m.group(1) == "result" else m.group(1),
                  call.replace("{result}", "{result}"))
    try:
        verdict = eval(expr, local)
    except Exception:
        return None, traceback.format_exc(limit=3)
    return bool(verdict), None


def main():
    parser = argparse.ArgumentParser(description="Grade a Python solution against the repo's test manifests.")
    parser.add_argument("solution", help="path to your .py solution")
    parser.add_argument("--id", type=int, help="problem id, e.g. 347")
    parser.add_argument("--title", help="problem slug, e.g. top-k-frequent-elements")
    parser.add_argument("--all", action="store_true", help="show every failure, not just the first")
    parser.add_argument("--quiet", action="store_true", help="only print the summary line")
    args = parser.parse_args()

    if args.id is None and args.title is None:
        parser.error("pass --id or --title")

    problem_dir = find_problem(args.id, args.title)
    if problem_dir is None:
        print("%sno manifest found for %s%s" % (RED, args.title or args.id, RESET))
        return 2

    with open(os.path.join(problem_dir, "manifest.yaml"), encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)

    entry = manifest["entry"]
    params = entry.get("params") or {}
    template = entry["call"]["python3"]
    judge_type = (manifest.get("judge") or {}).get("type", "exact")
    oracle = (manifest.get("oracle") or {}).get("python3")
    limit_ms = (manifest.get("limits") or {}).get("time_ms", 1000)
    cases = manifest["tests"]

    with open(args.solution, encoding="utf-8") as handle:
        solution_src = handle.read()

    try:
        ns = build_namespace(solution_src, args.solution)
    except Exception:
        print("%sYour file did not even load - fix this first:%s\n" % (RED, RESET))
        traceback.print_exc(limit=5)
        return 1

    expr = render_call(template, params)
    suite_seed = manifest.get("seed", 0)
    passed, failures, skipped, slowest, slowest_name = 0, [], [], 0.0, ""

    for case in cases:
        raw_inputs = dict(case.get("in") or {})
        if has_generator(raw_inputs) and "out" in case:
            # Inputs were drawn by the runner's RNG and the output recorded from
            # that exact draw; we cannot reproduce it, so don't pretend to judge it.
            skipped.append(case.get("name", "?"))
            continue
        rng = random.Random(case.get("seed", suite_seed))
        try:
            case_inputs = {k: coerce(materialize(v, rng), params.get(k)) for k, v in raw_inputs.items()}
        except ValueError as exc:
            skipped.append("%s (%s)" % (case.get("name", "?"), exc))
            continue
        pristine_inputs = copy.deepcopy(case_inputs)
        local = dict(ns)
        local.update(case_inputs)
        started = time.perf_counter()
        try:
            result = eval(expr, local)
        except Exception:
            failures.append((case, None, traceback.format_exc(limit=4)))
            continue
        elapsed = (time.perf_counter() - started) * 1000.0
        if elapsed > slowest:
            slowest, slowest_name = elapsed, case.get("name", "?")

        if "out" in case:
            got_json = ns["to_json"](result)
            ok = compare(judge_type, got_json, case["out"])
            detail = got_json
        elif oracle:
            ok, err = run_oracle(ns, oracle, pristine_inputs, result)
            detail = ns["to_json"](result) if err is None else err
            if ok is None:
                ok = False
        else:
            ok, detail = False, "case has no `out` and the manifest has no oracle"

        if ok:
            passed += 1
        else:
            failures.append((case, detail, None))

    total = len(cases) - len(skipped)
    if not args.quiet:
        for case, detail, err in failures if args.all else failures[:1]:
            print("%sFAILED%s  %s" % (RED, RESET, case.get("name", "?")))
            for key, value in (case.get("in") or {}).items():
                print("  %-10s %s" % (key + ":", json.dumps(value)[:300]))
            if err:
                print("  %sraised:%s\n%s" % (RED, RESET, "".join("    " + l for l in err.splitlines(True))))
            else:
                if "out" in case:
                    print("  expected:  %s" % json.dumps(case["out"], separators=(",", ":"))[:300])
                else:
                    print("  expected:  (oracle-checked)")
                print("  got:       %s" % str(detail)[:300])
            print()
        if len(failures) > 1 and not args.all:
            print("%s... and %d more failing case(s); rerun with --all%s\n" % (DIM, len(failures) - 1, RESET))

    slug = os.path.basename(problem_dir)
    if skipped and not args.quiet:
        print("%sskipped %d case(s) with randomly generated inputs and recorded outputs: %s%s"
              % (DIM, len(skipped), ", ".join(skipped[:4]), RESET))
    if passed == total:
        print("%s%sACCEPTED%s  %d/%d cases  -  %s" % (BOLD, GREEN, RESET, passed, total, slug))
    else:
        print("%s%sREJECTED%s  %d/%d cases  -  %s" % (BOLD, RED, RESET, passed, total, slug))
    print("%sslowest case: %s (%.1f ms, manifest budget %d ms)%s" % (DIM, slowest_name, slowest, limit_ms, RESET))
    if passed == total and slowest > limit_ms:
        print("%snote: CPython here is slower than the judged runtime, but a case this slow is worth a second look at your complexity.%s" % (YELLOW, RESET))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
