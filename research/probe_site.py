import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=swiftshader","--enable-webgl","--ignore-gpu-blocklist"])
        pg = await b.new_page(viewport={"width":1440,"height":900})
        await pg.goto("https://shifatmasud-framer.vercel.app", wait_until="networkidle", timeout=60000)
        await pg.wait_for_timeout(3000)
        print("title", await pg.title())
        print("height", await pg.evaluate("document.documentElement.scrollHeight"), await pg.evaluate("document.body.scrollHeight"))
        print(await pg.evaluate("""() => {
          const out=[];
          document.querySelectorAll('a,button,[role=button],canvas,svg,[class*=card],[class*=Card],footer,[onclick]').forEach(e=>{
            const r=e.getBoundingClientRect();
            out.push([e.tagName, (e.className&&e.className.baseVal!==undefined?e.className.baseVal:e.className)+'', (e.innerText||e.getAttribute('aria-label')||'').slice(0,40).replace(/\\n/g,' '), Math.round(r.x),Math.round(r.y+scrollY),Math.round(r.width),Math.round(r.height)]);
          });
          return out.slice(0,150).map(x=>x.join(' | ')).join('\\n');
        }"""))
        await pg.screenshot(path="/tmp/top.png")
        await pg.screenshot(path="/tmp/full.png", full_page=True)
        await b.close()
asyncio.run(main())
