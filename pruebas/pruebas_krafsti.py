#!/usr/bin/env python3
"""Pruebas de Krafsti Studio (desde la 1.32). Comprueban en Chrome (Playwright) todo lo importante de la herramienta,
sin internet: la prueba bloquea cualquier petición fuera del archivo y falla si la página pide algo.

Uso:   python3 pruebas_krafsti.py Krafsti_Studio_v1.32.html  [--capturas carpeta]
Hace falta:  pip install playwright  y  playwright install chromium

Para llegar por dentro a la herramienta, la prueba hace una copia del HTML con un «gancho» (window.__T) dentro de Componer.
Al final escribe cuántas comprobaciones pasaron y sale con error si alguna falló.
"""
import asyncio, json, pathlib, re, sys, tempfile
from playwright.async_api import async_playwright

HTML = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'Krafsti_Studio_v1.32.html').resolve()
SHOTS = pathlib.Path(sys.argv[sys.argv.index('--capturas') + 1]) if '--capturas' in sys.argv else None
if SHOTS: SHOTS.mkdir(parents=True, exist_ok=True)

src = HTML.read_text(encoding='utf-8')
HOOK = "  window.__T=new Proxy({},{get:(_,k)=>eval(k)});   // solo en la copia de prueba\n"
MARK = "  document.querySelectorAll('[data-bool]').forEach("
assert MARK in src, 'no encuentro dónde poner el gancho de prueba'
TEST = pathlib.Path(tempfile.gettempdir()) / ('prueba_' + HTML.name)
TEST.write_text(src.replace(MARK, HOOK + MARK, 1), encoding='utf-8')

OK, FAIL, NET, ERRS = [], [], [], []
def check(name, cond, info=''):
    (OK if cond else FAIL).append(name)
    print(('  ✔ ' if cond else '  ✘ ') + name + (f'  [{info}]' if info != '' else ''))

async def route(r):
    u = r.request.url
    if u.startswith(('file:', 'data:', 'blob:')): return await r.continue_()
    NET.append(u); await r.abort()

