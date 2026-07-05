// Athena desktop shell (Tauri v2).
// v1 is a thin webview around the React app; the Python backend runs
// separately. TODO(cursor): spawn/supervise the backend as a sidecar
// process so one click starts everything (tauri-plugin-shell).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Athena");
}
