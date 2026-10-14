#!/usr/bin/env python3
"""Evaluate consented measured DB outcomes and atomically save gated JSON only.

Example: python scripts/train_recommender.py --output data/recommender_model.json
No scraped ratings, fabricated outcomes, or artificial production labels are used.
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recommender import InsufficientDataError, train_model
from recommender.engine import validate_model


def load_outcomes():
    from database.fitting import get_training_outcomes

    return get_training_outcomes()


def save_model(artifact, output):
    """No pickle, and no partial artifact becomes visible to serving processes."""
    validate_model(artifact)
    if artifact["quality_gate"] != "passed":
        raise ValueError("Quality gate failed; no model was saved.")
    try:
        output = Path(output).resolve().relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError("Choose an output JSON path within the project working directory.") from exc
    if output.suffix.lower() != ".json":
        raise ValueError("Output must use the .json extension.")
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name("." + output.name + "." + uuid.uuid4().hex + ".pending")
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, allow_nan=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, output)
    finally:
        pending.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Configured local JSON artifact path within the working directory.")
    args = parser.parse_args(argv)
    try:
        outcomes = load_outcomes()
    except Exception:
        print("Cannot load consented fitting outcomes. Check DB_* configuration, database connectivity, "
              "and run the fitting-outcome schema migration. No model was saved.", file=sys.stderr)
        return 1
    try:
        artifact = train_model(outcomes)
        if artifact["quality_gate"] != "passed":
            print("Evaluation quality gate failed. Collect more independent consented measurements "
                  "(including unseen golfers and clubs and multiple clubs per golfer). "
                  "Keep serving the baseline; no model was saved.", file=sys.stderr)
            print(json.dumps(artifact["evaluation"], allow_nan=False, sort_keys=True), file=sys.stderr)
            return 2
        save_model(artifact, args.output)
    except (InsufficientDataError, ValueError, OSError) as exc:
        print(f"Training not published: {exc}", file=sys.stderr)
        return 2
    print(f"Saved quality-gated JSON model to {args.output}. "
          f"Heldout MAE: {artifact['residual_mae']:.4f} proxy utility units "
          "(not calibrated confidence or causal efficacy).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
