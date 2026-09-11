# Track 1 - Heaps and Priority Queues (7 days)

Every problem below has a manifest in `tests/`, so every solution gets judged
locally against 20-40 cases, including adversarial ones.

The rule for each day: **say the approach and the complexity out loud before you
type**. In a real loop the interviewer stops you the moment you start coding
without a plan, and most rejections at FANG are "could not drive the discussion",
not "could not code".

---

## Day 1 - Mechanics and top-K

Concepts to own before you write anything:

- A binary heap is an array. `parent(i) = (i-1)//2`, `left(i) = 2i+1`, `right(i) = 2i+2`.
- `push` = append + sift up, `pop` = swap last into root + sift down. Both O(log n).
- Building a heap from n items by `heapify` is **O(n)**, not O(n log n). Know why:
  the work is `sum over levels of (nodes at that level) * (height below it)`, which telescopes to O(n).
- Python's `heapq` is a **min-heap only**. For a max-heap, push `-x` (ints) or
  `(-key, tiebreak, item)` tuples.
- k-th largest: a **min-heap of size k**, O(n log k), not a sort of the whole array.
  Know when quickselect (O(n) average) is the better answer and what its worst case is.

Problems:

1. `1046. last-stone-weight` - warm-up, max-heap simulation.
2. `347. top-k-frequent-elements` - count + size-k heap. Then answer: what makes
   bucket sort O(n) here, and when would you still prefer the heap?

## Day 2 - Custom ordering and tie-breaks

This is where people lose offers: the ordering is right in their head and wrong
in the comparator.

- `973. k-closest-points-to-origin` - size-k max-heap by squared distance. Never
  take the square root: it costs time and loses precision for no benefit.
- `692. top-k-frequent-words` - frequency descending, then **lexicographic
  ascending**. With a size-k heap in Python the tie-break has to flip for the
  word but not the count. Get this wrong and 3 of the 20 cases fail - which is
  exactly what a hidden test at an onsite does.

## Day 3 - K-way merge

- `23. merge-k-sorted-lists` - heap of k heads, O(N log k). Be ready to compare
  against divide-and-conquer pairwise merging (same complexity, different
  constant and memory profile).
- `373. find-k-pairs-with-smallest-sums` - the "do not push the whole grid"
  lesson: seed the heap with k candidates and expand neighbours lazily.
- Stretch: `632. smallest-range-covering-elements-from-k-lists`.

## Day 4 - Two heaps, and knowing when not to use a heap

- `480. sliding-window-median` - max-heap of the low half, min-heap of the high
  half, rebalance, and **lazy deletion** for elements that slid out of the
  window. This is the hardest standard heap problem in the set; expect it to
  take a full hour.
- `239. sliding-window-maximum` - the contrast case. A heap gives O(n log n); a
  monotonic deque gives O(n). Solve it both ways and be able to say why the
  deque wins.

## Day 5 - Greedy scheduling with a heap

- `621. task-scheduler` - heap simulation first, then the O(n) counting formula.
  Interviewers love asking for the formula after the simulation.
- `1834. single-threaded-cpu` - sort by arrival, heap by (duration, index),
  advance time when the CPU idles. The time-advance bug here is the classic one.
- Stretch: `1353. maximum-number-of-events-that-can-be-attended`.

## Day 6 - Heap + graph (Dijkstra)

- `743. network-delay-time` - textbook Dijkstra with a lazy-deletion heap.
- `787. cheapest-flights-within-k-stops` - Dijkstra with a stop budget vs
  Bellman-Ford in k rounds. Know which one is correct here and why plain
  Dijkstra with a visited set is wrong.
- Stretch: `778. swim-in-rising-water` - Dijkstra where the cost is a max, not a sum.

## Day 7 - Timed mock and retro

45 minutes, no hints, talk through it as if someone is watching:

- `767. reorganize-string`
- `1642. furthest-building-you-can-reach`
- `502. ipo`

Then write the retro in `practice/progress.md`: what pattern you reached for
first, where you stalled, and which of days 1-6 needs a repeat.

---

## What comes after heaps

Binary search on the answer -> graphs (BFS/DFS/topological) -> intervals ->
dynamic programming -> tries and strings. Same daily shape: concept questions
first, then judged problems, then a retro.
