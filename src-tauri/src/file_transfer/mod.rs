//! File transfer module — CEA2.x protocol vehicle-side implementation.
//!
//! Decision 6: independent from SignalModel. Provides TLS 1.3 control + data
//! channels, QR generation, session state machine, and file management.
//!
//! M3.1: control channel (campability/list/stop) + QR + TLS + session state.

pub mod config;
pub mod control;
pub mod files;
pub mod message;
pub mod qr;
pub mod session;
pub mod tls;

use std::sync::Arc;

use tokio::net::TcpListener;
use tokio::sync::Mutex;

use session::SessionManager;
use tls::TlsServerConfig;

// Re-export so lib.rs can use FtConfig directly.
pub use config::FtConfig;

/// Running file transfer service state.
pub struct FileTransferService {
    config: Arc<FtConfig>,
    tls: Arc<TlsServerConfig>,
    sessions: Arc<Mutex<SessionManager>>,
    /// Local IP address for QR (detected at startup).
    local_ip: String,
    /// The current share (if any).
    current_share: Arc<Mutex<Option<ShareInfo>>>,
    /// Dynamically managed file list (default dir scan + user-picked files).
    selected_files: Arc<std::sync::Mutex<Vec<files::FileInfo>>>,
}

/// Active share metadata for frontend display.
#[derive(Debug, Clone, serde::Serialize)]
pub struct ShareInfo {
    pub share_id: String,
    pub qr_json: String,
    pub cert_sha256: String,
    pub local_ip: String,
    pub port: u16,
    pub end_time: i64,
    pub files: Vec<ShareFileInfo>,
    pub active: bool,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct ShareFileInfo {
    pub file_id: String,
    pub name: String,
    pub size: u64,
    pub kind: String,
}

impl FileTransferService {
    /// Create a new service: load TLS config, scan default files, detect local IP.
    pub fn new(config: FtConfig) -> Result<Self, String> {
        // Load TLS config.
        let tls = tls::load_tls_config(&config.cert_path, &config.key_path)
            .map_err(|e| e.to_string())?;

        // Detect local IP.
        let local_ip = detect_local_ip();

        // Pre-load default files from the share directory.
        let default_files = files::scan_dir(&config.file_dir);

        Ok(Self {
            config: Arc::new(config),
            tls: Arc::new(tls),
            sessions: Arc::new(Mutex::new(SessionManager::new())),
            local_ip,
            current_share: Arc::new(Mutex::new(None)),
            selected_files: Arc::new(std::sync::Mutex::new(default_files)),
        })
    }

    /// Start a new share: use the current file list, generate QR.
    pub async fn start_share(&self) -> Result<ShareInfo, String> {
        // Read the current file list (default scan + user-picked files).
        let files = {
            let guard = self.selected_files.lock().unwrap();
            guard.clone()
        };
        if files.is_empty() || files.len() > 9 {
            return Err(format!(
                "expected 1-9 shareable files, found {}. Add files via the picker or place files in {}",
                files.len(),
                self.config.file_dir.display(),
            ));
        }

        // Generate share_id and share_secret.
        let share_id = uuid::Uuid::new_v4().to_string();
        let share_secret = qr::generate_share_secret();
        let end_time = chrono::Utc::now().timestamp() + self.config.share_timeout_secs as i64;

        // Build QR JSON.
        let qr_json = qr::build_qr_json(
            &self.config,
            &self.local_ip,
            &self.tls.cert_sha256_hex,
            &share_id,
            &share_secret,
            &files,
            end_time,
        )
        .map_err(|e| e.to_string())?;

        // Create share in session manager.
        {
            let mut mgr = self.sessions.lock().await;
            mgr.create_share(share_id.clone(), share_secret, end_time, files.clone());
        }

        let share_info = ShareInfo {
            share_id: share_id.clone(),
            qr_json,
            cert_sha256: self.tls.cert_sha256_hex.clone(),
            local_ip: self.local_ip.clone(),
            port: self.config.control_port,
            end_time,
            files: files
                .iter()
                .map(|f| ShareFileInfo {
                    file_id: f.file_id.clone(),
                    name: f.name.clone(),
                    size: f.size,
                    kind: format!("{:?}", f.kind).to_lowercase(),
                })
                .collect(),
            active: true,
        };

        *self.current_share.lock().await = Some(share_info.clone());
        Ok(share_info)
    }

