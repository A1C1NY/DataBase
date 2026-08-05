"""Import the repository's Amap JSON samples into MySQL."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.services.ingestion import ImportOutcome, IngestionError, IngestionService

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STOP_SAMPLES = [
    REPOSITORY_ROOT / "bus_stop_by_name.json",
    REPOSITORY_ROOT / "bus_stop_raw_gaode.json",
]
DEFAULT_LINE_SAMPLES = [REPOSITORY_ROOT / "bus_line_raw_gaode.json"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop", action="append", type=Path, default=None)
    parser.add_argument("--line", action="append", type=Path, default=None)
    parser.add_argument("--city-code", default="021")
    return parser


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} 的 JSON 根节点必须是对象")
    return payload


def _outcome(path: Path, outcome: ImportOutcome) -> dict[str, Any]:
    return {
        "path": str(path),
        "ingestion_run_id": outcome.ingestion_run_id,
        "status": outcome.status,
        "received_count": outcome.stats.received_count,
        "inserted_count": outcome.stats.inserted_count,
        "updated_count": outcome.stats.updated_count,
        "skipped_count": outcome.stats.skipped_count,
        "failed_count": outcome.stats.failed_count,
        "errors": list(outcome.errors),
        "warnings": list(outcome.warnings),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stop_paths = args.stop if args.stop is not None else DEFAULT_STOP_SAMPLES
    line_paths = args.line if args.line is not None else DEFAULT_LINE_SAMPLES
    service = IngestionService()
    results: list[dict[str, Any]] = []
    failed = False

    for path in stop_paths:
        try:
            outcome = service.import_stop_response(
                _read_json(path),
                trigger_type="sample_import",
                request_keyword=path.stem,
                city_code=args.city_code,
            )
            results.append(_outcome(path, outcome))
            failed = failed or outcome.status != "success"
        except (OSError, TypeError, ValueError, IngestionError) as exc:
            results.append({"path": str(path), "status": "failed", "error": str(exc)})
            failed = True

    for path in line_paths:
        try:
            outcome = service.import_line_response(
                _read_json(path),
                trigger_type="sample_import",
                request_keyword=path.stem,
                city_code=args.city_code,
            )
            results.append(_outcome(path, outcome))
            failed = failed or outcome.status != "success"
        except (OSError, TypeError, ValueError, IngestionError) as exc:
            results.append({"path": str(path), "status": "failed", "error": str(exc)})
            failed = True

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