PNG_JS = """([w,h,draw,input])=>{ const c=document.createElement('canvas'); c.width=w; c.height=h; const g=c.getContext('2d'); (new Function('g',draw))(g);
  return new Promise(ok=>c.toBlob(b=>{ const dt=new DataTransfer(); dt.items.add(new File([b],'prueba.png',{type:'image/png'})); const i=document.getElementById(input); i.files=dt.files; i.dispatchEvent(new Event('change')); ok(); })); }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1600, 'height': 950})
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: ERRS.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(TEST.as_uri()); await pg.wait_for_timeout(800)
        ev = pg.evaluate
        T = lambda js: ev(js)
        async def toast(): return await pg.text_content('#edToast')
        async def shot(n):
            if SHOTS: await pg.screenshot(path=str(SHOTS / f'{n}.png'))
        async def add(sel):
            await ev("()=>__T.edPane('add')"); await pg.click(sel)
        async def clear():
            await ev("()=>{ const T=__T; T.ED.layers.length=0; T.ED.sel=null; T.ED.msel.clear(); T.ED.selection=null; T.ED.W=T.ED.H=2000; T.ED.shape='rect'; T.edSyncCanvasUI(); T.edSelChanged(); T.edFit(); }")
        async def scr(x, y):
            return await ev("([x,y])=>{ const r=document.getElementById('edCanvas').getBoundingClientRect(), S=__T.edScr({x,y}); return [r.left+S.x, r.top+S.y]; }", [x, y])
        rows = pg.locator('#edLayerList .edl2')
        async def pick2():
            await rows.nth(0).click(); await rows.nth(1).click(modifiers=['Control'])

        print('Arranque')
        ver = await pg.text_content('#ver')
        check('la cabecera dice la versión', bool(re.match(r'Versión 1\.\d+', ver)), ver)

        print('Vectorizar')
        await pg.click('#tabVec')
        await ev(PNG_JS, [400, 300, "g.fillStyle='#fff'; g.fillRect(0,0,400,300); g.fillStyle='#d94f30'; g.beginPath(); g.arc(200,150,100,0,7); g.fill(); g.fillStyle='#1f4e5f'; g.fillRect(40,40,80,60);", 'file'])
        await pg.wait_for_timeout(2500)
        st = await pg.text_content('#status'); n = int(await pg.text_content('#sPaths') or 0)
        check('traza una imagen', st.startswith('Listo') and n > 0, f'{st} · {n} formas')

        print('Retocar')
        await pg.click('#tabBg')
        await ev(PNG_JS, [400, 300, "g.fillStyle='#fff'; g.fillRect(0,0,400,300); g.fillStyle='#2a9d8f'; g.fillRect(120,80,160,140);", 'bgFile'])
        await pg.wait_for_timeout(800); await pg.click('#bgAuto'); await pg.wait_for_timeout(800)
        st = await pg.text_content('#bgStatus')
        check('quita el fondo de los bordes', 'quitado' in st, st)

        print('Componer: formas y esquinas')
        await pg.click('#tabEd'); await pg.wait_for_timeout(800)
        fonts = await ev("()=>['Bebas Neue','Pacifico','Great Vibes','IBM Plex Sans'].every(f=>document.fonts.check(`400 40px \"${f}\"`))")
        check('las fuentes van dentro del archivo', fonts)
        await add('[data-shape=rect]')
        r0 = await T("()=>{ const L=__T.edSelL(); return [L.sh.w,L.sh.h]; }")
        h = await T("()=>{ const T=__T, L=T.edSelL(), h=T.edHandles(L), r=document.getElementById('edCanvas').getBoundingClientRect(); return [r.left+h.c[2].x, r.top+h.c[2].y]; }")
        await pg.mouse.move(*h); await pg.mouse.down(); await pg.mouse.move(h[0] + 80, h[1] + 10, steps=5); await pg.mouse.up()
        r1 = await T("()=>{ const L=__T.edSelL(); return [L.sh.w,L.sh.h]; }")
        check('tirar de una esquina no deforma', abs(r1[0] / r1[1] - r0[0] / r0[1]) < 0.01 and r1[0] > r0[0], f'{r0} → {r1}')
        h = await T("()=>{ const T=__T, L=T.edSelL(), h=T.edHandles(L), r=document.getElementById('edCanvas').getBoundingClientRect(); return [r.left+h.c[2].x, r.top+h.c[2].y]; }")
        await pg.keyboard.down('Shift'); await pg.mouse.move(*h); await pg.mouse.down(); await pg.mouse.move(h[0] + 60, h[1] - 60, steps=5); await pg.mouse.up(); await pg.keyboard.up('Shift')
        r2 = await T("()=>{ const L=__T.edSelL(); return [L.sh.w,L.sh.h]; }")
        check('con Mayúsculas sí deforma', abs(r2[0] / r2[1] - r1[0] / r1[1]) > 0.1, f'{r2}')

        print('Unir y restar')
        await clear(); await add('[data-shape=ellipse]'); await add('[data-shape=ellipse]')
        await T("()=>{ const L=__T.ED.layers; L[1].sh.w=L[1].sh.h=120; L[1].x=1000; L[1].y=700; __T.edSelChanged(); }")
        await pick2(); await pg.click('[data-bool=minus]'); await pg.wait_for_timeout(300)
        r = await T("()=>{ const L=__T.edSelL(); return {n:__T.ED.layers.length,more:(L.p.more||[]).length}; }")
        check('llavero: círculo menos círculo da una forma con agujero', r['n'] == 1 and r['more'] == 1, r)
        a = await T("()=>{ const T=__T, L=T.edSelL(), C=T.edSrc(L), g=C.c.getContext('2d'), k=C.c.width/C.w; const at=(x,y)=>g.getImageData(Math.round(x*k),Math.round(y*k),1,1).data[3]; return [at(1000-L.x+C.w/2,700-L.y+C.h/2), at(C.w/2,C.h/2+200)]; }")
        check('el agujero se ve transparente', a == [0, 255], a)
        await pg.click('#edPenEdit'); await pg.wait_for_timeout(150)
        pt = await T("()=>{ const T=__T, L=T.edSelL(), q=L.p.more[0][0], A=T.edScr(T.edL2D(L,q.x,q.y)), r=document.getElementById('edCanvas').getBoundingClientRect(); return [r.left+A.x, r.top+A.y, L.p.more[0].length]; }")
        await pg.mouse.move(pt[0], pt[1]); await pg.mouse.down(); await pg.mouse.move(pt[0] + 20, pt[1] + 8, steps=4); await pg.mouse.up()
        check('con la pluma se edita el agujero', await T("()=>__T.edSelL().p.pts.length") == pt[2])
        await pg.click('#edToolMove')
        await ev("()=>{ __T.edUndo(); __T.edUndo(); }")
        check('deshacer devuelve las dos capas', await T("()=>__T.ED.layers.map(L=>L.type).join(',')") == 'shape,shape')
        await shot('1_llavero')

        await clear(); await add('[data-shape=rect]')
        await T("()=>{ const L=__T.edSelL(); L.sh.w=1300; L.sh.h=520; L.sh.fill.t='none'; L.sh.sw=40; __T.edSelChanged(); }")
        await add('#edAddText'); await pg.fill('#edText', 'KRAFSTI'); await pg.dispatch_event('#edText', 'input')
        await T("()=>{ const L=__T.edSelL(); L.t.size=420; L.t.font='Bebas Neue'; L.y+=40; __T.edSelChanged(); }"); await pg.wait_for_timeout(400)
        await pick2(); await pg.click('[data-bool=union]'); await pg.wait_for_timeout(1200)
        r = await T("()=>{ const L=__T.edSelL(); return {n:__T.ED.layers.length,c:1+(L.p.more||[]).length}; }")
        check('texto + marco sin relleno: unir', r['n'] == 1 and r['c'] == 11, r)
        await ev("()=>{ const r=document.getElementById('esm-cut'); r.checked=true; r.dispatchEvent(new Event('change')); }")
        svg = await ev("async()=>(await __T.edBuildSvg()).svg")
        check('SVG «Solo contornos» con todos los contornos', sum(x.count('M') for x in re.findall(r'<path d="([^"]+)"', svg)) == 11)
        await ev("()=>{ const r=document.getElementById('esm-look'); r.checked=true; r.dispatchEvent(new Event('change')); }")
        check('SVG «Como se ve» con relleno par-impar', 'fill-rule="evenodd"' in await ev("async()=>(await __T.edBuildSvg()).svg"))

        await clear(); await add('#edAddText'); await pg.fill('#edText', 'Hola papá'); await pg.dispatch_event('#edText', 'input')
        await T("()=>{ const L=__T.edSelL(); L.t.size=300; L.t.font='Pacifico'; __T.edSelChanged(); }"); await pg.wait_for_timeout(500)
        b0 = await T("()=>{ const b=__T.edInkBox(__T.edSelL()); return [b.x0,b.y0,b.x1,b.y1]; }")
        await pg.click('#edBoolShape'); await pg.wait_for_timeout(1200)
        b1 = await T("()=>{ const b=__T.edInkBox(__T.edSelL()); return [b.x0,b.y0,b.x1,b.y1]; }")
        check('«Convertir en forma» cuadra con lo que se ve', max(abs(b0[i] - b1[i]) for i in range(4)) < 3, [round(v - w, 1) for v, w in zip(b1, b0)])
        check('las letras a mano quedan enlazadas', await T("()=>1+(__T.edSelL().p.more||[]).length") == 14)
        await shot('2_letras')

        await clear()
        await ev(PNG_JS, [800, 600, "g.fillStyle='#264653'; g.fillRect(0,0,800,600);", 'edFile']); await pg.wait_for_timeout(700)
        await add('[data-shape=ellipse]')
        await T("()=>{ const T=__T, L=T.edSelL(), I=T.ED.layers[0]; L.sh.w=L.sh.h=90; L.x=I.x; L.y=I.y-200; T.edSelChanged(); }")
        await pick2(); await pg.click('[data-bool=minus]'); await pg.wait_for_timeout(400)
        r = await T("()=>{ const L=__T.edSelL(); return [L.type,!!L.mask]; }")
        check('foto menos círculo: la foto lleva máscara', r == ['img', True], r)
        await clear(); await add('[data-shape=star]'); await add('[data-shape=ellipse]')
        await pick2(); await ev("()=>{ document.getElementById('edBoolKeep').checked=true; }")
        await pg.click('[data-bool=xor]'); await pg.wait_for_timeout(300)
        check('«Guardar las capas originales» las deja ocultas', await T("()=>__T.ED.layers.filter(L=>!L.vis).length") == 2)
        await ev("()=>{ document.getElementById('edBoolKeep').checked=false; }")
        await pg.click('#edToSel'); await pg.wait_for_timeout(150)
        check('una forma con agujeros pasa a selección con sus contornos', await T("()=>Array.isArray(__T.ED.selection.pts[0]) && __T.ED.selection.pts.length>1"))
        await pg.click('#edSelClear')

        print('Texto sobre una línea')
        await clear(); await pg.click('#edToolPen')
        for x, y, c in [(250, 1250, 0), (750, 850, 1), (1250, 1250, 1), (1750, 850, 0)]:
            sx, sy = await scr(x, y); await pg.mouse.move(sx, sy); await pg.mouse.down()
            if c: await pg.mouse.move(sx + 110, sy, steps=5)
            await pg.mouse.up()
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(150)
        await pg.locator('#edPadBar button', has_text='Guardar como trazado').first.click(); await pg.wait_for_timeout(150)
        check('la pluma guarda un trazado', await T("()=>__T.ED.layers.filter(L=>L.tz).length") == 1)
        await pg.click('#edRTabs [data-rp=paths]')
        await pg.locator('#edPathActs button', has_text='Texto encima').click(); await pg.wait_for_timeout(200)
        await pg.fill('#edText', 'Krafsti Studio'); await pg.dispatch_event('#edText', 'input'); await pg.wait_for_timeout(300)
        check('«Texto encima» pone el texto en el trazado', await T("()=>!!__T.edSelL().tp"))
        off0 = await T("()=>__T.edSelL().tp.off")
        c = await T("()=>{ const b=__T.edInkBox(__T.edSelL()); return [(b.x0+b.x1)/2,(b.y0+b.y1)/2]; }")
        sx, sy = await scr(*c); await pg.mouse.move(sx, sy); await pg.mouse.down(); await pg.mouse.move(sx + 40, sy, steps=5); await pg.mouse.up()
        check('arrastrar lo corre por la línea', await T("()=>__T.edSelL().tp.off") != off0)
        await add('[data-shape=ellipse]')
        await T("()=>{ const L=__T.edSelL(); L.sh.w=L.sh.h=500; L.x=1350; L.y=500; __T.edSelChanged(); }")
        await pg.click('#edTpFromShape'); await pg.fill('#edText', 'LLAVERO'); await pg.dispatch_event('#edText', 'input'); await pg.wait_for_timeout(300)
        b0 = await T("()=>{ const b=__T.edInkBox(__T.edSelL()); return b.x0; }")
        await T("()=>{ const c=__T.ED.layers.find(L=>L.type==='shape'); c.x+=100; __T.edDraw(); }")
        b1 = await T("()=>{ const b=__T.edInkBox(__T.edSelL()); return b.x0; }")
        check('si se mueve la forma, el texto va con ella', abs(b1 - b0 - 100) < 2, round(b1 - b0, 1))
        await pg.check('#edTpFlip')
        check('«Darle la vuelta»', await T("()=>__T.edSelL().tp.flip"))
        await shot('3_texto_en_linea')
        b0 = await T("()=>{ const L=__T.ED.layers.find(L=>L.tp&&L.t.text.startsWith('Krafsti')); const b=__T.edInkBox(L); return b.x0; }")
        await T("()=>{ const T=__T; T.ED.layers=T.ED.layers.filter(L=>!L.tz); T.edSelChanged(); }")
        b1 = await T("()=>{ const L=__T.ED.layers.find(L=>L.tp&&L.t.text.startsWith('Krafsti')); const b=__T.edInkBox(L); return b.x0; }")
        check('si se borra el trazado, el texto conserva su forma', abs(b0 - b1) < 0.5)

        print('SVG: letras tal como se ven')
        await clear(); await add('#edAddText'); await pg.fill('#edText', 'Hola'); await pg.dispatch_event('#edText', 'input')
        await T("()=>{ const L=__T.edSelL(); L.t.size=220; L.t.font='Pacifico'; L.t.color='#ff0000'; L.rot=-10; __T.edSelChanged(); }"); await pg.wait_for_timeout(400)
        diff = await ev("""async()=>{ const T=__T, svg=(await T.edBuildSvg()).svg; const W=500;
          const a=document.createElement('canvas'); a.width=a.height=W; const g=a.getContext('2d'); g.scale(W/T.ED.W,W/T.ED.H); T.ED.layers.forEach(L=>T.edDrawLayer(g,L,1));
          const img=new Image(); await new Promise(ok=>{ img.onload=ok; img.src='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(svg))); });
          const c=document.createElement('canvas'); c.width=c.height=W; c.getContext('2d').drawImage(img,0,0,W,W);
          const A=g.getImageData(0,0,W,W).data, B=c.getContext('2d').getImageData(0,0,W,W).data; let n=0,m=0; for(let i=3;i<A.length;i+=4){ if(A[i]>128) m++; if((A[i]>128)!==(B[i]>128)) n++; } return n/Math.max(1,m); }""")
        check('el SVG coincide con la pantalla', diff < 0.03, f'{diff*100:.1f} % distinto')

        print('Trazados, colores, desenfoque, duplicar')
        await clear(); await add('[data-shape=rect]'); await ev("()=>__T.edPane('layer')")
        await pg.click('#edToTz'); await pg.wait_for_timeout(200)
        check('«Guardar como trazado» de una forma', await T("()=>__T.ED.layers.filter(L=>L.tz).length==1 && __T.ED.layers.length==2"))
        await pg.click('#edRTabs [data-rp=layers]')
        await add('#edAddText'); await pg.fill('#edText', 'Aro'); await pg.dispatch_event('#edText', 'input')
        await T("()=>{ const L=__T.edSelL(); L.t.size=300; L.t.font='Bebas Neue'; L.y=1500; __T.edSelChanged(); }"); await pg.wait_for_timeout(300)
        await pg.click('#edToTz'); await pg.wait_for_timeout(600)
        check('«Guardar sus letras como trazado»', await T("()=>{ const z=__T.ED.layers.filter(L=>L.tz); return z.length==2 && (z[0].p.more||[]).length==5; }"))
        await pg.click('#edRTabs [data-rp=layers]')
        await T("()=>{ const T=__T, R=T.ED.layers.find(L=>L.type==='shape'); R.sh.fill.t='solid'; R.sh.fill.c1='#2a9d8f'; T.edSelect(T.ED.layers.find(L=>L.type==='text')); }")
        await pg.click('#edToolDrop')
        rp = await T("()=>{ const R=__T.ED.layers.find(L=>L.type==='shape'); return [R.x,R.y]; }")
        sx, sy = await scr(*rp); await pg.mouse.click(sx, sy); await pg.wait_for_timeout(200)
        check('«Tomar color» pinta la capa elegida y queda en el redondel', await T("()=>__T.ED.layers.find(L=>L.type==='text').t.color==='#2a9d8f' && __T.ED.cur==='#2a9d8f'"))
        await pg.click('#edPalBtn'); await pg.click('#edPalAddCur')
        await ev("()=>{ const i=document.getElementById('edPalPick'); i.value='#e9c46a'; i.dispatchEvent(new Event('change')); }")
        check('paleta del proyecto', await T("()=>JSON.stringify(__T.ED.pal)") == '["#2a9d8f","#e9c46a"]')
        check('la paleta se guarda con el proyecto', json.loads(await T("()=>__T.edProjectJSON()"))['doc'].get('Pal') == ['#2a9d8f', '#e9c46a'])
        await pg.mouse.click(5, 600)
        await add('[data-shape=ellipse]')
        w0 = await T("()=>__T.edSrc(__T.edSelL()).w")
        await ev("()=>__T.edPane('img')"); await pg.click('label[for=eis-blur]'); await pg.click('label[for=ebl-g]'); await pg.wait_for_timeout(300)
        w1 = await T("()=>__T.edSrc(__T.edSelL()).w")
        check('desenfoque normal (la capa crece con el margen)', w1 > w0, f'{w0} → {round(w1)}')
        await pg.click('label[for=ebl-m]'); await pg.wait_for_timeout(200)
        check('desenfoque de movimiento con dirección', await T("()=>__T.edSelL().fx.bl.t==='motion'") and await pg.is_visible('#edBlA'))
        await pg.click('label[for=ebl-no]'); await pg.wait_for_timeout(200)
        check('«Sin» lo quita', await T("()=>!__T.edSelL().fx"))
        await pg.click('label[for=eis-col]')
        await clear(); await add('[data-shape=star]'); await add('[data-shape=rect]'); await pick2()
        await pg.keyboard.press('Control+d'); await pg.wait_for_timeout(200)
        check('duplicar varias capas a la vez', await T("()=>__T.ED.layers.length==4 && __T.edSelSet().length==2"))

        print('Proyecto y copia automática')
        js = await T("()=>__T.edProjectJSON()")
        await ev("async(t)=>{ __T.ED.layers.length=0; await __T.edLoadProject(t,null); }", js); await pg.wait_for_timeout(300)
        check('guardar y abrir el proyecto', await T("()=>__T.ED.layers.length") == 4)
        await add('[data-shape=poly]')   # un cambio sin guardar
        await pg.wait_for_timeout(3200)
        pg.once('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.reload(); await pg.wait_for_timeout(1200)
        vis = await pg.is_visible('#edRecover')
        if vis: await pg.click('#edRecoverYes'); await pg.wait_for_timeout(600)
        check('tras recargar, ofrece recuperar el trabajo', vis and await T("()=>__T.ED.layers.length") == 5)

        print('Guía')
        await pg.click('#hGuide'); await pg.wait_for_timeout(150)
        n = await pg.locator('.guideitem').count()
        check('la guía tiene sus recetas', n >= 9, n)
        okg = True
        for i in range(n):
            if i: await pg.click('#hGuide')
            await pg.locator('.guideitem').nth(i).click(); await pg.wait_for_timeout(100)
            k = int((await pg.text_content('#guideStep')).split()[-1])
            for _ in range(k): await pg.click('#guideNext'); await pg.wait_for_timeout(60)
            okg = okg and await pg.is_hidden('#guideCard')
        check('se recorren todas las guías de principio a fin', okg)

        check('sin errores en la página', not ERRS, ERRS[:3])
        check('no pide nada a internet', not NET, NET[:3])
        await b.close()

asyncio.run(main())
print(f'\n{len(OK)} bien, {len(FAIL)} mal' + (': ' + ', '.join(FAIL) if FAIL else ''))
sys.exit(1 if FAIL else 0)
