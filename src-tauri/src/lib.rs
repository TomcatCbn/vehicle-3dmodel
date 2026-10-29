// M1.3 — SignalModel wired into Tauri: managed state + tick loop + command + event.
// Decisions 5 (D5.2 backend tick) + 7 (nested VehicleState).
// M3.1 — File transfer service (CEA2.x protocol, decision 6).

mod file_transfer;
mod signal;

use std::fs::OpenOptions;
use std::io::Write;
use std::sync::{Arc, OnceLock};
use std::time::Duration;

use serde::Serialize;
use tauri::{Emitter, Manager, State};
use tokio::sync::Mutex;

use file_transfer::{FileTransferService, FtConfig};
use signal::{SignalModel, VehicleCommand, VehicleState};
use signal::state::PowerState;

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

/// Tauri command: change power state (decision 8 D8.2).
/// Returns the updated VehicleState on success.
#[tauri::command]
async fn set_power_state(
    state: PowerState,
    app_state: State<'_, AppState>,
) -> Result<VehicleState, String> {
    let mut model = app_state.model.lock().await;
    match model.apply_command(&VehicleCommand::SetPower { state }) {
        Ok(()) => Ok(model.snapshot().clone()),
        Err(e) => Err(e.to_string()),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            send_vehicle_command,
            get_vehicle_state,
            set_power_state,
            debug_log_js,
            file_transfer::ft_start_share,
            file_transfer::ft_stop_share,
            file_transfer::ft_get_status,
            file_transfer::ft_get_files,
            file_transfer::ft_pick_files,
            file_transfer::ft_remove_file,
            file_transfer::ft_reset_files,
        ])
        .setup(|app| {
            // Instantiate the default AURA T6 signal model.
            let model = Arc::new(Mutex::new(SignalModel::aura_t6()));
            app.manage(AppState { model: model.clone() });

            // Initialize file transfer service (decision 6 D6.5: Tauri-only).
            match FileTransferService::new(FtConfig::default()) {
                Ok(ft_svc) => {
                    let ft_arc = Arc::new(ft_svc);
                    app.manage(std::sync::Mutex::new(Some(ft_arc.clone())));

                    // Start TLS listeners in background.
                    let ft_for_listeners = ft_arc.clone();
                    tauri::async_runtime::spawn(async move {
                        if let Err(e) = Arc::clone(&ft_for_listeners)
                            .run_listeners()
                            .await
                        {
                            eprintln!("⚠️ File transfer listeners failed: {e}");
                            debug_log(&format!("FT: listener error: {e}"));
                        }
                    });

                    debug_log("FT: file transfer service initialized");
                }
                Err(e) => {
                    eprintln!("⚠️ File transfer service init failed: {e}");
                    debug_log(&format!("FT: init failed: {e}"));
                    // Manage an empty state so commands can return a clean error.
                    app.manage(std::sync::Mutex::new(None::<Arc<FileTransferService>>));
                }
            }

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
