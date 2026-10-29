// M1.3 — SignalModel wired into Tauri: managed state + tick loop + command + event.
// Decisions 5 (D5.2 backend tick) + 7 (nested VehicleState).

mod signal;

use std::fs::OpenOptions;
use std::io::Write;
use std::sync::{Arc, OnceLock};
use std::time::Duration;

use serde::Serialize;
use tauri::{Emitter, Manager, State};
use tokio::sync::Mutex;

use signal::{SignalModel, VehicleCommand, VehicleState};

/// Per-session log path (under the project's logs/ directory, timestamped filename).
/// Each app launch gets its own file so logs from different runs don't mix.
static LOG_PATH: OnceLock<std::path::PathBuf> = OnceLock::new();

fn log_path() -> &'static std::path::Path {
    LOG_PATH.get_or_init(|| {
        // Resolve <repo>/logs/ relative to the executable or cwd.
        // In dev mode (cargo run), cwd is the src-tauri directory; the
        // project root is one level up. In packaged builds, cwd may be
        // elsewhere — fall back to cwd/logs in that case.
        let base = std::env::current_dir()
            .ok()
            .and_then(|cwd| {
                let parent = cwd.parent().map(|p| p.to_path_buf());
                // Use parent if it contains the project (heuristic: has logs/ or src/).
                parent.filter(|p| p.join("src").exists() || p.join("logs").exists())
            })
            .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());
        let dir = base.join("logs");
        let _ = std::fs::create_dir_all(&dir);
        let ts = chrono::Local::now().format("%Y%m%d_%H%M%S");
        dir.join(format!("vehicle-simulator-{ts}.log"))
    })
}

/// Append a line to the session log file (shared by Rust and JS frontend).
fn debug_log(msg: &str) {
    let timestamp = chrono::Local::now().format("%H:%M:%S%.3f");
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path())
    {
        let _ = writeln!(file, "[{timestamp}] {msg}");
    }
}

/// App-wide state shared between the tick loop and Tauri commands.
struct AppState {
    model: Arc<Mutex<SignalModel>>,
}

/// Payload emitted on every tick so the frontend can follow the snapshot.
#[derive(Serialize, Clone)]
struct StateChangedPayload {
    state: VehicleState,
}

/// Tauri command: apply a vehicle command (from local UI / future MQTT / BLE).
/// Returns the updated VehicleState on success, or an error string on interlock failure.
#[tauri::command]
async fn send_vehicle_command(
    command: VehicleCommand,
    state: State<'_, AppState>,
) -> Result<VehicleState, String> {
    let mut model = state.model.lock().await;
    match model.apply_command(&command) {
        Ok(()) => Ok(model.snapshot().clone()),
        Err(e) => Err(e.to_string()),
    }
}

/// Tauri command: get the current vehicle state snapshot.
#[tauri::command]
async fn get_vehicle_state(state: State<'_, AppState>) -> Result<VehicleState, String> {
    let model = state.model.lock().await;
    Ok(model.snapshot().clone())
}

/// Tauri command: write a debug log line from JS frontend.
#[tauri::command]
async fn debug_log_js(message: String) -> Result<(), String> {
    debug_log(&format!("JS: {message}"));
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![send_vehicle_command, get_vehicle_state, debug_log_js])
        .setup(|app| {
            // Instantiate the default AURA T6 signal model.
            let model = Arc::new(Mutex::new(SignalModel::aura_t6()));
            app.manage(AppState { model: model.clone() });

            // Log session start and print the log file path for easy access.
            debug_log("=== vehicle-simulator session started ===");
            eprintln!("📋 Debug log: {}", log_path().display());

            // Spawn the backend tick loop (~30 Hz, dt ≈ 33 ms).
            // Per decision 5 D5.2: smooth physics live in the backend; the
            // frontend only damp-interpolates toward these snapshots.
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut ticker =
                    tokio::time::interval(Duration::from_millis(33));
                loop {
                    ticker.tick().await;
                    let snapshot = {
                        let mut model = model.lock().await;
                        model.tick(0.033);
                        model.snapshot().clone()
                    };
                    let _ = handle.emit(
                        "signal://state-changed",
                        StateChangedPayload { state: snapshot },
                    );
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
