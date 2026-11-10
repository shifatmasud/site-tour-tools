#!/usr/bin/env python3
"""Site Tour: record a smooth, cursor-visible video tour of a public website.

Proven recipe (first used on shifatmasud-framer.vercel.app, Nov 10 2026):
  Xvfb virtual display -> headed Chromium (Playwright) in --app mode with SwiftShader
  WebGL and --disable-gpu-compositing (5 fps -> ~42 fps on a GPU-less VM) ->
  ffmpeg x11grab of the page viewport only (-draw_mouse 0) -> injected SVG pointer
  overlay with an orange press ring -> eased mouse glides, wheel scrolling, hovers,
  press-and-drag-off (never a click), canvas sweeps -> lossless-ish master ->
  2-pass H.264 delivery copy sized under the chat limit -> decode + frame checks.

Usage:
  python3 site_tour.py URL [--out DIR] [--probe] [--ready-js EXPR] [--max-seconds 120]
                           [--width 1440 --height 900] [--deliver-width 1280] [--max-mb 9.5]

--probe   only inspects the page (targets, height, canvases, readiness flags) and saves
          top/bottom screenshots; it records nothing. Run it first.

Safety: the tour never clicks. Presses are released off the element, other-document
navigations, form posts and popups are blocked, and anything that looks like
buy/pay/checkout/submit/send/delete/sign-in is hover-only.
"""
import argparse, json, math, os, re, shutil, signal, subprocess, sys, time

from playwright.sync_api import sync_playwright

CHROME_ARGS = [
    "--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--disable-gpu-compositing",  # the big one: software compositing keeps ~40 fps without a GPU
    "--disable-infobars", "--force-device-scale-factor=1", "--hide-scrollbars", "--no-first-run",
    "--autoplay-policy=no-user-gesture-required",
]

CURSOR_JS = r"""
(() => {
  const mk = () => {
    if (document.getElementById('__rec_cursor')) return;
    const c = document.createElement('div');
    c.id = '__rec_cursor';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M3 2 L3 19 L7.6 14.8 L10.6 21.6 L13.6 20.3 L10.7 13.6 L17 13.6 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    c.style.cssText = 'position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);filter:drop-shadow(0 1px 2px rgba(0,0,0,.35));transition:none';
    const ring = document.createElement('div');
    ring.id = '__rec_ring';
    ring.style.cssText = 'position:fixed;left:0;top:0;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;border:2px solid rgba(254,83,3,.9);background:rgba(254,83,3,.15);z-index:2147483646;pointer-events:none;opacity:0;transform:translate(-100px,-100px) scale(.6);transition:opacity .15s, scale .15s';
    document.documentElement.appendChild(ring);
    document.documentElement.appendChild(c);
    const pos = (e) => { const t = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)'; c.style.transform = t; ring.style.transform = t; };
    window.addEventListener('pointermove', pos, true);
    window.addEventListener('pointerdown', (e) => { pos(e); ring.style.opacity = '1'; ring.style.scale = '1'; }, true);
    window.addEventListener('pointerup', () => { ring.style.opacity = '0'; ring.style.scale = '.6'; }, true);
    // keep the overlay above loaders and modals appended later
    new MutationObserver(() => { if (document.documentElement.lastElementChild !== c) { document.documentElement.appendChild(ring); document.documentElement.appendChild(c); } }).observe(document.documentElement, {childList: true});
  };
  if (document.documentElement) mk(); else document.addEventListener('DOMContentLoaded', mk);
})();
"""

DANGER = re.compile(r"\b(buy|pay|checkout|check out|order|purchase|add to (cart|bag|basket)|subscribe|submit|send|post|delete|remove|sign ?(in|up)|log ?(in|out)|register|book|reserve|donate|confirm|accept|download|install)\b", re.I)

