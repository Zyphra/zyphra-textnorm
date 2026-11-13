# Copyright (c) 2026 Zyphra, Inc.
# Licensed under the Apache License, Version 2.0

from pathlib import Path
import csv


def get_abs_path(rel_path: str) -> str:
    """Returns absolute path relative to the uk package root."""
    return str(Path(__file__).parent / rel_path)


def load_labels(file_path: str):
    """Loads TSV mapping pairs."""
    labels = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if row and not row[0].startswith("#"):
                labels.append(row)
    return labels
