from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    pg=b.new_page(viewport={"width":1440,"height":900})
    logs=[]; pg.on("console",lambda m: logs.append(m.type+": "+m.text[:150]))
    pg.goto("https://shifatmasud-framer.vercel.app",wait_until="networkidle",timeout=60000)
    print(pg.evaluate("""()=>{const lc=document.querySelector('[data-framer-name="Logo Cloud"]');return lc.outerHTML.slice(0,2500)}"""))
    print(pg.evaluate("!!document.createElement('canvas').getContext('webgl2')"))
    print(pg.evaluate("[...document.querySelectorAll('canvas')].map(c=>c.width+'x'+c.height+' '+c.parentElement.getAttribute('data-framer-name'))"))
    print(pg.evaluate("document.querySelector('svg.sh-svg').outerHTML.slice(0,800)"))
    print(pg.evaluate("[...document.querySelectorAll('script[src]')].map(s=>s.src).join('\\n')"))
    print("\n".join(logs[:20]))
    b.close()
