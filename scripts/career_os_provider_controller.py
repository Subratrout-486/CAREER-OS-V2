#!/usr/bin/env python3
"""GitHub Actions bridge for the provider-neutral Career OS controller."""

from __future__ import annotations

import argparse
from pathlib import Path
import os

from career_os.autonomy.provider_controller import (
    ProviderController,
    ProviderFailure,
    ProviderFailureKind,
    classify_provider_failure,
)


def _controller() -> ProviderController:
    providers = [item.strip() for item in os.environ.get("CAREER_OS_PROVIDERS", "").split(",") if item.strip()]
    if not providers:
        raise SystemExit("no authorized provider names were supplied")
    return ProviderController(Path(os.environ.get("CAREER_OS_STATE", ".career-os/provider-state.json")), providers)


def _set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--departments", required=True)
    failure = subparsers.add_parser("failure")
    failure.add_argument("--provider", required=True)
    failure.add_argument("--message", required=True)
    args = parser.parse_args()

    controller = _controller()
    if args.command == "start":
        controller.start([item.strip() for item in args.departments.split(",") if item.strip()])
        _set_output("provider", controller.choose_provider() or "")
        return 0

    next_provider = controller.record_provider_failure(
        ProviderFailure(args.provider, classify_provider_failure(args.message), args.message)
    )
    _set_output("provider", next_provider or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
