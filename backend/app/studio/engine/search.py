"""Multi-objective (score vs latency vs size) evolutionary model search. Pure Python generator: easy to test, easy to run in a worker thread."""
import io, random, statistics, time, warnings
from typing import Callable, Iterator
import joblib, numpy as np, pandas as pd, sklearn
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, make_scorer,
                             mean_absolute_error, mean_squared_error, r2_score)
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.model_selection import train_test_split
from . import pareto, space
from .profile import DataError

METRICS = {
    "classification": {"accuracy": "Accuracy", "balanced_accuracy": "Balanced accuracy (good for imbalanced classes)", "f1_macro": "F1 (macro)"},
    "regression": {"r2": "R² (higher is better)", "neg_mae": "Negative MAE (closer to 0 is better)", "neg_rmse": "Negative RMSE (closer to 0 is better)"},
}
SEARCH_TRAIN_CAP = 8000
FINAL_TRAIN_CAP = 30000
MAX_BLOB = 8 * 1024 * 1024
CV_BELOW = 1500          # below this many search rows, scores are 3-fold averages (a single split is too noisy)
BOOT = 200


def score_fn(task: str, metric: str) -> Callable:
    if task == "classification":
        return {"accuracy": accuracy_score, "balanced_accuracy": balanced_accuracy_score,
                "f1_macro": lambda y, p: f1_score(y, p, average="macro")}[metric]
    return {"r2": r2_score, "neg_mae": lambda y, p: -mean_absolute_error(y, p),
            "neg_rmse": lambda y, p: -float(np.sqrt(mean_squared_error(y, p)))}[metric]


def default_metric(task: str, y: pd.Series | None = None) -> str:
    if task == "regression":
        return "r2"
    if y is not None and len(y):
        share = y.value_counts(normalize=True)
        if share.min() < 0.25 and len(share) > 1:
            return "balanced_accuracy"
    return "accuracy"


def resolve_task(requested: str, hint: str) -> str:
    return hint if requested == "auto" else requested


def prepare(df: pd.DataFrame, target: str, features: list[dict], task: str):
    """Returns (X, y, notes). Raises DataError with a friendly message."""
    notes: list[str] = []
    if target not in df.columns:
        raise DataError("Target column not found.")
    cols = [f["name"] for f in features]
    if not cols:
        raise DataError("No usable feature columns (after ignoring constant / ID-like columns).")
    d = df[cols + [target]].copy()
    if task == "classification":
        d[target] = d[target].map(lambda v: np.nan if pd.isna(v) else (str(int(v)) if isinstance(v, float) and float(v).is_integer() else str(v)))
        d = d.dropna(subset=[target])
        vc = d[target].value_counts()
        rare = vc[vc < 4].index
        if len(rare):
            notes.append(f"Dropped {len(rare)} class(es) with fewer than 4 rows.")
            d = d[~d[target].isin(rare)]
        if d[target].nunique() < 2:
            raise DataError("The target needs at least 2 classes with 4+ rows each.")
        if d[target].nunique() > 50:
            raise DataError("The target has more than 50 classes.")
    else:
        d[target] = pd.to_numeric(d[target], errors="coerce")
        d = d[np.isfinite(d[target])]
    if len(d) < 30:
        raise DataError("Fewer than 30 usable rows remain after removing rows with a missing target.")
    return d[cols], d[target], notes


def _split(X, y, task, test_size, seed):
    def tts(a, b, size, strat):
        try:
            return train_test_split(a, b, test_size=size, random_state=seed, stratify=strat)
        except ValueError:
            return train_test_split(a, b, test_size=size, random_state=seed)
    strat = y if task == "classification" else None
    Xt, Xte, yt, yte = tts(X, y, test_size, strat)
    Xtr, Xva, ytr, yva = tts(Xt, yt, 0.25, yt if strat is not None else None)
    return Xtr, Xva, Xte, ytr, yva, yte


def _latency_ms_per_1000(model, X: pd.DataFrame) -> float:
    Xs = X.iloc[: min(500, len(X))]
    times = []
    for _ in range(3):
        t = time.perf_counter()
        model.predict(Xs)
        times.append(time.perf_counter() - t)
    return statistics.median(times) / max(len(Xs), 1) * 1e6


def _dump(model) -> bytes:
    buf = io.BytesIO()
    joblib.dump(model, buf, compress=3)
    return buf.getvalue()


def _feature_meta(X: pd.DataFrame, features: list[dict]) -> list[dict]:
    out = []
    for f in features:
        s = X[f["name"]]
        m = {"name": f["name"], "kind": f["kind"]}
        if f["kind"] == "numeric":
            m.update(min=float(s.min()), max=float(s.max()), median=float(s.median()))
        else:
            m["values"] = [str(v) for v in s.dropna().value_counts().index[:20]]
        out.append(m)
    return out