    /// Stop the current share.
    pub async fn stop_share(&self) -> Result<(), String> {
        let share = self.current_share.lock().await;
        if let Some(ref _info) = *share {
            // Find session and end it.
            let mgr = self.sessions.lock().await;
            // Try to find session by share_id — in M3.1 we just clear local state.
            drop(mgr);
        }
        *self.current_share.lock().await = None;
        Ok(())
    }

    /// Get current share info (for frontend polling).
    pub async fn get_status(&self) -> Option<ShareInfo> {
        self.current_share.lock().await.clone()
    }

    /// Get the current file list for display.
    pub fn get_files(&self) -> Vec<ShareFileInfo> {
        let guard = self.selected_files.lock().unwrap();
        to_share_file_infos(&guard)
    }

    /// Add user-selected file paths to the list. Deduplicates by path,
    /// skips non-media files, enforces the 9-file limit.
    pub fn add_files(&self, paths: Vec<std::path::PathBuf>) -> Vec<ShareFileInfo> {
        let mut guard = self.selected_files.lock().unwrap();
        for path in paths {
            if guard.len() >= 9 {
                break;
            }
            if guard.iter().any(|f| f.path == path) {
                continue;
            }
            let idx = (guard.len() + 1) as u32;
            if let Some(info) = files::file_info_from_path(&path, idx) {
                guard.push(info);
            }
        }
        files::reindex_files(&mut guard);
        to_share_file_infos(&guard)
    }

    /// Remove a file from the list by file_id.
    pub fn remove_file(&self, file_id: &str) -> Vec<ShareFileInfo> {
        let mut guard = self.selected_files.lock().unwrap();
        guard.retain(|f| f.file_id != file_id);
        files::reindex_files(&mut guard);
        to_share_file_infos(&guard)
    }

    /// Reset the file list to default directory scan.
    pub fn reset_files(&self) -> Vec<ShareFileInfo> {
        let mut guard = self.selected_files.lock().unwrap();
        *guard = files::scan_dir(&self.config.file_dir);
        to_share_file_infos(&guard)
    }

    /// Start TLS listeners on control and data ports.
    /// This should be spawned as a tokio task.
    pub async fn run_listeners(self: Arc<Self>) -> Result<(), String> {
        // Bind control port.
        let control_listener = TcpListener::bind(("0.0.0.0", self.config.control_port))
            .await
            .map_err(|e| format!("failed to bind control port {}: {e}", self.config.control_port))?;

        let log_fn = move |msg: &str| {
            // Write to the shared log file.
            let timestamp = chrono::Local::now().format("%H:%M:%S%.3f");
            if let Ok(mut file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(super_log_path())
            {
                use std::io::Write;
                let _ = writeln!(file, "[{timestamp}] {msg}");
            }
        };

        // Spawn control listener.
        let config = self.config.clone();
        let sessions = self.sessions.clone();
        let tls_acceptor = Arc::new(self.tls.acceptor.clone());

        tokio::spawn(async move {
            loop {
                match control_listener.accept().await {
                    Ok((tcp_stream, peer_addr)) => {
                        eprintln!("FT: control connection from {peer_addr}");
                        let acceptor = tls_acceptor.clone();
                        let config = config.clone();
                        let sessions = sessions.clone();
                        let log = log_fn.clone();

                        tokio::spawn(async move {
                            match acceptor.accept(tcp_stream).await {
                                Ok(tls_stream) => {
                                    control::handle_control_connection(
                                        tls_stream,
                                        config,
                                        sessions,
                                        log,
                                    )
                                    .await;
                                }
                                Err(e) => {
                                    eprintln!("FT: TLS handshake failed: {e}");
                                }
                            }
                        });
                    }
                    Err(e) => {
                        eprintln!("FT: control accept error: {e}");
                    }
                }
            }
        });

        Ok(())
    }
}

/// Detect the local LAN IPv4 address (non-loopback).
fn detect_local_ip() -> String {
    // Use a UDP socket trick: connect to a public IP (doesn't send packets),
    // then read the local address the OS chose.
    use std::net::UdpSocket;
    match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => {
            // Try connecting to a non-routable IP to find the local interface.
            if s.connect("192.0.2.1:80").is_ok() {
                if let Ok(addr) = s.local_addr() {
                    let ip = addr.ip().to_string();
                    if !ip.starts_with("127.") {
                        return ip;
                    }
                }
            }
        }
        Err(_) => {}
    }

