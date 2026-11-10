import subprocess, time, math, os, signal
from playwright.sync_api import sync_playwright

URL = "https://shifatmasud-framer.vercel.app"
W, H = 1440, 900
DISPLAY = ":99"
OUT_RAW = "/tmp/rec/raw.mp4"

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
    (document.documentElement).appendChild(ring);
    (document.documentElement).appendChild(c);
    const pos = (e) => { const t = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)'; c.style.transform = t; ring.style.transform = t; };
    window.addEventListener('pointermove', pos, true);
    window.addEventListener('pointerdown', (e) => { pos(e); ring.style.opacity = '1'; ring.style.scale = '1'; }, true);
    window.addEventListener('pointerup', (e) => { ring.style.opacity = '0'; ring.style.scale = '.6'; }, true);
    // keep the overlay above the loader, which is appended later
    new MutationObserver(() => { if (document.documentElement.lastElementChild !== c) { document.documentElement.appendChild(ring); document.documentElement.appendChild(c); } }).observe(document.documentElement, {childList: true});
  };
  if (document.documentElement) mk(); else document.addEventListener('DOMContentLoaded', mk);
})();
"""

state = {"x": W * 0.62, "y": H * 0.62}

def ease(t):
    return 4 * t * t * t if t < .5 else 1 - pow(-2 * t + 2, 3) / 2

def glide(page, x, y, dur=0.8):
    x0, y0 = state["x"], state["y"]
    t0 = time.time()
    while True:
        t = min(1.0, (time.time() - t0) / dur)
        e = ease(t)
        page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
        if t >= 1.0:
            break
        time.sleep(0.012)
    state["x"], state["y"] = x, y

def path(page, pts, dur):
    # smooth path through points, constant time per segment
    seg = dur / max(1, len(pts))
    for (x, y) in pts:
        glide(page, x, y, seg)

def circle(page, cx, cy, rx, ry, turns=1.0, dur=3.0, start=0.0):
    t0 = time.time()
    while True:
        t = min(1.0, (time.time() - t0) / dur)
        a = start + 2 * math.pi * turns * t
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        page.mouse.move(x, y)
        state["x"], state["y"] = x, y
        if t >= 1.0:
            break
        time.sleep(0.012)

def scroll_to(page, y_target, speed=900):
    # time-based smooth wheel scroll at ~speed px/s
    last = time.time()
    for _ in range(5000):
        cur, maxy = page.evaluate("[scrollY, document.documentElement.scrollHeight - innerHeight]")
        tgt = min(y_target, maxy)
        diff = tgt - cur
        if abs(diff) < 4:
            break
        now = time.time(); dt = min(0.1, now - last); last = now
        dy = max(-speed * dt, min(speed * dt, diff))
        if abs(diff) < 150:
            dy = diff * 0.3 if abs(diff * 0.3) > 4 else diff
        page.mouse.wheel(0, dy)
        time.sleep(0.016)

def rect(page, sel, idx=0):
    return page.evaluate("([s,i])=>{const e=document.querySelectorAll(s)[i];if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y+scrollY,w:r.width,h:r.height}}", [sel, idx])

def bring(page, r, margin=0.5):
    # scroll so element center sits at `margin` of the viewport height
    scroll_to(page, r["y"] + r["h"] / 2 - H * margin)
    time.sleep(0.25)
    return page.evaluate("scrollY")

def main():
    env = dict(os.environ, DISPLAY=DISPLAY)
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", f"{W}x1000x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    os.environ["DISPLAY"] = DISPLAY
    ff = None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=False, env=env, args=[
                "--app=data:text/html,<body style=background:%23fafafa></body>", f"--window-size={W},987", "--window-position=0,0",
                "--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-gpu-compositing",
                "--disable-infobars", "--force-device-scale-factor=1", "--hide-scrollbars", "--no-first-run", "--autoplay-policy=no-user-gesture-required",
            ], ignore_default_args=["--enable-automation"])
            ctx = b.new_context(no_viewport=True)
            ctx.add_init_script(CURSOR_JS)
            page = ctx.new_page()
            page.goto("about:blank")
            page.evaluate("document.documentElement.style.background='#fafafa'")
            time.sleep(1.0)
            inner = page.evaluate("[innerWidth, innerHeight]"); print("inner", inner, flush=True)
            assert inner == [W, H], inner
            ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0", "-framerate", "30",
                                   "-video_size", f"{W}x{H}", "-i", DISPLAY + ".0+0,87", "-c:v", "libx264", "-preset", "ultrafast",
                                   "-crf", "16", "-pix_fmt", "yuv420p", OUT_RAW], stdin=subprocess.PIPE, env=env)
            t_start = time.time()
            marks = []
            def mark(lbl):
                marks.append((round(time.time() - t_start, 1), lbl)); print(marks[-1], flush=True)
            time.sleep(0.6)
            mark("load")
            page.goto(URL, wait_until="commit", timeout=60000)
            page.mouse.move(state["x"], state["y"])
            page.wait_for_function("window.__shPreDone===1", timeout=40000)
            mark("loader done")
            time.sleep(2.6)
            # hero: header button + marquee
            mark("hero")
            glide(page, 300, 220, 1.0)
            time.sleep(0.4)
            r = rect(page, '[data-framer-name="CTA Dark"]')
            bx, by = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
            glide(page, bx, by, 1.1)
            time.sleep(1.2)
            # press and hold (no click: release happens off the button)
            page.mouse.down(); time.sleep(0.8)
            glide(page, bx - 160, by + 140, 0.5)
            page.mouse.up(); time.sleep(0.4)
            glide(page, bx, by, 0.5); time.sleep(0.9)
            glide(page, 720, 380, 1.0); time.sleep(0.6)
            glide(page, 300, 380, 1.4); time.sleep(0.5)
            # work tiles
            mark("tiles")
            for row in range(3):
                r0 = rect(page, '[data-framer-name="Tile"]', row * 2)
                sy = bring(page, r0, 0.5)
                for col in range(2):
                    rr = rect(page, '[data-framer-name="Tile"]', row * 2 + col)
                    cx, cy = rr["x"] + rr["w"] / 2, rr["y"] - sy + rr["h"] / 2
                    glide(page, cx, cy, 0.9)
                    time.sleep(0.5)
                    path(page, [(cx - 180, cy - 140), (cx + 180, cy - 60), (cx - 60, cy + 160), (cx, cy)], 2.2)
                    time.sleep(0.6)
                # move out between rows
            mark("about")
            glide(page, 360, 450, 0.8)
            r = rect(page, '[data-framer-name="About"]')
            bring(page, r, 0.45)
            time.sleep(0.8)
            for i in range(3):
                rr = rect(page, '[data-framer-name="Row"]', i)
                sy = page.evaluate("scrollY")
                glide(page, rr["x"] + 160, rr["y"] - sy + rr["h"] / 2, 0.8)
                time.sleep(0.7)
            r = rect(page, '[data-framer-name="Quote"]')
            bring(page, r, 0.5)
            time.sleep(1.4)
            # contact button
            mark("contact")
            r = rect(page, '[data-framer-name="CTA Light"]')
            sy = bring(page, r, 0.42)
            r = rect(page, '[data-framer-name="CTA Light"]')
            bx, by = r["x"] + r["w"] / 2, r["y"] - sy + r["h"] / 2
            glide(page, bx, by, 1.0)
            time.sleep(1.2)
            page.mouse.down(); time.sleep(0.8)
            glide(page, bx + 200, by - 120, 0.5)
            page.mouse.up(); time.sleep(0.4)
            glide(page, bx, by, 0.5); time.sleep(0.8)
            glide(page, 720, by + 200, 0.8)
            # footer particle logo
            mark("footer")
            scroll_to(page, 99999, speed=700)
            time.sleep(1.8)
            c = page.evaluate("(()=>{const r=document.querySelector('canvas[data-sh-pl]').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()")
            cx, cy = c["x"] + c["w"] / 2, c["y"] + c["h"] / 2
            print("canvas", c, page.evaluate("(()=>{const cv=document.querySelector('canvas[data-sh-pl]');return cv.getContext('webgl2')?'webgl2':(cv.getContext('2d')?'2d-fallback':'none')})()"), flush=True)
            glide(page, 200, cy, 1.0)
            time.sleep(0.4)
            # slow pass through the logo
            glide(page, W - 200, cy, 2.6)
            time.sleep(0.4)
            glide(page, cx, cy, 1.2)
            time.sleep(0.8)
            circle(page, cx, cy, 170, 130, turns=1.5, dur=4.5)
            time.sleep(0.6)
            # fast swipes to scatter the particles
            for _ in range(2):
                glide(page, cx - 420, cy - 180, 0.35)
                glide(page, cx + 420, cy + 160, 0.35)
            glide(page, cx, cy, 0.4)
            time.sleep(1.6)
            # press and drag on the logo
            page.mouse.down()
            circle(page, cx, cy, 90, 70, turns=1.0, dur=2.5)
            page.mouse.up()
            time.sleep(0.6)
            # leave and let it reform
            glide(page, cx + 520, c["y"] + c["h"] - 40, 1.0)
            time.sleep(2.4)
            # footer links
            mark("links")
            links = page.evaluate("(()=>{const out=[];for(const t of ['X','GitHub','Email']){const el=[...document.querySelectorAll('[data-framer-name=Footer] *')].filter(e=>e.innerText&&e.innerText.trim()===t).pop();if(el){const r=el.getBoundingClientRect();out.push({t,x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,cur:getComputedStyle(el).cursor})}}return out})()")
            print("links", links, flush=True)
            for l in links:
                glide(page, l["x"], l["y"], 0.6)
                time.sleep(0.8)
            glide(page, cx, cy - 60, 1.0)
            time.sleep(2.0)
            mark("end")
            ff.stdin.write(b"q"); ff.stdin.flush()
            ff.wait(timeout=60)
            b.close()
            print("marks", marks)
    finally:
        if ff and ff.poll() is None:
            ff.send_signal(signal.SIGINT); ff.wait(timeout=30)
        xvfb.terminate()

if __name__ == "__main__":
    main()
