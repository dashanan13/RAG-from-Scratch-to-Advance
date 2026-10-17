"""Stage 10 - Evaluation dataset: load labeled questions and gold evidence.

Reads the labeled question set produced in `experiments/00` and grown in
`experiments/10`.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_questions(artifacts: Path) -> dict:
    """Return ``{'development': [...], 'heldout': [...]}`` from eval-questions.json."""
    path = Path(artifacts) / "eval-questions.json"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}. Run notebook 00 to label the question set first.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "development": list(payload.get("development", [])),
        "heldout": list(payload.get("heldout", [])),
    }
