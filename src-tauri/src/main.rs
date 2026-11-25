// Krafsti Studio como aplicación de escritorio: abre index.html en su propia ventana.
// En Windows, sin ventana de consola detrás.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    krafsti_studio_lib::run()
}