def _folds(Xtr, ytr, Xva, yva, task, seed):
    pool_X, pool_y = pd.concat([Xtr, Xva]), pd.concat([ytr, yva])
    if len(pool_X) >= CV_BELOW:
        return [(Xtr, ytr, Xva, yva)], False
    splitter = None
    if task == "classification" and pool_y.value_counts().min() >= 3:
        splitter = StratifiedKFold(3, shuffle=True, random_state=seed)
    splitter = splitter or KFold(3, shuffle=True, random_state=seed)
    return [(pool_X.iloc[a], pool_y.iloc[a], pool_X.iloc[b], pool_y.iloc[b]) for a, b in splitter.split(pool_X, pool_y)], True


def _ci(fn, y, p, seed):
    y, p = np.asarray(y), np.asarray(p)
    m = len(y)
    if m < 10:
        return None
    rs, vals = np.random.RandomState(seed), []
    for _ in range(BOOT if m <= 20000 else 100):
        i = rs.randint(0, m, m)
        try:
            v = float(fn(y[i], p[i]))
            if np.isfinite(v):
                vals.append(v)
        except Exception:
            pass
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) >= 20 else None


def _diagnostics(task, y, p, seed):
    y, p = np.asarray(y), np.asarray(p)
    if task == "classification":
        labs = sorted(set(map(str, y)) | set(map(str, p)))
        if len(labs) > 12:
            return None
        return {"kind": "confusion", "labels": labs, "matrix": confusion_matrix(y.astype(str), p.astype(str), labels=labs).tolist()}
    yf, pf = y.astype(float), p.astype(float)
    err = pf - yf
    idx = np.random.RandomState(seed).permutation(len(yf))[:200]
    return {"kind": "regression", "mae": round(float(np.abs(err).mean()), 4), "rmse": round(float(np.sqrt((err ** 2).mean())), 4),
            "scatter": [[round(float(yf[i]), 4), round(float(pf[i]), 4)] for i in idx]}


