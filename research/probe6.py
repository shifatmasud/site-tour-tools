from playwright.sync_api import sync_playwright
import re
hits=[]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"])
    pg=b.new_page(viewport={"width":1440,"height":900})
    def onr(r):
        try:
            if r.request.resource_type in ("script","fetch","xhr","document"):
                t=r.text()
                if "sh-pl" in t or "shPl" in t: hits.append((r.url,t))
        except Exception: pass
    pg.on("response",onr)
    pg.goto("https://shifatmasud-framer.vercel.app",wait_until="networkidle",timeout=60000)
    pg.wait_for_timeout(13000)
    b.close()
for u,t in hits:
    print(u,len(t))
    i=t.find("sh-pl"); 
    open('/tmp/rec/pl_src.js','w').write(t)
    seg=t[max(0,i-6000):i+6000]
    for m in re.finditer(r'(pointer[a-z]+|mouse[a-z]+|touch[a-z]+|click|wheel|/\*.{0,200}?\*/|//[^\n]{0,150})',seg):
        print(m.group(0)[:200])
