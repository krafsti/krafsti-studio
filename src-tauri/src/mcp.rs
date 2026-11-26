// ---------- Conexión con asistentes (MCP), 1.34 ----------
// Para que un asistente (Claude Desktop, ChatGPT de escritorio, Claude Code…) maneje Krafsti Studio.
// Va apagado hasta que el usuario lo enciende dentro de la aplicación (botón «Asistentes»), y solo
// escucha en el propio ordenador (127.0.0.1), con una clave.
//
// Dos piezas:
// 1. Dentro de la aplicación abierta, un servidor MCP por HTTP («Streamable HTTP») en
//    http://127.0.0.1:47321/mcp. Las llamadas a herramientas se pasan a la página (evento «mcp-llamada»),
//    que las hace sobre Componer y contesta con el comando mcp_respuesta.
// 2. «krafsti-studio --mcp»: el mismo programa, sin ventana, hace de servidor MCP «local» (stdio), que es lo
//    que configuran Claude Desktop y ChatGPT. Contesta él mismo a lo básico (presentarse y dar la lista de
//    herramientas, así el asistente arranca aunque la aplicación esté cerrada) y reenvía cada herramienta a
//    la aplicación abierta. Encuentra el puerto y la clave en el archivo asistentes.json.

use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Emitter, State};

const HERRAMIENTAS: &str = include_str!("herramientas_mcp.json");
const VERSION: &str = env!("CARGO_PKG_VERSION");
const PUERTO: u16 = 47321;
const ESPERA: u64 = 180; // segundos que se espera a la página
const NO_ABIERTA: &str = "Krafsti Studio no está abierta o tiene apagada la conexión con asistentes. \
Pide al usuario que abra Krafsti Studio, pulse «Asistentes» arriba a la derecha y la encienda; luego vuelve a intentarlo.";
const INSTRUCCIONES: &str = "Krafsti Studio es un editor de diseños para cortadora láser e impresora UV. \
Estas herramientas manejan la pestaña Componer de la aplicación abierta en el ordenador del usuario, que ve cada cambio en directo. \
Las medidas van en milímetros. x_mm e y_mm son el centro de la capa, medido desde la esquina de arriba a la izquierda del lienzo. \
Empieza con ver_diseno; después de cambiar algo, mira el resultado con captura. Todo se puede deshacer con deshacer. \
Para la láser, el SVG en modo solo_contornos saca solo las líneas de corte; para unir un texto a un marco o hacer el agujero de un llavero, usa combinar_formas. \
Antes de descartar el trabajo del usuario (descartar_cambios) pregúntale.";

#[derive(Default)]
pub struct Estado {
    servidor: Mutex<Option<Arc<tiny_http::Server>>>,
    puerto: Mutex<u16>,
    clave: Mutex<String>,
    pendientes: Arc<Mutex<HashMap<u64, mpsc::Sender<Value>>>>,
    siguiente: Arc<AtomicU64>,
}

// archivo con el puerto y la clave: en la carpeta de ajustes de la aplicación
fn archivo_conexion() -> PathBuf {
    let base = if cfg!(windows) {
        std::env::var_os("APPDATA").map(PathBuf::from).unwrap_or_else(std::env::temp_dir)
    } else {
        std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".config")))
            .unwrap_or_else(std::env::temp_dir)
    };
    base.join("com.krafsti.studio").join("asistentes.json")
}

fn leer_conexion() -> Option<Value> {
    serde_json::from_str(&std::fs::read_to_string(archivo_conexion()).ok()?).ok()
}

fn escribir_conexion(v: &Value) {
    let f = archivo_conexion();
    if let Some(p) = f.parent() {
        let _ = std::fs::create_dir_all(p);
    }
    let _ = std::fs::write(&f, v.to_string());
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&f, std::fs::Permissions::from_mode(0o600));
    }
}

fn clave_nueva() -> String {
    use std::hash::{BuildHasher, Hasher};
    let t = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    (0..3u64)
        .map(|i| {
            let mut h = std::collections::hash_map::RandomState::new().build_hasher();
            h.write_u64(i);
            h.write_u128(t);
            h.write_u32(std::process::id());
            format!("{:016x}", h.finish())
        })
        .collect()
}

