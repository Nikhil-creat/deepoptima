"""Model families, genotype sampling / mutation / crossover, estimator + preprocessing builders."""
import json, random
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

FAMILIES = {
    "linear": "Linear / logistic regression",
    "tree": "Decision tree",
    "rf": "Random forest",
    "hgb": "Gradient boosting",
    "mlp": "Neural network (architecture search)",
    "knn": "k-nearest neighbours",
}
SCALED = {"linear", "mlp", "knn"}
WIDTHS = [8, 16, 32, 64, 128]


def _samplers(rng: random.Random) -> dict:
    return {
        "linear": {"reg_log10": lambda: round(rng.uniform(-3, 2), 2), "balanced": lambda: rng.random() < 0.5},
        "tree": {"max_depth": lambda: rng.randint(2, 20), "min_samples_leaf": lambda: rng.randint(1, 30), "balanced": lambda: rng.random() < 0.5},
        "rf": {"n_estimators": lambda: rng.choice([20, 40, 60, 100, 150]), "max_depth": lambda: rng.randint(3, 20),
               "min_samples_leaf": lambda: rng.randint(1, 10), "max_features": lambda: rng.choice(["sqrt", 0.5, 1.0]),
               "balanced": lambda: rng.random() < 0.5},
        "hgb": {"max_iter": lambda: rng.choice([30, 60, 100, 150, 200]), "learning_rate": lambda: round(10 ** rng.uniform(-1.7, -0.5), 4),
                "max_depth": lambda: rng.randint(2, 8), "l2": lambda: rng.choice([0.0, 0.01, 0.1, 1.0])},
        "mlp": {"hidden": lambda: [rng.choice(WIDTHS) for _ in range(rng.randint(1, 3))], "activation": lambda: rng.choice(["relu", "tanh"]),
                "alpha_log10": lambda: round(rng.uniform(-6, -2), 2), "lr_log10": lambda: round(rng.uniform(-3.5, -1.5), 2),
                "max_iter": lambda: rng.choice([80, 120, 200])},
        "knn": {"k": lambda: rng.randint(1, 30), "weights": lambda: rng.choice(["uniform", "distance"])},
    }


def sample(family: str, rng: random.Random) -> dict:
    return {"family": family, "params": {k: f() for k, f in _samplers(rng)[family].items()}}


def key(g: dict) -> str:
    return json.dumps(g, sort_keys=True)


def mutate(g: dict, rng: random.Random) -> dict:
    fam, p = g["family"], json.loads(json.dumps(g["params"]))
    s = _samplers(rng)[fam]
    n = 1 + (rng.random() < 0.4)
    for k in rng.sample(list(s), min(n, len(s))):
        if fam == "mlp" and k == "hidden":
            h = list(p["hidden"])
            op = rng.choice(["grow", "shrink", "resize"])
            if op == "grow" and len(h) < 3: h.append(rng.choice(WIDTHS))
            elif op == "shrink" and len(h) > 1: h.pop(rng.randrange(len(h)))
            else: h[rng.randrange(len(h))] = rng.choice(WIDTHS)
            p["hidden"] = h
        else:
            p[k] = s[k]()
    return {"family": fam, "params": p}


def crossover(a: dict, b: dict, rng: random.Random) -> dict:
    p = {k: (a["params"][k] if rng.random() < 0.5 else b["params"][k]) for k in a["params"]}
    return {"family": a["family"], "params": p}


def make_estimator(g: dict, task: str, seed: int, n_train: int):
    f, p, clf = g["family"], g["params"], task == "classification"
    if f == "linear":
        cw = "balanced" if (clf and p.get("balanced")) else None            # helps imbalanced classes
        return LogisticRegression(C=10 ** (-p["reg_log10"]), max_iter=300, class_weight=cw) if clf else Ridge(alpha=10 ** p["reg_log10"])
    if f == "tree":
        c = DecisionTreeClassifier if clf else DecisionTreeRegressor
        kw = {"class_weight": "balanced"} if (clf and p.get("balanced")) else {}
        return c(max_depth=p["max_depth"], min_samples_leaf=p["min_samples_leaf"], random_state=seed, **kw)
    if f == "rf":
        c = RandomForestClassifier if clf else RandomForestRegressor
        kw = {"class_weight": "balanced"} if (clf and p.get("balanced")) else {}
        return c(n_estimators=p["n_estimators"], max_depth=p["max_depth"], min_samples_leaf=p["min_samples_leaf"],
                 max_features=p["max_features"], n_jobs=1, random_state=seed, **kw)
    if f == "hgb":
        c = HistGradientBoostingClassifier if clf else HistGradientBoostingRegressor
        return c(max_iter=p["max_iter"], learning_rate=p["learning_rate"], max_depth=p["max_depth"],
                 l2_regularization=p["l2"], early_stopping=False, random_state=seed)
    if f == "mlp":
        c = MLPClassifier if clf else MLPRegressor
        return c(hidden_layer_sizes=tuple(p["hidden"]), activation=p["activation"], alpha=10 ** p["alpha_log10"],
                 learning_rate_init=10 ** p["lr_log10"], max_iter=p["max_iter"],
                 early_stopping=not clf,                 # sklearn's early stopping breaks on text class labels
                 random_state=seed)
    if f == "knn":
        c = KNeighborsClassifier if clf else KNeighborsRegressor
        return c(n_neighbors=max(1, min(p["k"], n_train - 1)), weights=p["weights"])
    raise ValueError(f"unknown family {f}")


def build_pipeline(features: list[dict], g: dict, task: str, seed: int, n_train: int) -> Pipeline:
    num = [f["name"] for f in features if f["kind"] == "numeric"]
    cat = [f["name"] for f in features if f["kind"] == "categorical"]
    parts = []
    if num:
        steps = [("imp", SimpleImputer(strategy="median"))]
        if g["family"] in SCALED:
            steps.append(("sc", StandardScaler()))
        parts.append(("num", Pipeline(steps), num))
    if cat:
        parts.append(("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                                       ("oh", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=2,
                                                            max_categories=30, sparse_output=False))]), cat))
    prep = ColumnTransformer(parts, remainder="drop", verbose_feature_names_out=False)
    return Pipeline([("prep", prep), ("model", make_estimator(g, task, seed, n_train))])


def describe(g: dict) -> str:
    p = g["params"]
    f = g["family"]
    if f == "mlp": return f"MLP {'-'.join(map(str, p['hidden']))} · {p['activation']}"
    bal = " · balanced" if p.get("balanced") else ""
    if f == "rf": return f"Random forest · {p['n_estimators']} trees · depth {p['max_depth']}{bal}"
    if f == "hgb": return f"Boosting · {p['max_iter']} iters · depth {p['max_depth']} · lr {p['learning_rate']}"
    if f == "tree": return f"Tree · depth {p['max_depth']}{bal}"
    if f == "knn": return f"kNN · k={p['k']}"
    return f"Linear · reg 10^{p['reg_log10']}{bal}"
