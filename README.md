# jrm.py

`jrm.py` is a small command-line wrapper for production-safe JavaScript transforms.

It currently uses `terser` to:

- minify JavaScript
- optionally mangle identifiers
- preserve shebang handling
- preserve top-level `"use strict"` semantics
- detect ES module input and pass `--module` to `terser`

It does not implement anti-debugging, self-defending, integrity-trap, or encryption-based obfuscation layers.

## Requirements

- Python 3.10+
- Node.js
- `terser`

## Termux Setup

Install the required packages:

```sh
pkg update
pkg install python nodejs
npm install -g terser
```

Verify the tools:

```sh
python --version
node --version
terser --version
```

## Usage

Run with Python:

```sh
python jrm.py input.js -o output.js
```

Or make it executable:

```sh
chmod +x jrm.py
./jrm.py input.js -o output.js
```

## CLI

```text
python jrm.py input.js -o output.js
```

Optional flags:

- `--no-rename` skip identifier mangling
- `--no-aes` accepted for CLI compatibility
- `--no-md5` accepted for CLI compatibility
- `--no-flatten` accepted for CLI compatibility
- `--no-deadcode` accepted for CLI compatibility
- `--no-selfdefend` accepted for CLI compatibility
- `--no-props` accepted for CLI compatibility
- `--no-gzip` accepted for CLI compatibility
- `--verbose` print per-layer transform log
- `--fast` accepted for CLI compatibility

## Output

On completion the script prints:

```text
✅ Layers applied: [...]
📦 Input: X bytes → Output: Y bytes
🔑 Build salt: <hex>
⏱  Time: X.XXs
```

## Examples

Minify and mangle:

```sh
python jrm.py app.js -o app.min.js
```

Minify only:

```sh
python jrm.py app.js -o app.min.js --no-rename
```

Verbose run:

```sh
python jrm.py app.js -o app.min.js --verbose
```

## How It Works

1. Reads the input file as UTF-8.
2. Preserves a shebang line if present.
3. Detects top-level `"use strict"`.
4. Detects whether the file looks like an ES module.
5. Runs `terser` with compression and optional mangling.
6. Restores `"use strict"` when needed.
7. Writes the output file with `\n` line endings.

## Notes

- If `terser` is available in `node_modules/.bin/terser`, `jrm.py` will use that first.
- Otherwise it looks for `npx` or `terser` in `PATH`.
- If `terser` is missing, the script exits with an install hint.

## Troubleshooting

If `jrm.py` is reported as “No command found”, run:

```sh
python jrm.py input.js -o output.js
```

If you want to execute it directly:

```sh
chmod +x jrm.py
./jrm.py input.js -o output.js
```

If `terser` is not found:

```sh
pkg install nodejs
npm install -g terser
```

If a transform fails and `--verbose` is enabled, the script will log the skipped step and keep the previous source unchanged.