fn info(estado: &Estado) -> Value {
    let enc = estado.servidor.lock().unwrap().is_some();
    let puerto = *estado.puerto.lock().unwrap();
    json!({
        "encendido": enc,
        "puerto": puerto,
        "clave": *estado.clave.lock().unwrap(),
        "url": format!("http://127.0.0.1:{}/mcp", if puerto > 0 { puerto } else { PUERTO }),
        "programa": std::env::current_exe().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default(),
        "archivo": archivo_conexion().to_string_lossy(),
        "pedido": std::env::args().any(|a| a == "--asistentes"),
    })
}

#[tauri::command]
pub fn mcp_estado(estado: State<Estado>) -> Value {
    info(&estado)
}

#[tauri::command]
pub fn mcp_encender(app: AppHandle, estado: State<Estado>, encender: bool) -> Result<Value, String> {
    if !encender {
        if let Some(s) = estado.servidor.lock().unwrap().take() {
            s.unblock();
        }
        let clave = estado.clave.lock().unwrap().clone();
        escribir_conexion(&json!({"encendido": false, "puerto": 0, "clave": clave}));
        return Ok(info(&estado));
    }
    if estado.servidor.lock().unwrap().is_some() {
        return Ok(info(&estado));
    }
    // la clave se conserva entre veces (así un asistente configurado por HTTP no hay que tocarlo)
    let clave = leer_conexion()
        .and_then(|v| v.get("clave").and_then(|c| c.as_str()).map(String::from))
        .filter(|c| c.len() >= 32)
        .unwrap_or_else(clave_nueva);
    let mut abierto = None;
    for p in PUERTO..PUERTO + 10 {
        if let Ok(s) = tiny_http::Server::http(("127.0.0.1", p)) {
            abierto = Some((s, p));
            break;
        }
    }
    let (srv, puerto) = abierto.ok_or("No se pudo abrir ningún puerto del 47321 al 47330.")?;
    let srv = Arc::new(srv);
    *estado.puerto.lock().unwrap() = puerto;
    *estado.clave.lock().unwrap() = clave.clone();
    *estado.servidor.lock().unwrap() = Some(srv.clone());
    escribir_conexion(&json!({"encendido": true, "puerto": puerto, "clave": clave, "version": VERSION}));
    let pend = estado.pendientes.clone();
    let sig = estado.siguiente.clone();
    std::thread::spawn(move || {
        for req in srv.incoming_requests() {
            let (app, clave, pend, sig) = (app.clone(), clave.clone(), pend.clone(), sig.clone());
            std::thread::spawn(move || atender(req, &app, &clave, &pend, &sig));
        }
    });
    Ok(info(&estado))
}

#[tauri::command]
pub fn mcp_respuesta(estado: State<Estado>, id: u64, resultado: Value) {
    if let Some(tx) = estado.pendientes.lock().unwrap().remove(&id) {
        let _ = tx.send(resultado);
    }
}

fn texto_error(t: &str) -> Value {
    json!({"content": [{"type": "text", "text": t}], "isError": true})
}

// lo que se contesta sin la página: Some(Some(respuesta)), Some(None) = aviso sin respuesta, None = hace falta la página
fn respuesta_local(m: &Value) -> Option<Option<Value>> {
    let metodo = m.get("method").and_then(|v| v.as_str()).unwrap_or("");
    let id = m.get("id").cloned();
    let ok = |r: Value| Some(Some(json!({"jsonrpc": "2.0", "id": id.clone().unwrap_or(Value::Null), "result": r})));
    if id.is_none() && m.get("method").is_some() {
        return Some(None); // avisos («notifications/…»)
    }
    if m.get("method").is_none() {
        return Some(None); // respuestas del cliente: no se esperan
    }
    match metodo {
        "initialize" => {
            let pedida = m.pointer("/params/protocolVersion").and_then(|v| v.as_str()).unwrap_or("");
            let pv = if ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"].contains(&pedida) { pedida } else { "2025-06-18" };
            ok(json!({
                "protocolVersion": pv,
                "capabilities": {"tools": {"listChanged": false}},
                "serverInfo": {"name": "krafsti-studio", "title": "Krafsti Studio", "version": VERSION},
                "instructions": INSTRUCCIONES
            }))
        }
        "ping" => ok(json!({})),
        "tools/list" => ok(json!({"tools": serde_json::from_str::<Value>(HERRAMIENTAS).unwrap_or(json!([]))})),
        "tools/call" => None,
        _ => Some(Some(json!({"jsonrpc": "2.0", "id": id, "error": {"code": -32601, "message": format!("No existe el método {metodo}")}}))),
    }
}