DISCOVER_JS = r"""
() => {
  const H = innerHeight, W = innerWidth, sy = scrollY;
  const vis = (e) => { const s = getComputedStyle(e); if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity === 0) return false; const r = e.getBoundingClientRect(); return r.width > 8 && r.height > 8 && r.right > 0 && r.left < W; };
  const out = [];
  const add = (e, kind) => { if (!vis(e) || e.closest('#__rec_cursor')) return; const r = e.getBoundingClientRect(); out.push({kind, x: r.x, y: r.y + sy, w: r.width, h: r.height, text: (e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 60), tag: e.tagName.toLowerCase(), name: e.getAttribute('data-framer-name') || e.id || (typeof e.className === 'string' ? e.className.split(' ')[0] : '') || '', href: e.getAttribute('href') || '', form: !!e.closest('form'), type: e.getAttribute('type') || ''}); };
  document.querySelectorAll('canvas').forEach(e => { const r = e.getBoundingClientRect(); if (r.width >= 240 && r.height >= 160) add(e, 'canvas'); });
  document.querySelectorAll('video').forEach(e => { const r = e.getBoundingClientRect(); if (r.width >= 240) add(e, 'media'); });
  const cardRe = /(card|tile|project|work|item|product|post|feature|case)/i;
  document.querySelectorAll('article, li, a, div, section').forEach(e => {
    const r = e.getBoundingClientRect(); const n = (e.getAttribute('data-framer-name') || '') + ' ' + (typeof e.className === 'string' ? e.className : '');
    if (r.width >= 180 && r.width <= W * 0.72 && r.height >= 160 && r.height <= H * 1.1 && (cardRe.test(n) || e.tagName === 'ARTICLE')) add(e, 'card');
  });
  document.querySelectorAll('button, [role=button], a[href], input[type=submit], summary').forEach(e => { const r = e.getBoundingClientRect(); if (r.width <= W * 0.6 && r.height <= 220) add(e, 'button'); });
  // de-duplicate: drop items mostly inside an earlier, larger item of a stronger kind
  const rank = {canvas: 0, media: 1, card: 2, button: 3};
  out.sort((a, b) => rank[a.kind] - rank[b.kind] || b.w * b.h - a.w * a.h);
  const keep = [];
  for (const o of out) {
    const inside = keep.some(k => { const ix = Math.max(0, Math.min(k.x + k.w, o.x + o.w) - Math.max(k.x, o.x)); const iy = Math.max(0, Math.min(k.y + k.h, o.y + o.h) - Math.max(k.y, o.y)); const ov = ix * iy / (o.w * o.h); return ov > 0.8 && (k.kind === o.kind || (k.kind === 'card' && o.kind === 'button')); });
    if (!inside) keep.push(o);
  }
  keep.sort((a, b) => a.y - b.y || a.x - b.x);
  return {targets: keep, height: document.documentElement.scrollHeight, title: document.title,
          flags: Object.keys(window).filter(k => /^__[A-Za-z]+(Done|Ready|Loaded)$/.test(k) || /(preload|loader).*(done|ready)/i.test(k)).slice(0, 10)};
}
"""


def log(*a):
    print(*a, flush=True)


def free_display():
    for n in range(99, 80, -1):
        if not os.path.exists(f"/tmp/.X11-unix/X{n}") and not os.path.exists(f"/tmp/.X{n}-lock"):
            return f":{n}"
    raise RuntimeError("no free X display")


