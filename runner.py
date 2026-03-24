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
    from backend.api.routes import app

    log = _configure_logging(args.log_level)
    log.info(
        "Starting API server on {}:{} (reload={})",
        args.host,
        args.port,
        args.reload,
    )

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


def _run_pipeline(args: argparse.Namespace) -> None:
    import yaml

    log = _configure_logging(args.log_level)
    log.info(
        "Running pipeline with input={}, format={}, config={}, output={}",
        args.input,
        args.input_format,
        args.config,
        args.output,
    )

    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config file not found: {}", config_path)
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        config_data = yaml.safe_load(handle) or {}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Placeholder until pipeline orchestration is implemented.
    output_path.write_text(
        "Pipeline scaffold executed.\n"
        f"input={args.input}\n"
        f"format={args.input_format}\n"
        f"config_sources={list((config_data.get('sources') or {}).keys())}\n",
        encoding="utf-8",
    )
    log.info("Pipeline run completed. Wrote {}", output_path)


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
        default="csv",
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
        default="output/run_summary.txt",
        help="Path to pipeline summary output.",
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