def search_iter(df: pd.DataFrame, target: str, features: list[dict], cfg: dict, cancel: Callable[[], bool] = lambda: False) -> Iterator[dict]:
    """cfg: task, metric, families, generations, population, time_limit_s, test_size, seed."""
    warnings.filterwarnings("ignore")
    task, metric, seed = cfg["task"], cfg["metric"], cfg["seed"]
    families = [f for f in cfg["families"] if f in space.FAMILIES]
    if not families:
        raise DataError("Select at least one model family.")
    rng = random.Random(seed)
    X, y, notes = prepare(df, target, features, task)
    Xtr, Xva, Xte, ytr, yva, yte = _split(X, y, task, cfg["test_size"], seed)
    if len(Xtr) > SEARCH_TRAIN_CAP:
        idx = Xtr.sample(SEARCH_TRAIN_CAP, random_state=seed).index
        Xtr_s, ytr_s = Xtr.loc[idx], ytr.loc[idx]
        notes.append(f"Search used a {SEARCH_TRAIN_CAP:,}-row sample for speed; final models are refit on all training data.")
    else:
        Xtr_s, ytr_s = Xtr, ytr
    fn = score_fn(task, metric)
    folds, used_cv = _folds(Xtr_s, ytr_s, Xva, yva, task, seed)
    if used_cv:
        notes.append("Small dataset: scores during the search are averages over 3 folds, which makes them more reliable.")
    dummy = lambda: DummyClassifier(strategy="most_frequent") if task == "classification" else DummyRegressor(strategy="mean")
    baseline_val = float(np.mean([fn(d, dummy().fit(a, b).predict(c)) for a, b, c, d in folds]))
    yield {"type": "info", "n_train": len(Xtr), "n_val": len(Xva), "n_test": len(Xte), "n_features": len(features),
           "baseline_val": baseline_val, "notes": notes, "cv": used_cv,
           "classes": sorted(map(str, y.unique()))[:50] if task == "classification" else []}

    t0 = time.monotonic()
    limit = cfg["time_limit_s"]
    stop = lambda: cancel() or (time.monotonic() - t0) > limit
    seen: dict[str, dict] = {}

    def evaluate(g: dict) -> dict:
        t = time.perf_counter()
        try:
            scores, last = [], None
            for a, b, c, d in folds:
                pipe = space.build_pipeline(features, g, task, seed, len(a)).fit(a, b)
                scores.append(float(fn(d, pipe.predict(c))))
                last = (pipe, c)
            score = float(np.mean(scores))
            if not np.isfinite(score):
                raise ValueError("non-finite score")
            pipe, Xv = last
            return {"status": "ok", "score": score, "latency_ms": _latency_ms_per_1000(pipe, Xv),
                    "size_kb": len(_dump(pipe)) / 1024, "fit_seconds": (time.perf_counter() - t) / len(folds)}
        except Exception as e:                                    # a bad candidate must never kill the search
            return {"status": "failed", "error": str(e)[:160], "score": None, "latency_ms": None, "size_kb": None,
                    "fit_seconds": time.perf_counter() - t}

    def initial() -> list[dict]:
        return [space.sample(families[i % len(families)], rng) for i in range(cfg["population"])]

    pop = initial()
    stopped = ""
    for gen in range(cfg["generations"]):
        for g in pop:
            if stop():
                stopped = "cancelled" if cancel() else "time limit"
                break
            k = space.key(g)
            if k in seen:
                continue
            res = evaluate(g)
            seen[k] = {"key": k, "genotype": g, "gen": gen, **res}
            yield {"type": "trial", "gen": gen, "family": g["family"], "params": g["params"], "key": k,
                   "label": space.describe(g), **res}
        ok = [t for t in seen.values() if t["status"] == "ok"]
        if ok:
            objs = [(-t["score"], t["latency_ms"], t["size_kb"]) for t in ok]
            rk = pareto.ranks(objs)
            yield {"type": "generation", "gen": gen + 1, "best_score": max(t["score"] for t in ok),
                   "front_size": sum(1 for r in rk if r == 0), "tried": len(seen)}
        if stopped:
            break
        if not ok:
            pop = initial()
            continue
        elite = [ok[i]["genotype"] for i in pareto.select(objs, cfg["population"])]
        rank_of = {space.key(ok[i]["genotype"]): rk[i] for i in range(len(ok))}
        nxt: list[dict] = []
        tries = 0
        while len(nxt) < cfg["population"] and tries < 200:
            tries += 1
            if len(nxt) == cfg["population"] - 1 and rng.random() < 0.5:
                child = space.sample(rng.choice(families), rng)               # fresh blood against stagnation
            else:
                a, b = (min(rng.sample(elite, 2) if len(elite) > 1 else elite * 2, key=lambda g: rank_of.get(space.key(g), 9)) for _ in range(2))
                child = space.crossover(a, b, rng) if a["family"] == b["family"] and rng.random() < 0.4 else space.mutate(a, rng)
            if space.key(child) not in seen and child["family"] in families:
                nxt.append(child)
        pop = nxt or initial()

    if stopped == "cancelled":
        return
    ok = [t for t in seen.values() if t["status"] == "ok"]
    if not ok:
        raise DataError("No model could be trained on this data. Check the target column and data quality.")
    objs = [(-t["score"], t["latency_ms"], t["size_kb"]) for t in ok]
    rk = pareto.ranks(objs)
    for t, r in zip(ok, rk):
        t["rank"] = r
    yield {"type": "ranks", "ranks": {t["key"]: t["rank"] for t in ok}}

    front = sorted([t for t in ok if t["rank"] == 0], key=lambda t: -t["score"])
    picks = front[:3]
    for extra in (min(front, key=lambda t: t["latency_ms"]), min(front, key=lambda t: t["size_kb"])):
        if extra not in picks:
            picks.append(extra)
    for t in front:
        if len(picks) >= 6: break
        if t not in picks: picks.append(t)

    full_X = pd.concat([Xtr, Xva]); full_y = pd.concat([ytr, yva])
    if len(full_X) > FINAL_TRAIN_CAP:
        idx = full_X.sample(FINAL_TRAIN_CAP, random_state=seed).index
        full_X, full_y = full_X.loc[idx], full_y.loc[idx]
    base_t = (DummyClassifier(strategy="most_frequent") if task == "classification" else DummyRegressor(strategy="mean")).fit(full_X, full_y)
    baseline_test = float(fn(yte, base_t.predict(Xte)))
    models, best = [], None
    for t in picks:
        pipe = space.build_pipeline(features, t["genotype"], task, seed, len(full_X)).fit(full_X, full_y)
        blob = _dump(pipe)
        preds = pipe.predict(Xte)
        ci = _ci(fn, yte, preds, seed)
        m = {"key": t["key"], "test_score": float(fn(yte, preds)), "latency_ms": _latency_ms_per_1000(pipe, Xte),
             "size_kb": len(blob) / 1024, "blob": blob if len(blob) <= MAX_BLOB else None,
             "ci_low": ci[0] if ci else None, "ci_high": ci[1] if ci else None}
        models.append(m)
        if best is None or m["test_score"] > best[0]["test_score"]:
            best = (m, pipe, preds)
    importance = []
    try:
        Xs = Xte.iloc[:600]; ys = yte.loc[Xs.index]
        pi = permutation_importance(best[1], Xs, ys, scoring=make_scorer(fn), n_repeats=3, random_state=seed, n_jobs=1)
        pairs = sorted(zip(Xs.columns, pi.importances_mean), key=lambda p: -p[1])[:15]
        importance = [{"feature": f, "importance": max(0.0, float(v))} for f, v in pairs]
    except Exception:
        pass
    try:
        diagnostics = _diagnostics(task, yte, best[2], seed)
    except Exception:
        diagnostics = None
    yield {"type": "final", "models": models, "best_key": best[0]["key"], "baseline_test": baseline_test, "importance": importance,
           "diagnostics": diagnostics,
           "features": _feature_meta(X, features), "sklearn_version": sklearn.__version__, "stopped": stopped}
