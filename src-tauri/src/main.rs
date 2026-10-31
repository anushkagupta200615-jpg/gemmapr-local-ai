// Letshack Bouncer shell. Pure display wrapper: it expects the engine to be
// already serving on http://127.0.0.1:8765 (see `python -m app run`).
//
//   window "hud"  -> live dashboard
//   window "gate" -> fullscreen gate overlay, always-on-top (the bouncer)
//
// If the engine is not running when this starts, the HUD shows the browser's
// connection error; `python -m app run` fixes it.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running the bouncer shell");
}