    // Fallback: try to enumerate interfaces.
    // For simplicity in M3.1, return 127.0.0.1 as last resort.
    "127.0.0.1".to_string()
}

/// Get the log path (same as lib.rs LOG_PATH, duplicated here to avoid
/// circular dependency on the signal module's logging).
fn super_log_path() -> std::path::PathBuf {
    let base = std::env::current_dir()
        .ok()
        .and_then(|cwd| {
            let parent = cwd.parent().map(|p| p.to_path_buf());
            parent.filter(|p| p.join("src").exists() || p.join("logs").exists())
        })
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());
    let dir = base.join("logs");
    let _ = std::fs::create_dir_all(&dir);
    let ts = chrono::Local::now().format("%Y%m%d_%H%M%S");
    dir.join(format!("vehicle-simulator-{ts}.log"))
}

/// Tauri command: start a file transfer share.
#[tauri::command]
pub async fn ft_start_share(
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<ShareInfo, String> {
    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };
    svc.start_share().await
}

/// Tauri command: stop the current share.
#[tauri::command]
pub async fn ft_stop_share(
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<(), String> {
    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };
    svc.stop_share().await
}

/// Tauri command: get current share status.
#[tauri::command]
pub async fn ft_get_status(
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<Option<ShareInfo>, String> {
    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };
    Ok(svc.get_status().await)
}

/// Tauri command: get the current file list for display.
#[tauri::command]
pub fn ft_get_files(
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<Vec<ShareFileInfo>, String> {
    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };
    Ok(svc.get_files())
}

/// Tauri command: open a native file picker and add selected files.
#[tauri::command]
pub async fn ft_pick_files(
    app: tauri::AppHandle,
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<Vec<ShareFileInfo>, String> {
    use tauri_plugin_dialog::DialogExt;

    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };

    // async command runs on a background thread, so blocking_pick_files
    // blocks this worker thread — not the main thread — avoiding deadlock.
    let paths = app
        .dialog()
        .file()
        .set_title("选择要分享的文件")
        .add_filter("图片", &["jpg", "jpeg", "png", "gif", "bmp", "webp"])
        .add_filter("视频", &["mp4", "mov", "avi", "mkv", "webm"])
        .blocking_pick_files();

    let picked: Vec<std::path::PathBuf> = match paths {
        Some(files) => files.into_iter().filter_map(|f| f.into_path().ok()).collect(),
        None => return Ok(svc.get_files()),
    };

    Ok(svc.add_files(picked))
}

/// Tauri command: remove a file from the share list by file_id.
#[tauri::command]
pub fn ft_remove_file(
    file_id: String,
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<Vec<ShareFileInfo>, String> {
    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };
    Ok(svc.remove_file(&file_id))
}

/// Tauri command: reset file list to default directory scan.
#[tauri::command]
pub fn ft_reset_files(
    state: tauri::State<'_, std::sync::Mutex<Option<Arc<FileTransferService>>>>,
) -> Result<Vec<ShareFileInfo>, String> {
    let svc = {
        let guard = state.lock().unwrap();
        guard.as_ref().ok_or("file transfer service not initialized")?.clone()
    };
    Ok(svc.reset_files())
}

/// Convert a slice of FileInfo to ShareFileInfo for frontend display.
fn to_share_file_infos(files: &[files::FileInfo]) -> Vec<ShareFileInfo> {
    files
        .iter()
        .map(|f| ShareFileInfo {
            file_id: f.file_id.clone(),
            name: f.name.clone(),
            size: f.size,
            kind: format!("{:?}", f.kind).to_lowercase(),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_local_ip() {
        let ip = detect_local_ip();
        // Should be a valid IPv4 address.
        assert!(ip.parse::<std::net::Ipv4Addr>().is_ok());
    }
}