class Tour:
    def __init__(self, page, W, H):
        self.page, self.W, self.H = page, W, H
        self.x, self.y = W * 0.62, H * 0.62

    @staticmethod
    def ease(t):
        return 4 * t * t * t if t < .5 else 1 - pow(-2 * t + 2, 3) / 2

    def move(self, x, y):
        x = max(2, min(self.W - 2, x)); y = max(2, min(self.H - 2, y))
        self.page.mouse.move(x, y); self.x, self.y = x, y

    def glide(self, x, y, dur=0.8):
        x0, y0, t0 = self.x, self.y, time.time()
        while True:
            t = min(1.0, (time.time() - t0) / dur); e = self.ease(t)
            self.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            if t >= 1.0: break
            time.sleep(0.012)

    def path(self, pts, dur):
        seg = dur / max(1, len(pts))
        for (x, y) in pts: self.glide(x, y, seg)

    def circle(self, cx, cy, rx, ry, turns=1.0, dur=3.0, start=0.0):
        t0 = time.time()
        while True:
            t = min(1.0, (time.time() - t0) / dur); a = start + 2 * math.pi * turns * t
            self.move(cx + rx * math.cos(a), cy + ry * math.sin(a))
            if t >= 1.0: break
            time.sleep(0.012)

    def scroll_to(self, y_target, speed=900):
        last = time.time(); stuck = 0; prev = None
        for _ in range(6000):
            cur, maxy = self.page.evaluate("[scrollY, document.documentElement.scrollHeight - innerHeight]")
            tgt = min(y_target, maxy); diff = tgt - cur
            if abs(diff) < 4: break
            stuck = stuck + 1 if prev is not None and abs(cur - prev) < 1 else 0; prev = cur
            if stuck > 40: break  # scroll-jacked or locked page
            now = time.time(); dt = min(0.1, now - last); last = now
            dy = max(-speed * dt, min(speed * dt, diff))
            if abs(diff) < 150: dy = diff * 0.3 if abs(diff * 0.3) > 4 else diff
            self.page.mouse.wheel(0, dy)
            time.sleep(0.016)
        return self.page.evaluate("scrollY")

    def bring(self, t, margin=0.5):
        sy = self.scroll_to(t["y"] + t["h"] / 2 - self.H * margin); time.sleep(0.25)
        return sy

    def press_off(self, x, y, dx=-160, dy=140):
        """Show the pressed state, then release away from the element so nothing is activated."""
        self.page.mouse.down(); time.sleep(0.8)
        self.glide(x + dx, y + dy, 0.5)
        self.page.mouse.up(); time.sleep(0.4)


