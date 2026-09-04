# scripts/utils/validation.py
import pandas as pd
from pathlib import Path

def check_file_exists(path: Path) -> None:
    """Comprueba que el archivo existe y no está vacío."""
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"El archivo {path} está vacío.")

def validate_columns(df: pd.DataFrame, required: set[str]) -> None:
    """Verifica que el DataFrame contenga las columnas requeridas."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")

def validate_not_empty(df: pd.DataFrame, name: str = "DataFrame") -> None:
    """Comprueba que el DataFrame no esté vacío."""
    if df.empty:
        raise ValueError(f"{name} está vacío.")

def validate_datetime(df: pd.DataFrame, col: str) -> None:
    """Asegura que una columna tenga formato datetime válido."""
    if not pd.api.types.is_datetime64_any_dtype(df[col]):
        raise TypeError(f"La columna '{col}' no tiene formato datetime válido.")
    if df[col].isna().any():
        raise ValueError(f"La columna '{col}' contiene valores nulos.")