fn llamar_pagina(m: &Value, app: &AppHandle, pend: &Mutex<HashMap<u64, mpsc::Sender<Value>>>, sig: &AtomicU64) -> Value {
    let id = sig.fetch_add(1, Ordering::SeqCst) + 1;
    let (tx, rx) = mpsc::channel();
    pend.lock().unwrap().insert(id, tx);
    let nombre = m.pointer("/params/name").cloned().unwrap_or(Value::Null);
    let args = m.pointer("/params/arguments").cloned().unwrap_or(json!({}));
    let r = if app.emit("mcp-llamada", json!({"id": id, "nombre": nombre, "args": args})).is_err() {
        texto_error("No se pudo hablar con la ventana de Krafsti Studio.")
    } else {
        rx.recv_timeout(Duration::from_secs(ESPERA))
            .unwrap_or_else(|_| texto_error("Krafsti Studio no contestó a tiempo (¿hay una ventana o un aviso abierto?)."))
    };
    pend.lock().unwrap().remove(&id);
    json!({"jsonrpc": "2.0", "id": m.get("id").cloned().unwrap_or(Value::Null), "result": r})
}

fn atender(mut req: tiny_http::Request, app: &AppHandle, clave: &str, pend: &Mutex<HashMap<u64, mpsc::Sender<Value>>>, sig: &AtomicU64) {
    let cabeceras: Vec<(String, String)> =
        req.headers().iter().map(|h| (h.field.as_str().as_str().to_ascii_lowercase(), h.value.as_str().to_string())).collect();
    let cab = |n: &str| cabeceras.iter().find(|(k, _)| k == &n.to_ascii_lowercase()).map(|(_, v)| v.clone());
    let url = req.url().to_string();
    let (ruta, consulta) = url.split_once('?').unwrap_or((&url, ""));
    let responder = |req: tiny_http::Request, codigo: u16, cuerpo: String| {
        let mut r = tiny_http::Response::from_string(cuerpo).with_status_code(codigo).with_chunked_threshold(usize::MAX);
        if let Ok(h) = tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]) {
            r = r.with_header(h);
        }
        let _ = req.respond(r);
    };
    if ruta != "/mcp" {
        return responder(req, 404, r#"{"error":"Aquí solo está /mcp"}"#.into());
    }
    // solo programas del propio ordenador: una página web de otro sitio no puede usarlo
    if let Some(o) = cab("Origin") {
        if !(o.starts_with("http://127.0.0.1") || o.starts_with("http://localhost")) {
            return responder(req, 403, r#"{"error":"Origen no permitido"}"#.into());
        }
    }
    let dada = cab("Authorization")
        .and_then(|a| a.strip_prefix("Bearer ").map(|s| s.trim().to_string()))
        .or_else(|| cab("X-Krafsti-Clave"))
        .or_else(|| consulta.split('&').find_map(|p| p.strip_prefix("clave=").map(String::from)));
    if dada.as_deref() != Some(clave) {
        return responder(req, 401, r#"{"error":"Falta la clave de Krafsti Studio, o no es la buena"}"#.into());
    }
    if req.method() != &tiny_http::Method::Post {
        return responder(req, 405, r#"{"error":"Usa POST"}"#.into());
    }
    let mut cuerpo = String::new();
    if req.as_reader().read_to_string(&mut cuerpo).is_err() {
        return responder(req, 400, r#"{"error":"No se pudo leer la petición"}"#.into());
    }
    let Ok(m) = serde_json::from_str::<Value>(&cuerpo) else {
        return responder(req, 400, json!({"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"JSON no válido"}}).to_string());
    };
    let una = |m: &Value| -> Option<Value> {
        match respuesta_local(m) {
            Some(r) => r,
            None => Some(llamar_pagina(m, app, pend, sig)),
        }
    };
    let salida = if let Some(lista) = m.as_array() {
        let v: Vec<Value> = lista.iter().filter_map(|x| una(x)).collect();
        if v.is_empty() { None } else { Some(Value::Array(v)) }
    } else {
        una(&m)
    };
    match salida {
        Some(v) => responder(req, 200, v.to_string()),
        None => {
            let _ = req.respond(tiny_http::Response::empty(202));
        }
    }
}

// ---------- el puente «--mcp» (stdio) ----------
fn reenviar(m: &Value) -> Result<Value, String> {
    let c = leer_conexion().ok_or(NO_ABIERTA)?;
    if !c.get("encendido").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(NO_ABIERTA.into());
    }
    let puerto = c.get("puerto").and_then(|v| v.as_u64()).unwrap_or(0) as u16;
    let clave = c.get("clave").and_then(|v| v.as_str()).unwrap_or("");
    let dir: SocketAddr = ([127, 0, 0, 1], puerto).into();
    let mut s = TcpStream::connect_timeout(&dir, Duration::from_secs(3)).map_err(|_| NO_ABIERTA.to_string())?;
    let _ = s.set_read_timeout(Some(Duration::from_secs(ESPERA + 20)));
    let cuerpo = m.to_string();
    let pet = format!(
        "POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{puerto}\r\nAuthorization: Bearer {clave}\r\nContent-Type: application/json\r\nAccept: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{cuerpo}",
        cuerpo.len()
    );
    s.write_all(pet.as_bytes()).map_err(|_| NO_ABIERTA.to_string())?;
    // se lee hasta que el servidor cierra (o hasta tener el cuerpo entero). Ojo: entre el asistente y la
    // aplicación puede haber un intermediario (ChatGPT de escritorio, en Windows, pasa las conexiones por uno)
    // que cambia la respuesta a «Transfer-Encoding: chunked» y pone las cabeceras en minúsculas.
    let mut buf = Vec::new();
    let mut trozo = [0u8; 65536];
    loop {
        if respuesta_completa(&buf) {
            break;
        }
        match s.read(&mut trozo) {
            Ok(0) => break,
            Ok(k) => buf.extend_from_slice(&trozo[..k]),
            Err(_) if !buf.is_empty() => break,
            Err(_) => return Err("Krafsti Studio no contestó a tiempo.".into()),
        }
    }
    let (estado, cuerpo) = separar_respuesta(&buf).ok_or_else(|| format!("Respuesta incompleta de Krafsti Studio: «{}»", muestra(&buf)))?;
    if estado == "401" {
        return Err("La clave guardada no coincide: en Krafsti Studio apaga y vuelve a encender «Asistentes».".into());
    }
    serde_json::from_slice(&cuerpo).map_err(|e| format!("Respuesta extraña de Krafsti Studio (código {estado}, {e}): «{}»", muestra(&buf)))
}

fn muestra(b: &[u8]) -> String {
    let t: String = String::from_utf8_lossy(b).chars().take(300).collect();
    t.replace('\r', "\\r").replace('\n', "\\n")
}

fn cabeceras(buf: &[u8]) -> Option<(usize, String)> {
    let p = buf.windows(4).position(|w| w == b"\r\n\r\n")?;
    Some((p + 4, String::from_utf8_lossy(&buf[..p]).to_ascii_lowercase()))
}

fn valor<'a>(cab: &'a str, nombre: &str) -> Option<&'a str> {
    cab.lines().find_map(|l| {
        let (k, v) = l.split_once(':')?;
        if k.trim() == nombre { Some(v.trim()) } else { None }
    })
}

fn es_chunked(cab: &str) -> bool {
    valor(cab, "transfer-encoding").map(|v| v.contains("chunked")).unwrap_or(false)
}

// deshace «chunked»: tamaño en hexadecimal, salto, datos, salto… hasta un trozo de tamaño 0.
// Devuelve None si aún no ha llegado entero.
fn deschunk(mut d: &[u8]) -> Option<Vec<u8>> {
    let mut out = Vec::new();
    loop {
        let p = d.windows(2).position(|w| w == b"\r\n")?;
        let linea = String::from_utf8_lossy(&d[..p]);
        let n = usize::from_str_radix(linea.split(';').next().unwrap_or("").trim(), 16).ok()?;
        d = &d[p + 2..];
        if n == 0 {
            return Some(out);
        }
        if d.len() < n + 2 {
            return None;
        }
        out.extend_from_slice(&d[..n]);
        d = &d[n + 2..];
    }
}

fn respuesta_completa(buf: &[u8]) -> bool {
    let Some((ini, cab)) = cabeceras(buf) else { return false };
    if es_chunked(&cab) {
        return deschunk(&buf[ini..]).is_some();
    }
    match valor(&cab, "content-length").and_then(|v| v.parse::<usize>().ok()) {
        Some(n) => buf.len() >= ini + n,
        None => false, // sin largo: hasta que se cierre
    }
}

fn separar_respuesta(buf: &[u8]) -> Option<(String, Vec<u8>)> {
    let (ini, cab) = cabeceras(buf)?;
    let estado = cab.split_whitespace().nth(1).unwrap_or("").to_string();
    let resto = &buf[ini..];
    let cuerpo = if es_chunked(&cab) {
        deschunk(resto)?
    } else if let Some(n) = valor(&cab, "content-length").and_then(|v| v.parse::<usize>().ok()) {
        resto.get(..n)?.to_vec()
    } else {
        resto.to_vec()
    };
    Some((estado, cuerpo))
}

#[cfg(test)]
mod pruebas {
    use super::*;
    #[test]
    fn lee_chunked_y_normal() {
        let c = b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\nserver: x\r\n\r\n5\r\n{\"a\":\r\n2\r\n1}\r\n0\r\n\r\n";
        assert!(respuesta_completa(c));
        let (e, b) = separar_respuesta(c).unwrap();
        assert_eq!(e, "200");
        assert_eq!(b, b"{\"a\":1}");
        assert!(!respuesta_completa(&c[..c.len() - 5]));
        let n = b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\n{\"a\":1}";
        assert!(respuesta_completa(n));
        assert_eq!(separar_respuesta(n).unwrap().1, b"{\"a\":1}");
        assert!(!respuesta_completa(&n[..n.len() - 1]));
    }
}

fn responder_puente(m: &Value) -> Option<Value> {
    if let Some(r) = respuesta_local(m) {
        return r;
    }
    let id = m.get("id").cloned().unwrap_or(Value::Null);
    Some(reenviar(m).unwrap_or_else(|e| json!({"jsonrpc": "2.0", "id": id, "result": texto_error(&e)})))
}

pub fn puente_stdio() {
    let entrada = std::io::stdin();
    let mut salida = std::io::stdout();
    for linea in entrada.lock().lines() {
        let Ok(linea) = linea else { break };
        let t = linea.trim();
        if t.is_empty() {
            continue;
        }
        let r = match serde_json::from_str::<Value>(t) {
            Err(_) => Some(json!({"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "JSON no válido"}})),
            Ok(Value::Array(lista)) => {
                let v: Vec<Value> = lista.iter().filter_map(responder_puente).collect();
                if v.is_empty() { None } else { Some(Value::Array(v)) }
            }
            Ok(m) => responder_puente(&m),
        };
        if let Some(r) = r {
            if writeln!(salida, "{r}").is_err() || salida.flush().is_err() {
                break;
            }
        }
    }
}
