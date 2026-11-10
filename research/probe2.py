from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-webgl","--ignore-gpu-blocklist"])
    pg=b.new_page(viewport={"width":1440,"height":900})
    pg.goto("https://shifatmasud-framer.vercel.app",wait_until="networkidle",timeout=60000)
    pg.wait_for_timeout(2000)
    print(pg.evaluate("document.body.innerText")[:3000])
    print("----")
    print(pg.evaluate("""()=>{const o=[];document.querySelectorAll('body *').forEach(e=>{const r=e.getBoundingClientRect();const y=r.y+scrollY;const cs=getComputedStyle(e);
      if(y>2400 && r.width>150 && r.height>60 && (e.children.length<4)) o.push([e.tagName,(e.className.baseVal??e.className)+'',e.getAttribute('data-framer-name')||'',cs.cursor,Math.round(r.x),Math.round(y),Math.round(r.width),Math.round(r.height),(e.innerText||'').slice(0,30).replace(/\\n/g,' ')].join(' | '))});return o.slice(0,80).join('\\n')}"""))
    print("----canvas/svg/cursor-pointer")
    print(pg.evaluate("""()=>{const o=[];document.querySelectorAll('canvas,svg,[data-framer-name]').forEach(e=>{const r=e.getBoundingClientRect();if(r.width>100)o.push([e.tagName,e.getAttribute('data-framer-name')||'',getComputedStyle(e).cursor,Math.round(r.x),Math.round(r.y+scrollY),Math.round(r.width),Math.round(r.height)].join(' | '))});return o.join('\\n')}"""))
    b.close()
