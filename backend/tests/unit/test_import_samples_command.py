from pathlib import Path

from app.commands import import_samples
from app.commands.import_samples import (
    DEFAULT_LINE_SAMPLES,
    DEFAULT_STOP_SAMPLES,
    build_parser,
)
from app.services.ingestion import ImportOutcome, ImportStats


def test_default_sample_paths_exist() -> None:
    assert all(path.is_file() for path in [*DEFAULT_STOP_SAMPLES, *DEFAULT_LINE_SAMPLES])


def test_command_accepts_repeated_sample_arguments() -> None:
    args = build_parser().parse_args(
        [
            "--stop",
            "first.json",
            "--stop",
            "second.json",
            "--line",
            "line.json",
            "--city-code",
            "021",
        ]
    )

    assert args.stop == [Path("first.json"), Path("second.json")]
    assert args.line == [Path("line.json")]
    assert args.city_code == "021"


def test_command_returns_nonzero_when_any_import_is_partial(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    sample = tmp_path / "sample.json"
    sample.write_text("{}", encoding="utf-8")

    class FakeService:
        def import_stop_response(self, *args, **kwargs) -> ImportOutcome:  # type: ignore[no-untyped-def]
            return ImportOutcome(
                ingestion_run_id=1,
                status="partial",
                stats=ImportStats(skipped_count=1, failed_count=1),
            )

        def import_line_response(self, *args, **kwargs) -> ImportOutcome:  # type: ignore[no-untyped-def]
            return ImportOutcome(
                ingestion_run_id=2,
                status="success",
                stats=ImportStats(),
            )

    monkeypatch.setattr(import_samples, "IngestionService", FakeService)

    result = import_samples.main(
        ["--stop", str(sample), "--line", str(sample), "--city-code", "021"]
    )

    assert result == 1
