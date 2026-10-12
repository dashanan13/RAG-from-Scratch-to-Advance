"""Stage 10 - Evaluation dataset: load labeled questions and gold evidence.

Reads the labeled question set produced in `experiments/00` and grown in
`experiments/10`.
"""
from __future__ import annotations

from pathlib import Path


def load_questions(artifacts: Path) -> dict:
    """Return ``{'development': [...], 'heldout': [...]}`` from eval-questions.json."""
    raise NotImplementedError("Fill from experiments/10.")
