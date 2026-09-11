# Daily interview practice

A daily drill built on top of this repo's own test suites. No Docker and no
network needed: `practice/grade.py` runs your Python solution against the same
`manifest.yaml` files the real runner uses, with the same conventions
(`to_list_node` / `to_tree_node`, `exact` and `ignore_order` judging, and the
oracle checkers).

## The daily loop

1. **Concept questions first.** Answer them before opening an editor. If you
   cannot state the invariant and the complexity, coding is guesswork.
2. **Solve, timed.** Easy 15 min, medium 25-30 min, hard 45 min. Stop at the
   limit and note where you stalled - a stall you can name is a stall you can fix.
3. **Submit to the judge.** Not "it works on the example". The manifests carry
   20-40 cases each, including empty inputs, ties, negatives, and large
   generated inputs.
4. **Review.** Complexity, edge cases, and what the follow-up question would be.
5. **Log it** in `practice/progress.md`, including the problems due for a repeat.

## Commands

Create today's starter file (signature only, no hints):

```console
$ python3 practice/new_problem.py top-k-frequent-elements --day 1
$ python3 practice/new_problem.py --id 23 --day 3
```

Submit it:

```console
$ python3 practice/grade.py practice/day01/top_k_frequent_elements.py --id 347
$ python3 practice/grade.py practice/day01/top_k_frequent_elements.py --title top-k-frequent-elements --all
```

Output is a verdict, the first failing case with its input, and the slowest
case against the manifest's time budget:

```text
FAILED  three_levels_2
  nums:      [9,9,9,8,8,7]
  k:         1
  expected:  [9]
  got:       [9,8]

REJECTED  37/38 cases  -  347. top-k-frequent-elements
slowest case: unique_ranking_8 (0.1 ms, manifest budget 1000 ms)
```

Flags: `--all` shows every failure, `--quiet` prints only the verdict.

## What the grader does and does not do

- It judges **Python 3** solutions. For other languages use the real CLI
  (`openleetcode submit`), which needs the Docker backend.
- Timings come from CPython in this environment, so they are slower than the
  judged runtime. Treat the time line as a smell test for your complexity, not
  as a verdict - correctness is what decides ACCEPTED/REJECTED.
- Cases whose inputs are randomly generated *and* whose expected output was
  recorded from the runner's own RNG draw cannot be reproduced faithfully, so
  they are skipped and reported. Generated cases checked by an oracle - the vast
  majority - are fully judged.

## Layout

```text
practice/
  README.md
  grade.py                 local judge
  new_problem.py           starter-file generator
  progress.md              the log and the spaced-repetition queue
  curriculum/heap.md       track 1: heaps and priority queues
  day01/ day02/ ...        your solutions
```
