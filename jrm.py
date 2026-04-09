#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import time
from typing import Callable


_SHEBANG_RE = re.compile(r"\A#![^\n]*(?:\n|$)")
_USE_STRICT_RE = re.compile(r"""^\s*(["'])use strict\1\s*;?""", re.ASCII)
_MODULE_RE = re.compile(r"^\s*(?:import|export)\b", re.MULTILINE)

_UNSAFE_LAYER_MESSAGES = {
    "aes": "AES string encryption is intentionally unsupported.",
    "md5": "MD5 integrity traps are intentionally unsupported.",
    "flatten": "Control-flow flattening is intentionally unsupported.",
    "deadcode": "Dead-code injection is intentionally unsupported.",
    "selfdefend": "Self-defending wrappers are intentionally unsupported.",
    "props": "Property obfuscation is intentionally unsupported.",
    "gzip": "Gzip/base64 bootstrap wrapping is intentionally unsupported.",
}


def _read_source(input_path: pathlib.Path) -> str:
    return input_path.read_text(encoding="utf-8")


def _split_prefix(source: str) -> tuple[str, bool, bool, str]:
    shebang = ""
    remaining = source
    shebang_match = _SHEBANG_RE.match(remaining)
    if shebang_match:
        shebang = shebang_match.group(0)
        remaining = remaining[shebang_match.end() :]

    use_strict = bool(_USE_STRICT_RE.match(remaining))
    is_module = bool(_MODULE_RE.search(remaining))
    return shebang, use_strict, is_module, remaining


def _resolve_terser() -> list[str] | None:
    for candidate in ("npx.cmd", "npx", "terser.cmd", "terser"):
        resolved = shutil.which(candidate)
        if not resolved:
            continue
        if "npx" in pathlib.Path(resolved).name.lower():
            return [resolved, "terser"]
        return [resolved]
    return None


def _run_terser(source: str, *, mangle: bool, is_module: bool) -> str:
    base = _resolve_terser()
    if base is None:
        raise RuntimeError("Unable to find `npx` or `terser` in PATH.")

    command = [
        *base,
        "--compress",
        "passes=2",
        "--ecma",
        "2020",
    ]
    if mangle:
        command.append("--mangle")
    if is_module:
        command.append("--module")

    completed = subprocess.run(
        command,
        input=source.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr_text or "terser returned a non-zero exit code")
    return completed.stdout.decode("utf-8")


def _apply_minify(source: str, *, rename_enabled: bool) -> tuple[str, list[str]]:
    shebang, use_strict, is_module, body = _split_prefix(source)
    minified = _run_terser(body, mangle=rename_enabled, is_module=is_module).strip()
    if use_strict and not _USE_STRICT_RE.match(minified):
        minified = '"use strict";' + minified
    return shebang + minified + "\n", [
        "safe-minify",
        *(["safe-rename"] if rename_enabled else []),
    ]


def _apply_layer(
    layer_name: str,
    transform: Callable[[str], tuple[str, list[str]]],
    current: str,
    *,
    verbose: bool,
) -> tuple[str, list[str]]:
    start = time.perf_counter()
    try:
        updated, applied = transform(current)
        if verbose:
            elapsed = time.perf_counter() - start
            print(f"[apply] {layer_name}: {elapsed:.2f}s")
        return updated, applied
    except Exception as exc:
        if verbose:
            print(f"[skip] {layer_name}: {exc}")
        return current, []


def _log_skipped_layers(args: argparse.Namespace) -> None:
    candidates = {
        "aes": not args.no_aes,
        "md5": (not args.no_md5) and (not args.fast),
        "flatten": (not args.no_flatten) and (not args.fast),
        "deadcode": not args.no_deadcode,
        "selfdefend": not args.no_selfdefend,
        "props": not args.no_props,
        "gzip": not args.no_gzip,
    }
    for key, enabled in candidates.items():
        if enabled and args.verbose:
            print(f"[skip] {key}: {_UNSAFE_LAYER_MESSAGES[key]}")


def _run_pipeline(source: str, args: argparse.Namespace) -> tuple[str, list[str]]:
    current = source
    applied: list[str] = []

    current, layer_list = _apply_layer(
        "minify",
        lambda text: _apply_minify(text, rename_enabled=not args.no_rename),
        current,
        verbose=args.verbose,
    )
    applied.extend(layer_list)
    _log_skipped_layers(args)
    return current, applied


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply production-safe JavaScript transforms. "
            "Anti-analysis layers are intentionally not implemented."
        )
    )
    parser.add_argument("input", help="Input JavaScript file")
    parser.add_argument("-o", "--output", required=True, help="Output JavaScript file")
    parser.add_argument("--no-rename", action="store_true", help="Skip identifier mangling")
    parser.add_argument("--no-aes", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--no-md5", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--no-flatten", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--no-deadcode", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--no-selfdefend", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--no-props", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--no-gzip", action="store_true", help="Accepted for CLI compatibility")
    parser.add_argument("--verbose", action="store_true", help="Print per-layer transform log")
    parser.add_argument("--fast", action="store_true", help="Accepted for CLI compatibility")
    return parser


def _emit_line(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.buffer.write((text + "\n").encode(encoding, errors="replace"))
    sys.stdout.flush()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)
    if not input_path.is_file():
        parser.error(f"Input file not found: {input_path}")

    build_salt = secrets.token_hex(16)
    start = time.perf_counter()

    source = _read_source(input_path)
    transformed, applied = _run_pipeline(source, args)
    output_path.write_text(transformed, encoding="utf-8", newline="\n")

    elapsed = time.perf_counter() - start
    input_size = len(source.encode("utf-8"))
    output_size = len(transformed.encode("utf-8"))

    _emit_line(f"✅ Layers applied: {applied}")
    _emit_line(f"📦 Input: {input_size} bytes → Output: {output_size} bytes")
    _emit_line(f"🔑 Build salt: {build_salt}")
    _emit_line(f"⏱  Time: {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
