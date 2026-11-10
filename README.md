# Site Tour tools

Site Tour records a public website as a smooth MP4 tour with a visible pointer. It waits for the loader, scrolls from top to bottom, shows hover and press states on buttons and cards, plays with interactive canvases, and ends on the footer. It runs on a Linux machine with no graphics card, and it never clicks, buys, submits or sends anything.

This repository holds everything an agent needs to run it: the agent skill instructions, the recording pipeline, the setup script, the hand-tuned script behind the first recording, and the test scripts used while building it.

## What is in this repository

| Path | What it is |
| --- | --- |
| `SKILL.md` | Agent Skills instructions: triggers, steps, safety rules, troubleshooting |
| `site_tour.py` | The full pipeline: probe, record, encode, verify |
| `setup.sh` | Installs Xvfb, ffmpeg, Playwright with Chromium, and Pillow on Ubuntu or Debian |
| `examples/shifatmasud_framer_tour.py` | The exact script that recorded shifatmasud-framer.vercel.app |
| `research/` | Probe, window and frame-rate test scripts used to work out the recipe |

## Give it to another agent

1. Clone or download this repository into the agent's skills folder, for example `skills/site-tour/`. `SKILL.md` follows the common Agent Skills format, so agents that read skills folders pick it up from there.
2. On the agent's Linux machine, run setup once:

```bash
bash setup.sh
```

3. Ask the agent to "record this site" or run a "site tour" with a public URL. It follows `SKILL.md`.

## Run it by hand

Probe the page first. This records nothing: it prints targets, readiness flags, canvases and anything marked DANGER, and saves top and bottom screenshots.

```bash
python3 site_tour.py https://example.com --probe
```

Then record:

```bash
python3 site_tour.py https://example.com --max-seconds 120
```

Useful options:

- `--ready-js "window.__shPreDone===1"`: a JavaScript expression that turns true once the site's loader is done (the probe lists likely flags).
- `--width 1440 --height 900`: page size of the recording.
- `--deliver-width 1280`: width of the smaller delivery copy.
- `--max-mb 9.5`: size cap for the delivery copy.
- `--out DIR`: run folder. The default is `~/site-tour-runs/<site>/`.

Each run folder gets the raw capture, a full-size master, a delivery copy, `report.json`, check frames and `contact_sheet.jpg`. Before you use a video, check that `report.json` shows `decode_ok` and `reached_bottom` as true and `last_frame_blank` as false, and look at the contact sheet.

## How the capture works

- Xvfb virtual display with a real, headed Chromium driven by Playwright in `--app` mode.
- SwiftShader WebGL flags plus `--disable-gpu-compositing`. On the first site, that flag lifted the hero from 15 fps and card hovers from 5 fps to about 42 fps.
- ffmpeg `x11grab` of the page viewport only, at 30 fps, with the real cursor hidden.
- An injected SVG arrow and an orange press ring stand in for the cursor.
- Eased mouse glides and wheel scrolling, so scroll-jacking libraries such as Lenis still move.

`SKILL.md` has the full recipe and the troubleshooting list.

## The original recording script

`examples/shifatmasud_framer_tour.py` is kept exactly as it ran. It is a custom choreography for one Framer site, so copy its structure for other showcase sites rather than running it as is. Before running it:

- Create its output folder with `mkdir -p /tmp/rec`. It writes the raw capture to `/tmp/rec/raw.mp4`.
- It uses display `:99` and a fixed viewport offset (`+0,87`) measured on that machine. If the video is offset or black, measure again (see `research/wtest2.py`) or use `site_tour.py`, which calibrates the offset itself.
- It only records. Encode the master and delivery copy with ffmpeg, or use `site_tour.py`, which does both.

## Research scripts

These are the one-off scripts used while building the recipe. They target shifatmasud-framer.vercel.app and write screenshots to `/tmp` and `/tmp/rec`, so change the URL and paths before reusing them.

- `probe_site.py`, `probe2.py` to `probe6.py`: page structure, Framer element names, canvases, the loader flag, and the scripts behind the footer effect.
- `wtest.py`, `wtest2.py`: window modes and the red-frame calibration of where the viewport sits on screen.
- `fpstest.py`: frame rates under different Chromium GPU flags.

## Safety

- No clicks. A press is held about 0.8 seconds, then released away from the element.
- After the page is ready, the pipeline blocks navigation to other documents, form posts and popups.
- Anything that looks like buy, pay, checkout, submit, send, delete or sign in gets a hover only.
- Public pages only. Do not record pages behind a login or with personal data.

## Limits

- No sound is recorded.
- Motion can look slightly less smooth than on a real device, because the machine renders without a GPU.
- `setup.sh` targets Ubuntu or Debian with `apt-get`.
