# Recurly Mintlify documentation

This site migrates the supplied `recurly-docs-1.0` export into Mintlify. The source export is preserved in `scripts/source-assets/recurly-docs-1.0.tar.gz`; `scripts/build_docs.py` generates 714 MDX pages, navigation, the OpenAPI spec, and `parity-manifest.json` from it. `index.mdx`, `api-reference.mdx`, and `resources.mdx` are authored landing pages.

## Stylesheet

`custom.css` starts with every byte of the supplied `recurly-docs-global-styles.css`, in its original order. Mintlify-specific styles follow it. An unchanged copy is at `scripts/source-assets/recurly-docs-global-styles.css.txt`; its `.txt` extension prevents Mintlify from loading the same CSS twice. To confirm the source rules remain intact:

```sh
python3 - <<'PY'
from pathlib import Path
source = Path('scripts/source-assets/recurly-docs-global-styles.css.txt').read_bytes()
assert Path('custom.css').read_bytes().startswith(source)
print(f'All {len(source):,} original CSS bytes are present')
PY
```

## Rebuild and preview

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/build_docs.py
mint validate
mint broken-links
mint dev
```

The build script replaces the generated `guides/`, `reference/`, `recipes/`, and `custom-pages/` directories, plus `docs.json`, `openapi/recurly-v2.yaml`, and `parity-manifest.json`. Keep hand-authored changes in the landing pages and `custom.css`. Run the build before starting `mint dev` to avoid flooding the preview watcher with file changes.
