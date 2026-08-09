#!/usr/bin/env python3
"""Dynamic test data generator for ETL performance testing.

Generates synthetic CSV files with configurable row counts matching the
temperaturas schema used by the ETL pipeline.
"""

from __future__ import annotations

import argparse
import csv
import random
import unicodedata
from datetime import date
from pathlib import Path


def normalize_key(cidade: str) -> str:
    """Normalize a city name into a partition-safe key.

    This implementation matches transforms.csv_to_parquet.normalize_city_key()
    exactly. Applies, in order:
      1. NFKD decomposition to split accented characters into base letter +
         combining diacritical mark;
      2. Removal of all combining characters (accents, tildes, cedillas, ...);
      3. Lowercasing.

    Examples::

        >>> normalize_key("Florianopolis")
        'florianopolis'
        >>> normalize_key("Chapeco")
        'chapeco'
        >>> normalize_key("Criciuma")
        'criciuma'
        >>> normalize_key("Blumenau")
        'blumenau'
    """
    nfkd = unicodedata.normalize("NFKD", cidade)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# 6 cities from SC-Brazil temperature monitoring
CITIES = [
    "Florianopolis",
    "Joinville",
    "Blumenau",
    "Chapeco",
    "Lages",
    "Criciuma",
]


def generate_row(cidade: str, data_medicao: str) -> dict:
    """Generate a single temperature record.

    Args:
        cidade: City name (preserved as-is in the CSV).
        data_medicao: Measurement date in YYYY-MM-DD format.

    Returns:
        Dictionary with cidade, cidade_key, data_medicao, temp_min, temp_max.
    """
    cidade_key = normalize_key(cidade)
    temp_min = round(random.uniform(10.0, 25.0), 1)
    temp_max = round(random.uniform(20.0, 35.0), 1)
    # Ensure temp_max >= temp_min, capped at 35.0
    if temp_max < temp_min:
        temp_max = round(temp_min + random.uniform(0.0, 10.0), 1)
        if temp_max > 35.0:
            temp_max = 35.0
    return {
        "cidade": cidade,
        "cidade_key": cidade_key,
        "data_medicao": data_medicao,
        "temp_min": temp_min,
        "temp_max": temp_max,
    }


def generate_csv(output_path: str, rows: int, data_medicao: str = "2026-01-15") -> None:
    """Generate a CSV file with synthetic temperature data.

    Args:
        output_path: Path to write the CSV file.
        rows: Number of data rows to generate.
        data_medicao: Measurement date in YYYY-MM-DD format.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["cidade", "cidade_key", "data_medicao", "temp_min", "temp_max"],
        )
        writer.writeheader()
        for _ in range(rows):
            cidade = random.choice(CITIES)
            writer.writerow(generate_row(cidade, data_medicao))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic CSV test data for ETL performance testing."
    )
    parser.add_argument(
        "--rows",
        type=int,
        required=True,
        help="Number of data rows to generate (required, positive integer).",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to write the CSV file (required).",
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2026-01-15",
        help="Measurement date in YYYY-MM-DD format (default: 2026-01-15).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional).",
    )

    args = parser.parse_args()

    # Set random seed if provided for reproducibility
    if args.seed is not None:
        random.seed(args.seed)

    # Validate rows (mitigates T-06-02: DoS via huge row count)
    if args.rows <= 0:
        raise ValueError("--rows must be a positive integer (max recommended: 10000000).")

    # Validate date format
    try:
        date.fromisoformat(args.date)
    except ValueError as e:
        raise ValueError(f"--date must be in YYYY-MM-DD format: {e}")

    generate_csv(args.output, args.rows, args.date)
    print(f"Generated {args.rows} rows -> {args.output}")


if __name__ == "__main__":
    main()
