"""Command-line entry point for importing the three local JSON samples."""

import argparse
from pathlib import Path

from app.db.session import SessionFactory
from app.services.ingestion import import_samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入高德和上海公交 JSON 样例")
    parser.add_argument("amap_stop", type=Path, help="高德站点 JSON")
    parser.add_argument("amap_line", type=Path, help="高德线路 JSON")
    parser.add_argument("shanghai", type=Path, help="上海实时 JSON")
    args = parser.parse_args(argv)

    with SessionFactory() as session:
        try:
            runs = import_samples(session, args.amap_stop, args.amap_line, args.shanghai)
        except Exception as exc:
            parser.error(f"导入失败: {exc}")
            return 2
    for run in runs:
        print(
            f"run={run.id} source={run.source} status={run.status} "
            f"received={run.received_count} inserted={run.inserted_count} "
            f"updated={run.updated_count} errors={run.error_message or '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
