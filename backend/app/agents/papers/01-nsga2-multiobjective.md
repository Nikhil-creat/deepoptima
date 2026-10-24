# Multi-objective selection for architecture search

A candidate network is described by several objectives at once: accuracy, latency and parameter count. A candidate dominates another when it is no worse on every objective and strictly better on at least one. The Pareto front is the set of candidates nobody dominates.

NSGA-II sorts a population into successive fronts and breaks ties inside a front with crowding distance, which prefers candidates in sparse regions of the front. This keeps diversity, so the search returns a spread of trade-offs (small and fast, large and accurate) rather than one point.

When a search stalls on a single front, raise mutation strength or inject fresh random candidates.
