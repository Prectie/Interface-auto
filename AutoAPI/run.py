from __future__ import annotations

import argparse
import sys
from pathlib import Path

from Core.repository import YamlRepository
from Exceptions.AutoApiException import AutoApiException


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="AutoAPI")
    parser.add_argument(
        "--data",
        dest="data_root",
        default="Data",
        help="YAML 资产目录，默认 Data",
    )

    subparsers = parser.add_subparsers(dest="command")
    validate_parser = subparsers.add_parser("validate", help="加载并基础校验 P0 YAML 资产")
    validate_parser.add_argument(
        "--data",
        default=None,
        help="YAML 资产目录，默认使用全局 --data 或 Data",
    )
    return parser


def validate(data_dir: str) -> int:
    repo = YamlRepository(Path(data_dir))
    repo.load()

    ids = repo.list_ids()
    print("AutoAPI validate passed")
    print(f"apis: {len(ids['apis'])}")
    print(f"cases: {len(ids['cases'])}")
    print(f"scenarios: {len(ids['scenarios'])}")
    print(f"plans: {len(ids['plans'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        try:
            return validate(args.data or args.data_root)
        except AutoApiException as exc:
            print(exc, file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"AutoAPI validate failed: {exc}", file=sys.stderr)
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
