# kingstonfeet interim site

A temporary static stand-in for kingstonfeet.com while the old WordPress host is in maintenance mode, rebuilt from the public crawl taken on 15 October 2026 (`../kingstonfeet-old-site/2026-10-15/`).

- `docs/` is the published site (GitHub Pages serves this folder from `main`).
- `build/build.py` regenerates `docs/` from the archive: `uv run --with beautifulsoup4 --with pillow python build/build.py`
- `build/site.css` is the only stylesheet. No WordPress, Beaver Builder, jQuery, analytics or tracking code.
- `build/report.json` lists every page title/description, forward and image used.

Text is copied as-is from the archived pages. Outdated pages (COVID, lockdown, hiring, November 2020 images, the "-copy" page, PhysioMore) forward to the homepage; `/category/blog/`, `/author/kfjoanna/` and `/blog/page/2/` forward to `/blog/`.
