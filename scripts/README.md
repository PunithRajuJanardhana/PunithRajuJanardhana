# Profile artwork

Run the generator from the repository root:

```sh
python3 scripts/generate-artwork.py
```

The generator uses only the Python standard library and writes SVG files into `assets/`. It locates that directory relative to the script, so it can also be run from another working directory.

The generated SVGs are retained as optional profile artwork; the current profile README uses text and does not embed them. Review any changes under `assets/` before committing regenerated files.
