from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    pg=b.new_page(viewport={"width":1440,"height":900})
    t=time.time()
    pg.goto("https://shifatmasud-framer.vercel.app",wait_until="domcontentloaded",timeout=60000)
    pg.wait_for_function("window.__shPreDone===1",timeout=30000)
    print("loader done after",round(time.time()-t,1))
    pg.wait_for_timeout(2500)
    pg.screenshot(path="/tmp/rec/hero.png")
    for i in range(20):
        pg.mouse.wheel(0,300); pg.wait_for_timeout(150)
    pg.wait_for_timeout(1500)
    print("scrollY",pg.evaluate("scrollY"))
    print(pg.evaluate("""()=>{const lc=document.querySelector('[data-framer-name="Logo Cloud"]');return lc.outerHTML.slice(0,1200)+' children:'+lc.children.length+' rect:'+JSON.stringify(lc.getBoundingClientRect())}"""))
    print(pg.evaluate("[...document.querySelectorAll('canvas')].map(c=>c.width+'x'+c.height+' '+(c.parentElement.getAttribute('data-framer-name')||c.parentElement.className)+' '+JSON.stringify(c.getBoundingClientRect()))"))
    print(pg.evaluate("[...document.querySelectorAll('body > *')].map(e=>e.tagName+'.'+(e.className.baseVal??e.className)+'#'+e.id).join(' ; ')"))
    pg.mouse.move(400,500); pg.wait_for_timeout(300)
    pg.screenshot(path="/tmp/rec/bottom2.png")
    b.close()
