#!/usr/bin/env python3
"""Pruebas de Krafsti Studio (desde la 1.32; en la 1.34 se suman Guardar, carpetas, el trabajo de Vectorizar y el MCP). Comprueban en Chrome (Playwright) todo lo importante de la herramienta,
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

        print('1.34: Guardar, carpetas, trabajo de Vectorizar y asistentes')
        labels = await ev("()=>['dl','edSvg','edDl','bgDl','cAll'].map(i=>document.getElementById(i).textContent)")
        check('los botones dicen «Guardar»', all(t.startswith('Guardar') for t in labels) and not await ev("()=>/Descargar/.test(document.body.innerText)"), labels)
        r = await ev("""async()=>{ const got={}; window.showSaveFilePicker=async o=>({name:o.suggestedName, async createWritable(){ return {write:async d=>{ got.d=d; }, close:async()=>{ got.closed=true; }}; }});
          let msg=''; const ok=await __T.saveFile('prueba.svg','<svg/>','image/svg+xml',t=>msg=t);
          window.showSaveFilePicker=async()=>{ throw new DOMException('x','AbortError'); }; let msg2=''; const ok2=await __T.saveFile('b.png',new Blob(['x']),'image/png',t=>msg2=t);
          delete window.showSaveFilePicker; return [ok, msg, !!got.closed, got.d && got.d.size, ok2, msg2]; }""")
        check('«Guardar» usa la ventana «Guardar como» (y cancelar no guarda)', r[0] and r[1] == 'Guardado: prueba.svg' and r[2] and r[3] == 6 and r[4] is False and 'cancelado' in r[5], r)
        # proyecto en carpeta (con una carpeta de mentira en memoria): guardar, abrir, y abrir el archivo suelto en el navegador
        await clear(); await ev("()=>__T.edPane('add')")
        await ev(PNG_JS, [300, 200, "g.fillStyle='#e9c46a'; g.fillRect(0,0,300,200); g.fillStyle='#1f4e5f'; g.fillRect(50,50,100,60);", 'edFile'])
        await pg.wait_for_timeout(600); await add('[data-shape=star]')
        FAKE = """window.__fake=(files)=>{ const mk=pre=>({kind:'directory',name:pre||'carpeta',path:'/x/'+(pre||'carpeta'),
            async getDirectoryHandle(n){ return mk(pre?pre+'/'+n:n); },
            async getFileHandle(n,o){ const p=pre?pre+'/'+n:n; if(!(o&&o.create)&&!files[p]) throw new DOMException('no','NotFoundError');
              return {kind:'file',name:n, async getFile(){ return new File([files[p]],n,{lastModified:Date.now()}); },
                async createWritable(){ const parts=[]; return {write:async d=>{ parts.push(d); }, close:async()=>{ files[p]=new Blob(parts); }}; }}; },
            async *entries(){ for(const p of Object.keys(files)){ const rel=pre ? (p.startsWith(pre+'/')?p.slice(pre.length+1):null) : p; if(rel && !rel.includes('/')) yield [rel, await this.getFileHandle(rel)]; } } });
          return mk(''); };"""
        await ev("()=>{" + FAKE + "}")
        r = await ev("""async()=>{ const T=__T, files={}; window.__files=files; T.edFlush(); T.ED.name='prueba'; const d=__fake(files); T['(v=>edDir=v)'](d); await T.edSaveToDir(); return Object.keys(files).sort(); }""")
        check('guardar en carpeta: el proyecto y su imagen en imagenes/', len(r) == 2 and r[0].startswith('imagenes/imagen-') and r[1] == 'prueba.krafsti', r)
        r = await ev("""async()=>{ const T=__T; T.ED.layers.length=0; T['(v=>edDirty=v)'](false); const res=await T.edOpenFromDir(__fake(window.__files));
          const I=T.ED.layers.find(L=>L.type==='img'), c=I && T.EDSRC.get(I.src); return [T.ED.layers.length, c ? c.width : 0, res.missing.length, !!T.edDir]; }""")
        check('abrir carpeta: vuelven las capas con su imagen', r == [2, 300, 0, True], r)
        r = await ev("""async()=>{ const T=__T, t=await window.__files['prueba.krafsti'].text(); T.ED.layers.length=0; let err='';
          try{ await T.edLoadProject(t,null); }catch(e){ err=e.message; } return [err, T.ED.layers.length]; }""")
        check('«Abrir archivo…» con un proyecto de carpeta avisa (no lo abre vacío)', 'Abrir carpeta' in r[0] and r[1] == 0, r)
        # el trabajo de Vectorizar
        await pg.click('#tabVec'); await ev("()=>vecPane('mode')"); await pg.click('label[for=m-ill]')
        await ev(PNG_JS, [400, 300, "g.fillStyle='#fff'; g.fillRect(0,0,400,300); g.fillStyle='#d94f30'; g.beginPath(); g.arc(200,150,100,0,7); g.fill(); g.fillStyle='#1f4e5f'; g.fillRect(40,40,80,60); g.fillStyle='#e9c46a'; g.fillRect(260,200,90,60);", 'file'])
        await pg.wait_for_timeout(2500)
        await ev("()=>{ const e=document.getElementById('iColors'); e.value=6; e.dispatchEvent(new Event('input')); }"); await pg.wait_for_timeout(1500)
        r0 = await ev("""()=>{ const S=__T.S; S.groups=[{id:1,name:'Fondo'},{id:2,name:'Dibujo'}]; S.gseq=2; S.grpOf=S.trace.layers.map((_,i)=>i%2?2:1); S.include=S.include.map((v,i)=>i!==1&&v);
          S.stOff={'g2':0.5}; S.hgt={'g1':40}; document.getElementById('stMin').value=1.3; document.getElementById('wmm').value=123;
          return {n:S.trace.layers.length, tones:S.trace.layers.map(L=>L.hex).join(), grp:S.grpOf.join(), inc:S.include.join()}; }""")
        work = await ev("()=>__T.vecWorkJSON()")
        await ev("()=>{ document.getElementById('iColors').value=16; __T.loadSrc(__T.makeSample(),'ejemplo'); }"); await pg.click('label[for=m-fill]'); await pg.wait_for_timeout(2000)
        await ev("async(t)=>{ await __T.vecLoadWork(JSON.parse(t)); }", work); await pg.wait_for_timeout(500)
        r1 = await ev("""()=>{ const S=__T.S; return {n:S.trace.layers.length, tones:S.trace.layers.map(L=>L.hex).join(), grp:S.grpOf.join(), inc:S.include.join(),
          mode:document.querySelector('input[name=mode]:checked').value, k:document.getElementById('iColors').value, out:document.getElementById('iColorsOut').textContent,
          names:S.groups.map(g=>g.name).join(), stOff:S.stOff.g2, hgt:S.hgt.g1, stMin:document.getElementById('stMin').value, w:document.getElementById('wmm').value}; }""")
        check('trabajo de Vectorizar: vuelven tonos, grupos y lo incluido', r1['tones'] == r0['tones'] and r1['grp'] == r0['grp'] and r1['inc'] == r0['inc'] and r1['names'] == 'Fondo,Dibujo', (r0, r1))
        check('trabajo de Vectorizar: vuelven el modo y los ajustes', r1['mode'] == 'illus' and r1['k'] == '6' and r1['out'] == '6' and r1['stOff'] == 0.5 and r1['hgt'] == 40 and r1['stMin'] == '1.3' and r1['w'] == '123', r1)
        # asistentes (MCP): las herramientas de Componer, sin la aplicación (las de guardar en disco se prueban en ella)
        await pg.click('#tabEd'); await clear()
        M = lambda n, a={}: ev("async([n,a])=>{ const r=await window.__krafstiMCP.llamar(n,a); return {e:!!r.isError, t:(r.content||[]).map(c=>c.type==='text'?c.text:c.type).join('|')}; }", [n, a])
        r = await M('nuevo_diseno', {'forma': 'circular', 'diametro_mm': 40, 'descartar_cambios': True})
        check('asistente: lienzo circular de 40 mm', not r['e'] and await T("()=>__T.ED.shape==='circle' && Math.abs(__T.ED.W*25.4/__T.ED.ppi-40)<0.1"), r['t'])
        await M('anadir_forma', {'tipo': 'circulo', 'ancho_mm': 40, 'relleno': '#f2e6cf'})
        r = await M('anadir_texto', {'texto': 'Lucía', 'fuente': 'Pacifico', 'alto_mm': 7, 'alrededor_del_circulo': 'arriba'})
        check('asistente: texto alrededor del círculo', not r['e'] and await T("()=>{ const L=__T.ED.layers.find(L=>L.type==='text'); return L && L.ring && L.ring.pos==='top' && L.t.font==='Pacifico'; }"), r['t'][:120])
        await M('anadir_forma', {'tipo': 'circulo', 'ancho_mm': 4, 'x_mm': 20, 'y_mm': 4})
        ids = await T("()=>__T.ED.layers.filter(L=>L.type==='shape').map(L=>L.id)")
        r = await M('combinar_formas', {'ids': ids, 'operacion': 'restar'})
        check('asistente: restar (agujero del llavero)', not r['e'] and await T("()=>{ const L=__T.ED.layers.find(L=>L.bname==='Resta'); return L && (L.p.more||[]).length==1; }"), r['t'][:120])
        n0 = await T("()=>__T.ED.layers.length")
        r = await M('anadir_texto', {'texto': 'x', 'fuente': 'Comic Sans'})
        check('asistente: un error no deja nada a medias', r['e'] and 'Comic Sans' in r['t'] and await T("()=>__T.ED.layers.length") == n0)
        r = await M('nuevo_diseno', {})
        check('asistente: no borra el trabajo sin permiso', r['e'] and 'descartar_cambios' in r['t'])
        r = await M('captura', {'ancho_px': 300})
        check('asistente: captura del diseño', r['t'].startswith('image|'), r['t'][:60])
        r = await M('ver_diseno')
        d = json.loads(r['t'])
        check('asistente: ver_diseno', len(d['capas_de_abajo_arriba']) == 2 and d['lienzo']['forma'] == 'circular', [c['id'] for c in d['capas_de_abajo_arriba']])
        r = await M('deshacer', {'veces': 1})
        check('asistente: deshacer', not r['e'] and await T("()=>__T.ED.layers.length") == 3, r['t'])
        # (1.35) la resolución va dentro del PNG y del JPG
        r = await ev("""async()=>{ const T=__T; T.ED.ppi=300; const out={};
          const p=new Uint8Array(await (await T.edBlob('png')).arrayBuffer()); let i=8, n=0, ppm=0, ok=true;
          while(i<p.length){ const dv=new DataView(p.buffer,i), len=dv.getUint32(0), ty=String.fromCharCode(...p.subarray(i+4,i+8));
            if(ty==='pHYs'){ n++; ppm=new DataView(p.buffer,i+8).getUint32(0); const c=T.crc32(p.subarray(i+4,i+8+len)); ok=c===new DataView(p.buffer,i+8+len).getUint32(0); }
            if(ty==='IEND') break; i+=12+len; }
          const j=new Uint8Array(await (await T.edBlob('jpg')).arrayBuffer());
          const img=await createImageBitmap(await T.edBlob('png'));
          return [n, ppm, ok, j[13], (j[14]<<8)|j[15], img.width===T.ED.W]; }""")
        check('PNG y JPG llevan dentro los 300 ppp', r == [1, 11811, True, 1, 300, True], r)
        await clear()

        print('1.36: pestañas, fusión de capas, quitar la selección y fondo')
        await clear()
        r = await ev("()=>[[...document.querySelectorAll('.mtabs .mtab')].map(b=>b.id).join(), document.getElementById('pageEd').hidden, document.getElementById('tabConv').firstChild.textContent.trim()]")
        check('empieza en Componer; orden Componer, Vectorizar, Retocar, Convertir', r == ['tabEd,tabVec,tabBg,tabConv', False, 'Convertir'], r)
        M = lambda n, a={}: ev("async([n,a])=>{ const r=await window.__krafstiMCP.llamar(n,a); return {e:!!r.isError, t:(r.content||[]).map(c=>c.type==='text'?c.text:c.type).join('|')}; }", [n, a])
        await M('nuevo_diseno', {'ancho_mm': 20, 'alto_mm': 20, 'descartar_cambios': True})
        PX = """(x,y)=>{ const c=__T.edRender(false), d=c.getContext('2d').getImageData(Math.round(x*c.width),Math.round(y*c.height),1,1).data; return [d[0],d[1],d[2],d[3]]; }"""
        await M('anadir_forma', {'tipo': 'rectangulo', 'ancho_mm': 20, 'alto_mm': 20, 'relleno': '#3366cc'})
        await M('anadir_forma', {'tipo': 'rectangulo', 'ancho_mm': 10, 'alto_mm': 20, 'x_mm': 5, 'relleno': '#ff8000'})
        top = await T("()=>__T.ED.layers[__T.ED.layers.length-1].id")
        res = {}
        for modo, nombre in [('multiplicar', 'multiply'), ('trama', 'screen'), ('restar', 'subtract'), ('Luz focal', 'pin-light'), ('color más oscuro', 'darker-color')]:
            r = await M('cambiar_capa', {'id': top, 'modo_fusion': modo})
            res[nombre] = await ev("(f)=>eval(f)(0.25,0.5)", PX)
        # azul 33,66,cc (51,102,204) y naranja ff,80,00 (255,128,0)
        ok = (res['multiply'][:3] == [51, 51, 0] and res['screen'][:3] == [255, 179, 204] and res['subtract'][:3] == [0, 0, 204]
              and res['pin-light'][:3] == [255, 102, 0] and res['darker-color'][:3] == [51, 102, 204])
        check('modos de fusión (Multiplicar, Trama, Restar, Luz focal, Color más oscuro)', ok, res)
        r = await ev("(f)=>eval(f)(0.75,0.5)", PX)
        check('la fusión no toca lo que la capa no cubre', r[:3] == [51, 102, 204], r)
        await T("()=>{ const s=document.querySelector('#eis-bm'); s.click(); return 1; }")
        await ev("(id)=>{ __T.ED.sel=id; __T.edSelChanged(); __T.edPane('img'); }", top)
        r = await ev("()=>[document.getElementById('edImgBlend').hidden, document.getElementById('edBm').value, document.getElementById('edBm').options.length]")
        check('pestaña Imagen › Fusión con los 27 modos', r == [False, 'darker-color', 27], r)
        r = await ev("async()=>{ const s=await __T.edBuildSvg(); return [/mix-blend-mode/.test(s.svg), s.notes.some(n=>/no existe en SVG/.test(n))]; }")
        check('SVG: el modo que no existe en SVG avisa', r == [False, True], r)
        await M('cambiar_capa', {'id': top, 'modo_fusion': 'multiply'})
        r = await ev("async()=>{ const s=await __T.edBuildSvg(); return /mix-blend-mode:multiply/.test(s.svg); }")
        check('SVG: Multiplicar va como mix-blend-mode', r is True)
        await ev("()=>{ __T.ED.selection={pts:[[{x:1,y:1},{x:50,y:1},{x:50,y:50}]],inv:false,feather:0}; __T.edSyncSel(); }")
        b1 = await ev("()=>!document.getElementById('edDeselBtn').hidden")
        await pg.keyboard.press('Escape'); await pg.keyboard.press('Escape'); await pg.keyboard.press('Escape')
        await ev("()=>{ __T.ED.selection={pts:[[{x:1,y:1},{x:50,y:1},{x:50,y:50}]],inv:false,feather:0}; __T.edSyncSel(); }")
        await pg.click('#edDeselBtn')
        r = await ev("()=>[!__T.ED.selection, document.getElementById('edDeselBtn').hidden]")
        check('«Quitar selección» aparece con una selección y la quita', b1 and r == [True, True], [b1, r])
        await pg.click('[data-pane=add]'); await pg.click('#edFondoBtn')
        r = await ev("()=>{ const F=__T.ED.layers.find(L=>L.fondo); return [!!F, __T.ED.layers.filter(L=>!L.tz)[0]===F, __T.edName(F), F.lock]; }")
        check('«Fondo» crea una capa al final de todo', r == [True, True, 'Fondo', True], r)
        await M('cambiar_lienzo', {'forma': 'circular', 'diametro_mm': 30})
        r = await ev("()=>{ const F=__T.ED.layers.find(L=>L.fondo); __T.edSrc(F); return [F.sh.kind, F.sh.w===__T.ED.W, F.x===__T.ED.W/2]; }")
        check('el fondo sigue al lienzo (también redondo)', r == ['ellipse', True, True], r)
        r = await M('anadir_fondo', {'color': '#f2e6cf', 'degradado_hasta': '#d94f30'})
        check('asistente: anadir_fondo con degradado', not r['e'] and await T("()=>__T.ED.layers.filter(L=>L.fondo).length===1 && __T.ED.layers.find(L=>L.fondo).sh.fill.t==='linear'"), r['t'])
        await clear()

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
