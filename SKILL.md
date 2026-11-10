---
name: site-tour
description: Record a smooth, cursor-visible MP4 tour of a public website URL (scroll, hovers, safe presses, canvas effects) on a GPU-less Linux machine. Use when asked to "record this site", "site tour" or "screen record <url>".
---

# Site Tour

Records a public website as a video that a person would want to watch: it waits for the loader, scrolls top to bottom, shows hover and press states on buttons and cards, plays with interactive canvases (particle logos, WebGL), and ends on the footer. It never clicks, buys, submits or sends anything.

This recipe is proven: it produced a 1 minute 51 second, 1280x800 tour of shifatmasud-framer.vercel.app on a cloud VM with no graphics card, with a 1440x900 master kept alongside.

## Triggers

- "record this site <url>", "site tour <url>", "screen record <url>", "make a video of my website"
- Input: one public URL (http or https). Pages behind a login are out of scope.

## What is in this folder

- **site_tour.py**: the whole pipeline. `--probe` inspects a page; a normal run records, encodes and checks.
- **setup.sh**: installs Xvfb, ffmpeg, Playwright with Chromium, and Pillow on Ubuntu or Debian.
- **examples/shifatmasud_framer_tour.py**: the exact hand-tuned script used for the first successful recording. Copy its structure when a site needs its own choreography.

## How the capture works (keep these choices)

1. **Virtual display**: Xvfb at width x (height + 200), 24-bit.
2. **Real, headed Chromium** through Playwright in `--app` mode (no tabs or address bar), `no_viewport=True`, window sized so the page is exactly 1440x900. The script calibrates where the viewport sits on screen by painting it red and grabbing one frame.
3. **GPU flags**: `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist` plus **`--disable-gpu-compositing`**. In the first site's test, without that last flag the hero ran at 15 fps and card hovers at 5 fps; with it, about 42 fps throughout.
4. **Capture**: `ffmpeg -f x11grab -draw_mouse 0 -framerate 30 -video_size 1440x900 -i :N.0+X,Y -c:v libx264 -preset ultrafast -crf 16`. Stop it by writing `q` to its stdin so the file closes cleanly.
5. **Visible pointer**: recordings never show the real cursor, so an SVG arrow and an orange press ring are injected with `add_init_script` and kept on top of loaders with a MutationObserver.
6. **Human motion**: eased glides (cubic in-out, 12 ms steps), wheel scrolling at about 900 px per second that slows near the target, figure paths over cards, circles and fast swipes over canvases.

## Steps

1. **Setup once**: `bash setup.sh` (skip what is already installed).
2. **Probe**: `python3 site_tour.py URL --probe`. Read the printed list and the top and bottom screenshots in the run folder. Look for:
   - a loader flag the page sets when ready (the probe lists `window.__*Done` style flags). Pass it as `--ready-js "window.__shPreDone===1"` or similar.
   - canvases, cards, the main call-to-action buttons, the footer.
   - anything marked DANGER (buy, pay, checkout, submit, send, delete, sign in, forms). Those are hover-only.
   - no cart, checkout or form on the page: say so later rather than inventing one.
3. **Record**: `python3 site_tour.py URL [--ready-js EXPR] [--max-seconds 120]`. The generic tour works on most sites. For a showcase site, write a custom choreography by copying `examples/shifatmasud_framer_tour.py`: target elements by stable selectors (for Framer sites, `[data-framer-name="..."]`), give each interactive section its moment, and end on the footer.
4. **Encode**: the script keeps a CRF 20 master at full size and makes a delivery copy at 1280 wide. It tries CRF 21 first and falls back to a 2-pass bitrate sized to stay under `--max-mb` (default 9.5, for a 10 MB chat limit).
5. **Verify** before delivering (the script writes `report.json` and `contact_sheet.jpg`):
   - `decode_ok` is true (a full ffmpeg decode with no errors).
   - `reached_bottom` is true, and the last frame is not blank.
   - look at the contact sheet: loader or hero first, footer last, pointer visible.
   - `blocked` lists anything the safety net stopped. If it is not empty, mention it.
6. **Deliver the actual video file** to the user (attach or upload it, not a file path). Offer the sharper master if it is bigger than the limit.

## Safety rules

- Never click. A press is held about 0.8 seconds to show the pressed state, then released away from the element.
- After the page is ready, the script blocks other-document navigation, non-GET document requests (form posts) and popups.
- No purchases, sign-ins, form fills, messages, downloads or cookie-wall acceptance beyond what is needed to see the page.
- Public pages only. Do not record pages with personal data.

## Honest reporting

Tell the user, in a few lines: length and resolution, what the tour covered from top to bottom, anything not found (for example "no cart on the page"), that there is no sound, that the arrow is an added pointer, and that motion can look slightly less smooth than on a real device because the machine renders without a GPU. Mention the master if you compressed the delivery copy.

## Troubleshooting

- **Black or wrong-offset video**: re-run; calibration prints `viewport on screen X Y W H`. It should match the page size.
- **Choppy WebGL**: confirm `--disable-gpu-compositing` is present; lower to 1280x800 with `--width 1280 --height 800`.
- **Loader never finishes**: probe with a longer wait, or pass a `--ready-js` that checks for a hero element.
- **Scroll-jacked pages** (Lenis, Locomotive): wheel scrolling is used on purpose because those libraries ignore `scrollTo`. If the page does not move, the script stops trying after a short time.
- **Over the size limit**: lower `--max-seconds`, or `--deliver-width 1024`.
