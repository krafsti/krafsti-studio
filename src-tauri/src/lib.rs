// Lo que la página no puede hacer sola dentro de la aplicación: escribir en disco el archivo
// que el usuario eligió en la ventana «Guardar como». La página manda los bytes tal cual
// y la ruta (codificada como en una URL) en la cabecera «ruta».

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
    std::fs::write(decodificar(ruta), datos).map_err(|e| format!("No se pudo guardar: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![guardar_archivo])
        .run(tauri::generate_context!())
        .expect("no se pudo abrir Krafsti Studio");
}
