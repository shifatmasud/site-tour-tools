import subprocess,time,os,sys
from playwright.sync_api import sync_playwright
W,H=1440,900
x=subprocess.Popen(["Xvfb",":97","-screen","0","1440x1000x24"],stderr=subprocess.DEVNULL);time.sleep(1)
env=dict(os.environ,DISPLAY=":97")
FPS="""()=>new Promise(r=>{let n=0;const t0=performance.now();function f(){n++;if(performance.now()-t0<2000)requestAnimationFrame(f);else r(Math.round(n/2))}requestAnimationFrame(f)})"""
base=["--force-device-scale-factor=1","--ignore-gpu-blocklist"]
configs={
 'swiftshader-all':["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],
 'sw-compositing':["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--disable-gpu-compositing"],
 'sw-comp-raster-threads':["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--disable-gpu-compositing","--num-raster-threads=4","--enable-zero-copy"],
}
which=sys.argv[1:] or list(configs)
for name in which:
    with sync_playwright() as p:
        b=p.chromium.launch(headless=False,env=env,args=["--app=data:text/html,x","--window-size=1440,987","--window-position=0,0"]+base+configs[name],ignore_default_args=["--enable-automation"])
        c=b.new_context(no_viewport=True); pg=c.new_page()
        pg.goto("https://shifatmasud-framer.vercel.app",wait_until="commit")
        pg.wait_for_function("window.__shPreDone===1",timeout=40000); time.sleep(3)
        res={'hero':pg.evaluate(FPS)}
        pg.evaluate("scrollTo(0,500)"); time.sleep(1); pg.mouse.move(360,600); time.sleep(0.5)
        res['tile-hover-idle']=pg.evaluate(FPS)
        # fps while moving mouse
        h=pg.evaluate_handle(FPS)
        t=time.time()
        while time.time()-t<2: pg.mouse.move(300+100*((time.time()-t)%1),600)
        res['tile-moving']=h.json_value()
        pg.evaluate("scrollTo(0,99999)"); time.sleep(1.5); pg.mouse.move(720,560)
        res['footer']=pg.evaluate(FPS)
        print(name,res,flush=True)
        b.close()
x.terminate()
