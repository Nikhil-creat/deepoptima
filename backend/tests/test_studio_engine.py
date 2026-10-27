import io, random
import numpy as np, pandas as pd
import pytest
from sklearn.datasets import load_diabetes, load_wine
from app.studio.engine import codegen, pareto, profile, search, space


def wine_csv(nan=True, cat=True) -> bytes:
    d = load_wine(as_frame=True)
    df = d.frame.copy()
    df["target"] = d.target_names[df.pop("target")]
    if cat:
        df["region"] = np.random.RandomState(0).choice(["north", "south", "east", "west"], len(df))
    if nan:
        df.loc[df.sample(frac=0.05, random_state=1).index, "alcohol"] = np.nan
        df.loc[df.sample(frac=0.05, random_state=2).index, "region"] = np.nan
    df["row id"] = [f"id{i}" for i in range(len(df))]                # ID-like text column -> must be ignored
    return df.to_csv(index=False).encode()


def test_profile_and_kinds():
    df = profile.read_csv(wine_csv(), 50000, 100)
    p = profile.profile_frame(df)
    kinds = {c["name"]: c["kind"] for c in p["columns"]}
    assert kinds["alcohol"] == "numeric" and kinds["region"] == "categorical" and kinds["row id"] == "ignored"
    tgt = {t["name"]: t for t in p["targets"]}
    assert tgt["target"]["task_hint"] == "classification" and tgt["target"]["usable"]
    assert any("row id" in w for w in p["warnings"])
    back = profile.from_gz(profile.to_gz(df), p)
    assert back.shape == df.shape and back["region"].isna().sum() == df["region"].isna().sum()


@pytest.mark.parametrize("bad,msg", [(b"", "empty"), (b"a,b\n1,2\n", "30 rows"), (b"onlyonecolumn\n" + b"1\n" * 40, "2 columns")])
def test_bad_files(bad, msg):
    with pytest.raises(profile.DataError, match=msg):
        profile.read_csv(bad, 1000, 100)


def test_row_and_col_limits():
    big = pd.DataFrame(np.random.rand(200, 3), columns=list("abc")).to_csv(index=False).encode()
    with pytest.raises(profile.DataError, match="more than"):
        profile.read_csv(big, 100, 10)
    wide = pd.DataFrame(np.random.rand(50, 12)).to_csv(index=False).encode()
    with pytest.raises(profile.DataError, match="columns"):
        profile.read_csv(wide, 1000, 5)


def run(df, target, task, metric, **kw):
    p = profile.profile_frame(df)
    feats = [c for c in p["columns"] if c["name"] != target and c["kind"] != "ignored"]
    cfg = dict(task=task, metric=metric, families=list(space.FAMILIES), generations=2, population=6, time_limit_s=60,
               test_size=0.2, seed=7, **kw)
    return list(search.search_iter(df, target, feats, cfg))


def test_classification_end_to_end():
    df = profile.read_csv(wine_csv(), 50000, 100)
    ev = run(df, "target", "classification", "accuracy")
    kinds = [e["type"] for e in ev]
    assert kinds[0] == "info" and kinds[-1] == "final" and "ranks" in kinds
    trials = [e for e in ev if e["type"] == "trial"]
    assert len({e["family"] for e in trials}) >= 4
    final = ev[-1]
    assert final["models"] and all(m["blob"] for m in final["models"])
    best = max(m["test_score"] for m in final["models"])
    assert best > final["baseline_test"] + 0.2                          # clearly beats the majority-class baseline
    import joblib
    pipe = joblib.load(io.BytesIO(next(m for m in final["models"] if m["key"] == final["best_key"])["blob"]))
    row = df.drop(columns=["target", "row id"]).head(3)
    assert len(pipe.predict(row)) == 3
    unseen = row.copy(); unseen["region"] = "mars"
    assert len(pipe.predict(unseen)) == 3                               # unseen category must not crash
    assert final["importance"] and final["features"]


def test_regression_end_to_end():
    d = load_diabetes(as_frame=True); df = d.frame.copy()
    df = profile.read_csv(df.to_csv(index=False).encode(), 50000, 100)
    ev = run(df, "target", "regression", "r2")
    final = ev[-1]
    assert max(m["test_score"] for m in final["models"]) > final["baseline_test"] + 0.2