def calibrate(page, disp, W, H, workdir):
    """Find where the page viewport sits on the X screen (app-mode window chrome varies)."""
    page.set_content("<body style='margin:0;background:rgb(255,0,0)'></body>"); time.sleep(1.2)
    shot = os.path.join(workdir, "calib.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-video_size", f"{W}x{H + 200}", "-i", disp + ".0", "-frames:v", "1", shot], check=True)
    from PIL import Image
    im = Image.open(shot).convert("RGB"); px = im.load(); w, h = im.size
    ys = [y for y in range(h) if px[w // 2, y] == (255, 0, 0)]
    xs = [x for x in range(w) if px[x, ys[len(ys) // 2]] == (255, 0, 0)] if ys else []
    if not ys or not xs: raise RuntimeError("calibration failed: viewport not found on screen")
    return xs[0], ys[0], xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1


def wait_ready(page, ready_js, timeout=40):
    if ready_js:
        page.wait_for_function(ready_js, timeout=timeout * 1000); return "ready_js"
    try:
        page.wait_for_load_state("load", timeout=timeout * 1000)
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    return "load+networkidle"


def probe(url, W, H, out):
    with sync_playwright() as p:
        b = p.chromium.launch(args=CHROME_ARGS)
        pg = b.new_page(viewport={"width": W, "height": H})
        t = time.time(); pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        how = wait_ready(pg, None); pg.wait_for_timeout(2500)
        info = pg.evaluate(DISCOVER_JS); info["ready"] = how; info["ready_after_s"] = round(time.time() - t, 1)
        for tg in info["targets"]:
            tg["danger"] = bool(DANGER.search(tg["text"] + " " + tg["href"])) or tg["form"] or tg["type"] == "submit"
        pg.screenshot(path=os.path.join(out, "probe_top.png"))
        pg.evaluate("scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(1500)
        info["height_after_scroll"] = pg.evaluate("document.documentElement.scrollHeight")
        pg.screenshot(path=os.path.join(out, "probe_bottom.png"))
        b.close()
    with open(os.path.join(out, "probe.json"), "w") as f: json.dump(info, f, indent=1)
    log(json.dumps({k: info[k] for k in ("title", "height", "height_after_scroll", "flags", "ready", "ready_after_s")}))
    for tg in info["targets"]:
        log(f"  {tg['kind']:6} y={int(tg['y']):5} {int(tg['w'])}x{int(tg['h'])} {'DANGER ' if tg['danger'] else ''}{tg['tag']} '{tg['text'][:40]}' {tg['name'][:30]}")
    return info


def choreograph(tour, page, max_seconds, t_start, mark):
    W, H = tour.W, tour.H
    info = page.evaluate(DISCOVER_JS)
    targets = info["targets"]
    for tg in targets:
        tg["danger"] = bool(DANGER.search(tg["text"] + " " + tg["href"])) or tg["form"] or tg["type"] == "submit"
    # budget: keep the canvases and cards, thin out buttons if the page is busy
    buttons = [t for t in targets if t["kind"] == "button"]
    if len(buttons) > 10:
        step = math.ceil(len(buttons) / 10); keep_b = set(id(t) for t in buttons[::step])
        targets = [t for t in targets if t["kind"] != "button" or id(t) in keep_b]
    targets = targets[:28]
    mark(f"tour {len(targets)} targets")
    elapsed = lambda: time.time() - t_start
    reserve = 14  # seconds kept for the bottom of the page
    for tg in targets:
        if elapsed() > max_seconds - reserve: mark("budget reached, skipping to bottom"); break
        if tg["y"] > 0 and tg["y"] + tg["h"] > page.evaluate("document.documentElement.scrollHeight") - 40 and tg["kind"] == "button":
            continue  # footer links are handled at the end
        sy = tour.bring(tg, 0.5)
        cx = tg["x"] + tg["w"] / 2; cy = tg["y"] - sy + tg["h"] / 2
        if not (0 < cy < H): continue
        if tg["kind"] == "canvas" or tg["kind"] == "media":
            mark(f"canvas {tg['name'][:20]}")
            left, right = max(60, tg["x"] + 40), min(W - 60, tg["x"] + tg["w"] - 40)
            tour.glide(left, cy, 0.9); time.sleep(0.3)
            tour.glide(right, cy, 2.4); time.sleep(0.3)
            tour.glide(cx, cy, 1.0); time.sleep(0.6)
            rx, ry = min(170, tg["w"] / 3), min(130, tg["h"] / 3)
            tour.circle(cx, cy, rx, ry, turns=1.5, dur=4.0)
            for _ in range(2):  # fast swipes: scatters particle / physics effects
                tour.glide(cx - min(420, tg["w"] / 2.3), cy - ry * 1.3, 0.35)
                tour.glide(cx + min(420, tg["w"] / 2.3), cy + ry * 1.2, 0.35)
            tour.glide(cx, cy, 0.4); time.sleep(1.2)
            if tg["kind"] == "canvas":  # press and drag (canvas presses do not navigate)
                page.mouse.down(); tour.circle(cx, cy, rx * 0.55, ry * 0.55, turns=1.0, dur=2.2); page.mouse.up()
            tour.glide(min(W - 40, cx + rx * 3), cy + ry, 1.0); time.sleep(2.0)  # let it settle / reform
        elif tg["kind"] == "card":
            tour.glide(cx, cy, 0.9); time.sleep(0.5)
            dx, dy = min(180, tg["w"] / 2.4), min(140, tg["h"] / 2.4)
            tour.path([(cx - dx, cy - dy), (cx + dx, cy - dy * 0.4), (cx - dx * 0.35, cy + dy), (cx, cy)], 2.0); time.sleep(0.5)
        else:
            tour.glide(cx, cy, 0.8); time.sleep(0.9)
            if not tg["danger"] and tg["w"] >= 60 and tg["h"] >= 28:
                tour.press_off(cx, cy, -160 if cx > W / 2 else 160, 140 if cy < H / 2 else -140)
                tour.glide(cx, cy, 0.5); time.sleep(0.6)
    # bottom of the page and footer links
    mark("footer")
    tour.glide(W * 0.5, H * 0.45, 0.8)
    sy = tour.scroll_to(10 ** 7, speed=750); time.sleep(1.6)
    bottom = page.evaluate("[scrollY, document.documentElement.scrollHeight - innerHeight]")
    links = page.evaluate("""() => [...document.querySelectorAll('a[href], button')].map(e => { const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height, t: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30)}; }).filter(o => o.w > 4 && o.y > innerHeight * 0.35 && o.y < innerHeight - 4).slice(-6)""")
    for l in links:
        if time.time() - t_start > max_seconds - 3: break
        tour.glide(l["x"], l["y"], 0.6); time.sleep(0.7)
    tour.glide(W * 0.5, H * 0.4, 1.0); time.sleep(1.8)
    mark("end")
    return {"targets": len(targets), "bottom": bottom, "footer_links": [l["t"] for l in links]}


def record(url, W, H, out, ready_js, max_seconds, custom=None):
    disp = free_display()
    env = dict(os.environ, DISPLAY=disp)
    xvfb = subprocess.Popen(["Xvfb", disp, "-screen", "0", f"{W}x{H + 200}x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5); os.environ["DISPLAY"] = disp
    raw = os.path.join(out, "raw.mp4"); ff = None; summary = {}
    try:
        with sync_playwright() as p:
            chrome_h = 87
            for attempt in range(2):
                b = p.chromium.launch(headless=False, env=env, args=[
                    "--app=data:text/html,<body style=background:%23fafafa></body>", f"--window-size={W},{H + chrome_h}", "--window-position=0,0"] + CHROME_ARGS,
                    ignore_default_args=["--enable-automation"])
                ctx = b.new_context(no_viewport=True)
                page = ctx.new_page()
                inner = page.evaluate("[innerWidth, innerHeight]")
                if inner == [W, H]: break
                chrome_h += H - inner[1]; b.close()
            log("inner", inner)
            ox, oy, cw, chh = calibrate(page, disp, W, H, out)
            log("viewport on screen", ox, oy, cw, chh)
            # safety nets: no other-document navigation, no form posts, no popups
            state = {"armed": False, "blocked": []}
            def guard(route):
                r = route.request
                if state["armed"] and r.is_navigation_request() and r.frame == page.main_frame:
                    state["blocked"].append(r.url); return route.abort()
                if state["armed"] and r.method != "GET" and r.resource_type == "document":
                    state["blocked"].append(r.method + " " + r.url); return route.abort()
                return route.continue_()
            ctx.route("**/*", guard)
            ctx.on("page", lambda pg: (state["blocked"].append("popup " + pg.url), pg.close()))
            ctx.add_init_script(CURSOR_JS)
            page.goto("about:blank"); page.evaluate("document.documentElement.style.background='#fafafa'"); time.sleep(0.8)
            ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0", "-framerate", "30",
                                   "-video_size", f"{W}x{H}", "-i", f"{disp}.0+{ox},{oy}", "-c:v", "libx264", "-preset", "ultrafast",
                                   "-crf", "16", "-pix_fmt", "yuv420p", raw], stdin=subprocess.PIPE, env=env)
            t_start = time.time(); marks = []
            def mark(lbl):
                marks.append((round(time.time() - t_start, 1), lbl)); log(marks[-1])
            time.sleep(0.6); mark("load")
            page.goto(url, wait_until="commit", timeout=60000)
            tour = Tour(page, W, H); tour.move(tour.x, tour.y)
            how = wait_ready(page, ready_js); state["armed"] = True
            mark(f"ready ({how})"); time.sleep(2.6)
            tour.glide(W * 0.25, H * 0.3, 1.0); time.sleep(0.4)
            if custom:
                summary = custom(tour, page, mark) or {}
            else:
                summary = choreograph(tour, page, max_seconds, t_start, mark)
            ff.stdin.write(b"q"); ff.stdin.flush(); ff.wait(timeout=90)
            summary.update({"marks": marks, "blocked": state["blocked"], "url": url, "final_url": page.url})
            b.close()
    finally:
        if ff and ff.poll() is None:
            ff.send_signal(signal.SIGINT); ff.wait(timeout=30)
        xvfb.terminate()
    return raw, summary


def probe_media(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=width,height,r_frame_rate", "-of", "json", path], capture_output=True, text=True)
    j = json.loads(r.stdout); s = j["streams"][0]
    return {"duration": float(j["format"]["duration"]), "size_mb": round(int(j["format"]["size"]) / 1048576, 2), "w": s["width"], "h": s["height"], "fps": s["r_frame_rate"]}


def finish(raw, out, slug, deliver_w, max_mb):
    master = os.path.join(out, f"{slug}-master.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", master], check=True)
    dur = probe_media(master)["duration"]
    deliver = os.path.join(out, f"{slug}.mp4")
    vf = f"scale={deliver_w}:-2:flags=lanczos"
    # simple pages compress well: try quality-based first, fall back to sized 2-pass
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", master, "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-vf", vf, "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", deliver], check=True)
    if os.path.getsize(deliver) <= max_mb * 1048576:
        return master, deliver, "crf21"
    master_mb = os.path.getsize(master) / 1048576
    kbps = int(max_mb * 8 * 1024 * 0.93 / dur)  # 7% headroom for container + rate tolerance
    for attempt in range(3):
        common = ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{kbps}k", "-vf", vf, "-pix_fmt", "yuv420p", "-an", "-passlogfile", os.path.join(out, "p")]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", master] + common + ["-pass", "1", "-f", "mp4", "/dev/null"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", master] + common + ["-pass", "2", "-movflags", "+faststart", deliver], check=True)
        if os.path.getsize(deliver) <= max_mb * 1048576: break
        kbps = int(kbps * 0.85)
    for f in os.listdir(out):
        if f.startswith("p-0.log"): os.remove(os.path.join(out, f))
    return master, deliver, f"{kbps}k 2-pass (master {master_mb:.1f} MB)"


def validate(path, out, n=8):
    info = probe_media(path)
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    info["decode_ok"] = dec.returncode == 0 and not dec.stderr.strip()
    from PIL import Image, ImageStat
    frames = []; tiles = []
    for i in range(n):
        t = info["duration"] * (i + 0.5) / n if i < n - 1 else max(0, info["duration"] - 0.5)
        fp = os.path.join(out, f"check_{i}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", fp], check=True)
        im = Image.open(fp).convert("L"); sd = ImageStat.Stat(im).stddev[0]
        frames.append({"t": round(t, 1), "stddev": round(sd, 1), "blank": sd < 3}); tiles.append(Image.open(fp).convert("RGB"))
    tw = 480; th = int(tiles[0].height * tw / tiles[0].width)
    sheet = Image.new("RGB", (tw * 4, th * math.ceil(n / 4)), "white")
    for i, im in enumerate(tiles): sheet.paste(im.resize((tw, th)), ((i % 4) * tw, (i // 4) * th))
    sheet.save(os.path.join(out, "contact_sheet.jpg"), quality=85)
    info["frames"] = frames; info["last_frame_blank"] = frames[-1]["blank"]
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("--out", default=None); ap.add_argument("--probe", action="store_true")
    ap.add_argument("--ready-js", default=None, help="JS expression that is truthy once the site's loader is done")
    ap.add_argument("--max-seconds", type=float, default=120); ap.add_argument("--width", type=int, default=1440); ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--deliver-width", type=int, default=1280); ap.add_argument("--max-mb", type=float, default=9.5)
    a = ap.parse_args()
    slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://(www\.)?", "", a.url.lower())).strip("-")[:50] + "-site-tour"
    out = a.out or os.path.join(os.path.expanduser("~"), "site-tour-runs", slug)
    os.makedirs(out, exist_ok=True)
    if a.probe:
        probe(a.url, a.width, a.height, out); return
    raw, summary = record(a.url, a.width, a.height, out, a.ready_js, a.max_seconds)
    master, deliver, kbps = finish(raw, out, slug, min(a.deliver_width, a.width), a.max_mb)
    report = {"summary": summary, "master": master, "master_info": probe_media(master), "deliver": deliver, "deliver_kbps": kbps, "deliver_check": validate(deliver, out)}
    reached = summary.get("bottom") and abs(summary["bottom"][0] - summary["bottom"][1]) < 8
    report["reached_bottom"] = bool(reached) if summary.get("bottom") else None
    with open(os.path.join(out, "report.json"), "w") as f: json.dump(report, f, indent=1)
    log("REPORT", json.dumps({k: report[k] for k in ("master", "deliver", "reached_bottom")}), json.dumps(report["deliver_check"] | {"frames": None}))
    if summary.get("blocked"): log("BLOCKED (safety net)", summary["blocked"])


if __name__ == "__main__":
    main()
