# yearbook_1980

The Clarion yearbooks of Divine Child High School (Dearborn, Michigan),
digitized: page scans turned into slideshow videos and an interactive web
site, with every photo extracted, AI-colorized, upscaled, and cataloged
with its caption. The site hosts multiple years — currently the 1980 and
1981 Clarions.

## Layout

| Folder | Contents |
|---|---|
| `src/` | Video pipeline: page cleanup (deskew, glare removal), AI colorization, page-turn transitions, soundtrack muxing -> MP4 (see `src/README.md`) |
| `site_prep/` | Photo extraction: detects photos on each page, OCRs captions, colorizes and upscales each one, builds the web app (see `site_prep/README.md`) |
| `output/site/` | **The deployable static web site** — a landing page plus one self-contained folder per book (`1980/`, `1981/`), each with the app, `catalog.json`, and all images. Serve or host this folder as-is. |

The 1981 book's images are produced by the pipeline copy in the sibling
`1981 yearbook` project folder and copied into `output/site/1981/` here.

Raw page scans, pipeline caches, and audio/video renders are kept out of
the repo (see `.gitignore`); the site folder is self-contained.

## Deploy (Render Static Site)

- Publish directory: `output/site`
- Build command: none

## Local preview

```
python -m http.server 8123 --directory "output/site"
```