def test_cancel_stops_without_final():
    df = profile.read_csv(wine_csv(), 50000, 100)
    p = profile.profile_frame(df)
    feats = [c for c in p["columns"] if c["name"] != "target" and c["kind"] != "ignored"]
    n = {"i": 0}
    def cancel():
        n["i"] += 1
        return n["i"] > 3
    cfg = dict(task="classification", metric="accuracy", families=["tree", "rf"], generations=5, population=6, time_limit_s=60, test_size=0.2, seed=1)
    ev = list(search.search_iter(df, "target", feats, cfg, cancel))
    assert ev[-1]["type"] != "final"


def test_time_limit_still_finishes_with_models():
    df = profile.read_csv(wine_csv(), 50000, 100)
    p = profile.profile_frame(df)
    feats = [c for c in p["columns"] if c["name"] != "target" and c["kind"] != "ignored"]
    cfg = dict(task="classification", metric="accuracy", families=["tree", "linear"], generations=50, population=8, time_limit_s=1, test_size=0.2, seed=1)
    ev = list(search.search_iter(df, "target", feats, cfg))
    assert ev[-1]["type"] == "final" and ev[-1]["stopped"] == "time limit"


def test_single_class_target_rejected():
    df = pd.DataFrame({"a": np.arange(60.0), "b": np.arange(60.0) % 7, "y": ["x"] * 60})
    df = profile.read_csv(df.to_csv(index=False).encode(), 1000, 10)
    with pytest.raises(profile.DataError, match="2 classes"):
        run(df, "y", "classification", "accuracy")


def test_pareto_and_space():
    objs = [(0, 1, 1), (1, 0, 1), (1, 1, 0), (2, 2, 2)]
    assert pareto.ranks(objs) == [0, 0, 0, 1]
    assert set(pareto.select(objs, 2)) <= {0, 1, 2}
    rng = random.Random(1)
    for fam in space.FAMILIES:
        g = space.sample(fam, rng)
        m = space.mutate(g, rng)
        assert m["family"] == fam and space.key(m)
        assert space.describe(g)


def test_codegen_compiles():
    s = codegen.predict_script("t", "RF", [{"name": "a", "kind": "numeric"}, {"name": "b", "kind": "categorical"}], "1.8.0", "classification")
    compile(s, "predict.py", "exec")


def test_small_data_uses_cv_and_reports_ci_and_diagnostics():
    df = profile.read_csv(wine_csv(), 50000, 100)
    ev = run(df, "target", "classification", "accuracy")
    assert ev[0]["cv"] is True and any("3 folds" in n for n in ev[0]["notes"])
    final = ev[-1]
    for m in final["models"]:
        assert m["ci_low"] is not None and m["ci_low"] <= m["ci_high"] <= 1.0
    d = final["diagnostics"]
    assert d["kind"] == "confusion" and len(d["labels"]) == 3 and sum(map(sum, d["matrix"])) == ev[0]["n_test"]


def test_regression_diagnostics():
    d = load_diabetes(as_frame=True)
    df = profile.read_csv(d.frame.to_csv(index=False).encode(), 50000, 100)
    final = run(df, "target", "regression", "r2")[-1]
    g = final["diagnostics"]
    assert g["kind"] == "regression" and 0 < len(g["scatter"]) <= 200 and g["rmse"] >= g["mae"] > 0


def test_large_data_uses_single_split():
    rs = np.random.RandomState(0)
    X = rs.rand(2200, 4)
    df = pd.DataFrame(X, columns=list("abcd")); df["y"] = np.where(X[:, 0] + X[:, 1] > 1, "hi", "lo")
    df = profile.read_csv(df.to_csv(index=False).encode(), 50000, 100)
    p = profile.profile_frame(df)
    feats = [c for c in p["columns"] if c["name"] != "y"]
    cfg = dict(task="classification", metric="accuracy", families=["tree", "linear"], generations=1, population=4, time_limit_s=30, test_size=0.2, seed=3)
    ev = list(search.search_iter(df, "y", feats, cfg))
    assert ev[0]["cv"] is False and ev[-1]["type"] == "final"
    assert max(m["test_score"] for m in ev[-1]["models"]) > 0.9


def test_class_balancing_option():
    rng = random.Random(0)
    seen = {space.sample("rf", rng)["params"]["balanced"] for _ in range(40)}
    assert seen == {True, False}
    g = {"family": "tree", "params": {"max_depth": 3, "min_samples_leaf": 2, "balanced": True}}
    assert space.make_estimator(g, "classification", 1, 100).get_params()["class_weight"] == "balanced"
    assert "class_weight" not in space.make_estimator(g, "regression", 1, 100).get_params()
    g2 = {"family": "linear", "params": {"reg_log10": 0.0, "balanced": True}}
    assert space.make_estimator(g2, "regression", 1, 100).__class__.__name__ == "Ridge"      # regression ignores it
