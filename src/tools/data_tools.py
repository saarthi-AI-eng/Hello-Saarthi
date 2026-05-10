"""
Data Analysis Tools — sandboxed pandas/numpy tools for the Data Analysis Agent.

All tools operate on CSVs in the UPLOAD_DIR (temp_data/).
Completely isolated: if these tools fail, no other agent is affected.
"""

import os
import io
import contextlib
import traceback
from pathlib import Path
from typing import Optional
import logging

import pandas as pd
import numpy as np
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("temp_data")


# ─── Helper ──────────────────────────────────────────────────

def _load_df(filename: str) -> pd.DataFrame:
    """Loads a CSV from the upload directory. Raises FileNotFoundError if missing."""
    path = UPLOAD_DIR / filename
    if not path.exists():
        available = [f.name for f in UPLOAD_DIR.glob("*.csv")]
        raise FileNotFoundError(
            f"'{filename}' not found. Available datasets: {available}"
        )
    return pd.read_csv(path)


def _safe_exec(code: str, df: pd.DataFrame) -> str:
    """
    Executes pandas/numpy code in a restricted namespace.
    `df` is the pre-loaded DataFrame. `pd` and `np` are available.
    Returns captured stdout as a string.
    """
    namespace = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
    }
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {"__builtins__": {"print": print, "len": len, "range": range,
                                          "int": int, "float": float, "str": str,
                                          "list": list, "dict": dict, "tuple": tuple,
                                          "round": round, "abs": abs, "sum": sum,
                                          "min": min, "max": max, "sorted": sorted,
                                          "enumerate": enumerate, "zip": zip,
                                          "True": True, "False": False, "None": None,
                                          "isinstance": isinstance, "type": type}},
                 namespace)
        output = buf.getvalue()
        # If no explicit print, check if the last expression produced a result
        if not output.strip():
            # Try to evaluate the last line as an expression
            lines = [l for l in code.strip().split('\n') if l.strip()]
            if lines:
                try:
                    result = eval(lines[-1], {"__builtins__": {}}, namespace)
                    if result is not None:
                        output = str(result)
                except Exception:
                    pass
        return output if output.strip() else "(No output produced)"
    except Exception as e:
        return f"Error executing code:\n{traceback.format_exc()}"


# ─── Tools ───────────────────────────────────────────────────

@tool
def list_datasets() -> str:
    """Lists all CSV datasets currently uploaded in the session. Use this first to see what data is available."""
    files = sorted(UPLOAD_DIR.glob("*.csv"))
    if not files:
        return "No datasets uploaded yet. Ask the user to upload a CSV file."
    lines = []
    for f in files:
        size_kb = f.stat().st_size / 1024
        lines.append(f"  - {f.name} ({size_kb:.1f} KB)")
    return "Available datasets:\n" + "\n".join(lines)


@tool
def load_dataset(filename: str) -> str:
    """
    Loads a CSV dataset and returns its shape, column names, data types, and first 5 rows.
    Use this to understand the structure of the data before running analyses.
    """
    try:
        df = _load_df(filename)
        info = io.StringIO()
        info.write(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n\n")
        info.write("Columns & Types:\n")
        for col in df.columns:
            info.write(f"  - {col}: {df[col].dtype}")
            nulls = df[col].isna().sum()
            if nulls > 0:
                info.write(f"  ({nulls} missing)")
            info.write("\n")
        info.write(f"\nFirst 5 rows:\n{df.head().to_string()}\n")
        return info.getvalue()
    except Exception as e:
        return f"Error: {e}"


@tool
def get_summary(filename: str) -> str:
    """
    Returns statistical summary of the dataset: describe(), value counts for categorical columns,
    and basic info about missing values. Use this for a quick overview.
    """
    try:
        df = _load_df(filename)
        buf = io.StringIO()

        # Numeric summary
        numeric_desc = df.describe()
        if not numeric_desc.empty:
            buf.write("=== Numeric Summary ===\n")
            buf.write(numeric_desc.to_string())
            buf.write("\n\n")

        # Categorical summary
        cat_cols = df.select_dtypes(include=["object", "category"]).columns
        if len(cat_cols) > 0:
            buf.write("=== Categorical Columns ===\n")
            for col in cat_cols:
                buf.write(f"\n{col} — {df[col].nunique()} unique values:\n")
                buf.write(df[col].value_counts().head(10).to_string())
                buf.write("\n")

        # Missing data
        missing = df.isna().sum()
        if missing.any():
            buf.write("\n=== Missing Values ===\n")
            buf.write(missing[missing > 0].to_string())
            buf.write("\n")

        return buf.getvalue() if buf.getvalue().strip() else "Dataset is empty."
    except Exception as e:
        return f"Error: {e}"


@tool
def get_column_analysis(filename: str, column: str) -> str:
    """
    Returns detailed analysis of a single column: stats, distribution, unique values, outliers.
    Use this when the user asks about a specific variable or column.
    """
    try:
        df = _load_df(filename)
        if column not in df.columns:
            return f"Column '{column}' not found. Available columns: {list(df.columns)}"

        series = df[column]
        buf = io.StringIO()
        buf.write(f"=== Column: {column} ===\n")
        buf.write(f"Type: {series.dtype}\n")
        buf.write(f"Non-null: {series.count()} / {len(series)}\n")
        buf.write(f"Unique values: {series.nunique()}\n\n")

        if pd.api.types.is_numeric_dtype(series):
            buf.write(f"Mean:   {series.mean():.4f}\n")
            buf.write(f"Median: {series.median():.4f}\n")
            buf.write(f"Std:    {series.std():.4f}\n")
            buf.write(f"Min:    {series.min()}\n")
            buf.write(f"Max:    {series.max()}\n")
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            outliers = series[(series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)]
            buf.write(f"Q1:     {q1:.4f}\n")
            buf.write(f"Q3:     {q3:.4f}\n")
            buf.write(f"IQR:    {iqr:.4f}\n")
            buf.write(f"Outliers: {len(outliers)} values\n")
        else:
            buf.write("Top 10 values:\n")
            buf.write(series.value_counts().head(10).to_string())
            buf.write("\n")

        return buf.getvalue()
    except Exception as e:
        return f"Error: {e}"


@tool
def run_analysis(filename: str, code: str) -> str:
    """
    Executes pandas/numpy Python code on a dataset. The DataFrame is pre-loaded as `df`.
    You have access to `pd` (pandas) and `np` (numpy). Use `print()` to show results.

    Examples:
        - "print(df.groupby('signal_type')['amplitude'].mean())"
        - "print(df[df['frequency'] > 100].shape)"
        - "print(df.corr().to_string())"
        - "filtered = df[df['snr'] > 20]; print(filtered.describe())"
    """
    try:
        df = _load_df(filename)
        result = _safe_exec(code, df)
        # Truncate very large outputs
        if len(result) > 3000:
            result = result[:3000] + "\n... (output truncated)"
        return result
    except Exception as e:
        return f"Error: {e}"


# ─── Collect all tools ───────────────────────────────────────

DATA_TOOLS = [list_datasets, load_dataset, get_summary, get_column_analysis, run_analysis]
