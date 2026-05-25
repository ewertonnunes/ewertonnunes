"""
Command-line interface.

Usage::

    spec-codegen generate --spec spec.yaml --schema ./spec_schema.py:ProjectSpec \\
                          --files ./files --out ./output
    spec-codegen verify   --spec spec.yaml --schema ./spec_schema.py:ProjectSpec \\
                          --files ./files --lockfile ./lockfile.json
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from spec_codegen.core import Generator
from spec_codegen.lockfile import Lockfile
from spec_codegen.verify import Verifier


def _load_schema(spec: str) -> type:
    """Load a Pydantic model from "path/to/module.py:ClassName"."""
    if ":" not in spec:
        raise SystemExit(f"--schema must be 'path/to/file.py:ClassName', got {spec!r}")
    path_str, cls_name = spec.split(":", 1)
    path = Path(path_str).resolve()
    spec_obj = importlib.util.spec_from_file_location(path.stem, path)
    if spec_obj is None or spec_obj.loader is None:
        raise SystemExit(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec_obj)
    sys.modules[path.stem] = module
    spec_obj.loader.exec_module(module)
    if not hasattr(module, cls_name):
        raise SystemExit(f"class {cls_name!r} not found in {path}")
    cls = getattr(module, cls_name)
    if not isinstance(cls, type):
        raise SystemExit(f"{cls_name!r} is not a class")
    return cls


def _make_generator(args: argparse.Namespace) -> Generator:
    return Generator(
        files_dir=args.files,
        spec_path=args.spec,
        spec_class=_load_schema(args.schema),
    )


def _cmd_generate(args: argparse.Namespace) -> int:
    gen = _make_generator(args)
    result = gen.generate(args.out)
    print(f"generated {result.file_count} files at {result.output_dir}")
    print(f"aggregate hash: {result.aggregate_hash()}")
    if args.write_lockfile:
        Lockfile.from_hashes(result.hashes).write(args.lockfile)
        print(f"wrote {args.lockfile}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    gen = _make_generator(args)
    return Verifier(gen, args.lockfile).run_cli(sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="spec-codegen")
    subs = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--spec", type=Path, required=True)
    common.add_argument(
        "--schema",
        required=True,
        help="path/to/spec_schema.py:ClassName",
    )
    common.add_argument("--files", type=Path, required=True)

    gen = subs.add_parser("generate", parents=[common])
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--write-lockfile", action="store_true")
    gen.add_argument("--lockfile", type=Path, default=Path("lockfile.json"))

    ver = subs.add_parser("verify", parents=[common])
    ver.add_argument("--lockfile", type=Path, default=Path("lockfile.json"))

    args = parser.parse_args(argv)

    if args.cmd == "generate":
        return _cmd_generate(args)
    if args.cmd == "verify":
        return _cmd_verify(args)
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
