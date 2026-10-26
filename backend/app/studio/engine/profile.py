"""CSV ingestion + column profiling for the tabular AutoML engine."""
import gzip, io, json, re
import numpy as np
import pandas as pd


class DataError(ValueError):
    """Problem with the user's data; message is safe to show to the user."""


def clean_names(cols) -> list[str]:
    seen: set[str] = set()
    out = []
    for i, c in enumerate(cols):
        name = re.sub(r"\s+", " ", str(c)).strip()[:60] or f"col_{i + 1}"
        base, k = name, 2
        while name in seen:
            name = f"{base[:55]}_{k}"
            k += 1
        seen.add(name)
        out.append(name)
    return out


def read_csv(data: bytes, max_rows: int, max_cols: int) -> pd.DataFrame:
    if not data or not data.strip():
        raise DataError("The file is empty.")
    df = None
    for sep in (",", ";", "\t", "|"):
        try:
            cand = pd.read_csv(io.BytesIO(data), sep=sep, nrows=max_rows + 1, encoding_errors="replace",
                               low_memory=False, on_bad_lines="skip")
        except Exception:
            continue
        if df is None:
            df = cand
        if cand.shape[1] >= 2:
            df = cand
            break
    if df is None:
        raise DataError("Could not read this file as CSV. Export it as a comma-separated .csv with a header row.")
    if df.shape[0] > max_rows:
        raise DataError(f"This file has more than {max_rows:,} rows. Please sample it down.")
    df.columns = clean_names(df.columns)
    df = df.dropna(axis=1, how="all")
    if df.shape[1] < 2:
        raise DataError("Need at least 2 columns (features plus the column you want to predict).")
    if df.shape[1] > max_cols:
        raise DataError(f"This file has more than {max_cols} columns. Please remove unneeded columns.")
    if df.shape[0] < 30:
        raise DataError("Need at least 30 rows to train and test a model.")
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_bool_dtype(s) or pd.api.types.is_numeric_dtype(s):
            continue
        s = s.map(lambda v: np.nan if pd.isna(v) else str(v).strip())
        s = s.replace("", np.nan)
        num = pd.to_numeric(s, errors="coerce")
        nn = s.notna().sum()
        df[c] = num if nn and num.notna().sum() >= 0.95 * nn else s
    return df.reset_index(drop=True)


def _kind(s: pd.Series, n: int) -> str:
    nun = s.nunique(dropna=True)
    if nun <= 1:
        return "ignored"
    if pd.api.types.is_bool_dtype(s):
        return "categorical"
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"
    return "categorical" if (nun <= 50 or nun / max(n, 1) <= 0.05) else "ignored"


def _num(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


def profile_frame(df: pd.DataFrame) -> dict:
    n = len(df)
    cols, warnings, targets = [], [], []
    for c in df.columns:
        s = df[c]
        kind = _kind(s, n)
        nun = int(s.nunique(dropna=True))
        miss = round(float(s.isna().mean() * 100), 1)
        info = {"name": c, "kind": kind, "dtype": "number" if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s) else "text",
                "missing_pct": miss, "n_unique": nun,
                "examples": [str(v)[:30] for v in s.dropna().unique()[:5]]}
        if kind == "numeric":
            info.update(min=_num(s.min()), max=_num(s.max()), mean=_num(s.mean()))
        if kind == "ignored":
            warnings.append(f"Column '{c}' is ignored ({'constant' if nun <= 1 else 'too many distinct text values, looks like an ID or free text'}).")
        if miss >= 40:
            warnings.append(f"Column '{c}' is {miss}% empty.")
        cols.append(info)
        is_text = not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)
        hint = "classification" if (is_text or nun <= 15) else "regression"
        usable, reason = True, ""
        if nun < 2: usable, reason = False, "constant column"
        elif miss >= 30: usable, reason = False, f"{miss}% missing"
        elif hint == "classification" and nun > 50: usable, reason = False, "too many classes (max 50)"
        elif kind == "ignored": usable, reason = False, "too many distinct values"
        share = None
        if hint == "classification" and 2 <= nun <= 50:
            share = round(float(s.map(lambda v: "nan" if pd.isna(v) else str(v)).value_counts(normalize=True).min()), 3)
        targets.append({"name": c, "task_hint": hint, "n_unique": nun, "usable": usable, "reason": reason, "min_class_share": share})
    return {"n_rows": n, "n_cols": int(df.shape[1]), "columns": cols, "targets": targets, "warnings": warnings[:12]}


def to_gz(df: pd.DataFrame) -> bytes:
    return gzip.compress(df.to_csv(index=False).encode("utf-8"), compresslevel=6)


def from_gz(blob: bytes, profile: dict) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(gzip.decompress(blob)), low_memory=False)
    for c in profile["columns"]:
        name = c["name"]
        if name not in df.columns:
            continue
        if c["dtype"] == "number" or c["kind"] == "numeric":
            df[name] = pd.to_numeric(df[name], errors="coerce")
        else:
            df[name] = df[name].map(lambda v: np.nan if pd.isna(v) else str(v)).astype(object)
    return df


def preview(df: pd.DataFrame, n: int = 8) -> list[dict]:
    return json.loads(df.head(n).to_json(orient="records"))


def read_rows_csv(data: bytes, max_rows: int = 1000) -> pd.DataFrame:
    """Lenient reader for files to predict on (no minimum row count)."""
    if not data or not data.strip():
        raise DataError("The file is empty.")
    df = None
    for sep in (",", ";", "\t", "|"):
        try:
            cand = pd.read_csv(io.BytesIO(data), sep=sep, nrows=max_rows + 1, encoding_errors="replace", low_memory=False, on_bad_lines="skip")
        except Exception:
            continue
        if df is None:
            df = cand
        if cand.shape[1] >= 2:
            df = cand
            break
    if df is None or df.shape[1] < 1:
        raise DataError("Could not read this file as CSV.")
    if df.shape[0] > max_rows:
        raise DataError(f"At most {max_rows:,} rows can be predicted at once.")
    df.columns = clean_names(df.columns)
    return df.reset_index(drop=True)


def csv_safe(v):
    """Neutralise spreadsheet formula injection in exported text cells."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v
