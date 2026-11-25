// Lo que la página no puede hacer sola dentro de la aplicación:
// - escribir y leer archivos y carpetas que el usuario eligió con las ventanas del sistema
//   (así no salen los avisos de permisos del navegador al guardar en una carpeta);
// - el servidor MCP (mcp.rs), para que un asistente (Claude, ChatGPT…) maneje Krafsti Studio.
// La página manda los bytes tal cual y la ruta (codificada como en una URL) en la cabecera «ruta».

mod mcp;

use serde::Serialize;
use std::path::Path;
use std::time::UNIX_EPOCH;

fn decodificar(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            if let Ok(v) = u8::from_str_radix(&s[i + 1..i + 3], 16) {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn mtime_ms(m: &std::fs::Metadata) -> f64 {
    m.modified()
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_millis() as f64)
        .unwrap_or(0.0)
}

#[tauri::command]
fn guardar_archivo(request: tauri::ipc::Request) -> Result<(), String> {
    let tauri::ipc::InvokeBody::Raw(datos) = request.body() else {
        return Err("No llegaron los datos del archivo.".into());
    };
    let ruta = request
        .headers()
        .get("ruta")
        .and_then(|v| v.to_str().ok())
        .ok_or("No llegó la ruta del archivo.")?;
    let ruta = decodificar(ruta);
    if let Some(p) = Path::new(&ruta).parent() {
        if !p.as_os_str().is_empty() {
            std::fs::create_dir_all(p).map_err(|e| format!("No se pudo crear la carpeta: {e}"))?;
        }
    }
    std::fs::write(&ruta, datos).map_err(|e| format!("No se pudo guardar: {e}"))
}

#[tauri::command]
fn leer_archivo(ruta: String) -> Result<tauri::ipc::Response, String> {
    std::fs::read(&ruta)
        .map(tauri::ipc::Response::new)
        .map_err(|e| format!("No se pudo leer «{ruta}»: {e}"))
}

#[derive(Serialize)]
struct Info {
    existe: bool,
    carpeta: bool,
    mtime: f64,
    tam: u64,
}

#[tauri::command]
fn info_archivo(ruta: String) -> Info {
    match std::fs::metadata(&ruta) {
        Ok(m) => Info { existe: true, carpeta: m.is_dir(), mtime: mtime_ms(&m), tam: m.len() },
        Err(_) => Info { existe: false, carpeta: false, mtime: 0.0, tam: 0 },
    }
}

#[derive(Serialize)]
struct Entrada {
    nombre: String,
    carpeta: bool,
    mtime: f64,
}

#[tauri::command]
fn listar_carpeta(ruta: String) -> Result<Vec<Entrada>, String> {
    let mut v = Vec::new();
    for e in std::fs::read_dir(&ruta).map_err(|e| format!("No se pudo abrir la carpeta: {e}"))? {
        let Ok(e) = e else { continue };
        let Ok(m) = e.metadata() else { continue };
        v.push(Entrada { nombre: e.file_name().to_string_lossy().into_owned(), carpeta: m.is_dir(), mtime: mtime_ms(&m) });
    }
    Ok(v)
}

#[tauri::command]
fn preparar_carpeta(ruta: String, crear: bool) -> Result<(), String> {
    if crear {
        std::fs::create_dir_all(&ruta).map_err(|e| format!("No se pudo crear la carpeta: {e}"))
    } else if Path::new(&ruta).is_dir() {
        Ok(())
    } else {
        Err(format!("No existe la carpeta «{ruta}»"))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // «krafsti-studio --mcp»: no abre la ventana; hace de puente entre el asistente (Claude Desktop,
    // ChatGPT…) y la aplicación abierta. Lo pone en marcha el asistente.
    if std::env::args().any(|a| a == "--mcp") {
        mcp::puente_stdio();
        return;
    }
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(mcp::Estado::default())
        .invoke_handler(tauri::generate_handler![
            guardar_archivo,
            leer_archivo,
            info_archivo,
            listar_carpeta,
            preparar_carpeta,
            mcp::mcp_encender,
            mcp::mcp_estado,
            mcp::mcp_respuesta
        ])
        .run(tauri::generate_context!())
        .expect("no se pudo abrir Krafsti Studio");
}
