import argparse
import sys
from datetime import datetime
from pathlib import Path

def _configure_logging(level: str):
    from loguru import logger

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"propintel_{timestamp}.log"

    logger.remove()
    logger.add(
        log_file,
        level=level.upper(),
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.add(
        sink=sys.stderr,
        level=level.upper(),
    )
    return logger


def _run_api(args: argparse.Namespace) -> None:
    import uvicorn

    log = _configure_logging(args.log_level)
    log.info(
        "Starting API server on {}:{} (reload={})",
        args.host,
        args.port,
        args.reload,
    )

    # Uvicorn requires an import string (not an app object) to enable reload/workers.
    app_target: str | object
    if args.reload:
        app_target = "backend.api.routes:app"
    else:
        from backend.api.routes import app

        app_target = app

    uvicorn.run(
        app_target,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


def _run_pipeline(args: argparse.Namespace) -> None:
    log = _configure_logging(args.log_level)

    input_format = args.input_format
    if input_format is None:
        suffix = Path(args.input).suffix.lower()
        if suffix == ".json":
            input_format = "json"
        elif suffix == ".csv":
            input_format = "csv"
        else:
            input_format = "csv"

    log.info(
        "Running pipeline with input={}, format={}, config={}, output={}",
        args.input,
        input_format,
        args.config,
        args.output,
    )

    from backend.core.ingestion import run_ingestion

    # Create a dedicated timestamped folder for all artifacts from this run.
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output) / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)
    output_summary_path = run_dir / f"run_summary_{run_ts}.json"

    summary = run_ingestion(
        input_path=args.input,
        input_format=input_format,
        config_path=args.config,
        output_summary_path=output_summary_path,
    )

    log.info(
        "Ingestion completed (run_dir={}, deduped_rows={}, rejected_rows={})",
        str(run_dir),
        summary["counts"]["deduped_rows"],
        summary["counts"]["rejected_rows"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PropIntel CLI: run API server or local pipeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    api_parser = subparsers.add_parser("api", help="Start FastAPI server.")
    api_parser.add_argument("--host", default="127.0.0.1", help="API bind host.")
    api_parser.add_argument("--port", type=int, default=8000, help="API bind port.")
    api_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )
    api_parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level.",
    )
    api_parser.set_defaults(func=_run_api)

    run_parser = subparsers.add_parser("run", help="Run local enrichment pipeline.")
    run_parser.add_argument(
        "--input",
        required=True,
        help="Path to input file (CSV, JSON, or PropFlux export).",
    )
    run_parser.add_argument(
        "--input-format",
        default=None,
        choices=["csv", "json", "propflux"],
        help="Input format type.",
    )
    run_parser.add_argument(
        "--config",
        default="config/sources.yaml",
        help="Path to source configuration YAML.",
    )
    run_parser.add_argument(
        "--output",
        default="output",
        help="Base output directory (a timestamped subfolder will be created).",
    )
    run_parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Pipeline log level.",
    )
    run_parser.set_defaults(func=_run_pipeline)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
