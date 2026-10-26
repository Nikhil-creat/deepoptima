"""NSGA-II helpers on plain lists (all objectives are minimised)."""
import math


def dominates(a, b) -> bool:
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def fronts(objs: list[tuple]) -> list[list[int]]:
    n = len(objs)
    S = [[] for _ in range(n)]
    cnt = [0] * n
    out: list[list[int]] = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(objs[p], objs[q]):
                S[p].append(q)
            elif dominates(objs[q], objs[p]):
                cnt[p] += 1
        if cnt[p] == 0:
            out[0].append(p)
    i = 0
    while out[i]:
        nxt = []
        for p in out[i]:
            for q in S[p]:
                cnt[q] -= 1
                if cnt[q] == 0:
                    nxt.append(q)
        i += 1
        out.append(nxt)
    return out[:-1]


def ranks(objs: list[tuple]) -> list[int]:
    r = [0] * len(objs)
    for k, f in enumerate(fronts(objs)):
        for i in f:
            r[i] = k
    return r


def crowding(objs: list[tuple], front: list[int]) -> dict[int, float]:
    if len(front) <= 2:
        return {i: math.inf for i in front}
    d = {i: 0.0 for i in front}
    for m in range(len(objs[0])):
        s = sorted(front, key=lambda i: objs[i][m])
        d[s[0]] = d[s[-1]] = math.inf
        span = (objs[s[-1]][m] - objs[s[0]][m]) or 1.0
        for k in range(1, len(s) - 1):
            d[s[k]] += (objs[s[k + 1]][m] - objs[s[k - 1]][m]) / span
    return d


def select(objs: list[tuple], k: int) -> list[int]:
    chosen: list[int] = []
    for f in fronts(objs):
        if len(chosen) + len(f) <= k:
            chosen += f
        else:
            cd = crowding(objs, f)
            chosen += sorted(f, key=lambda i: -cd[i])[: k - len(chosen)]
            break
    return chosen
