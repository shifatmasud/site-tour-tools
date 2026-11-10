from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    pg=b.new_page(viewport={"width":1440,"height":900})
    pg.goto("https://shifatmasud-framer.vercel.app",wait_until="networkidle",timeout=60000)
    pg.screenshot(path="/tmp/t0.png")
    for i in range(12):
        pg.mouse.wheel(0,500); pg.wait_for_timeout(250)
    pg.wait_for_timeout(1500)
    print("scrollY",pg.evaluate("scrollY"))
    print(pg.evaluate("""()=>{const lc=document.querySelector('[data-framer-name="Logo Cloud"]');return lc.outerHTML.slice(0,1500)+' children:'+lc.children.length}"""))
    print(pg.evaluate("[...document.querySelectorAll('canvas')].map(c=>c.width+'x'+c.height+' '+c.className+' '+JSON.stringify(c.getBoundingClientRect()))"))
    print(pg.evaluate("[...document.body.children].map(e=>e.tagName+'.'+(e.className.baseVal??e.className)+' '+e.id).join('\\n')"))
    pg.mouse.move(720,600); pg.wait_for_timeout(500)
    pg.screenshot(path="/tmp/bottom.png")
    print(pg.evaluate("document.querySelector('svg.sh-svg').outerHTML.slice(0,600)"))
    b.close()
