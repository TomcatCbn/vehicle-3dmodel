//! File transfer configuration (decision 6 D6.1, D6.2).

use std::path::PathBuf;

/// Configuration for the file transfer service.
#[derive(Debug, Clone)]
pub struct FtConfig {
    /// Control channel TLS port (default 19890 per CEA2.x).
    pub control_port: u16,
    /// Data channel TLS port (default 19891 per CEA2.x).
    pub data_port: u16,
    /// Path to the PEM certificate file.
    pub cert_path: PathBuf,
    /// Path to the PEM private key file.
    pub key_path: PathBuf,
    /// Directory containing shareable files.
    pub file_dir: PathBuf,
    /// OEM identifier in QR (e.g. "svw").
    pub oem: String,
    /// Max parallel file downloads per session (default 2 per CEA2.x).
    pub max_parallel: u8,
    /// QR EndTime window in seconds from creation (default 90 per CEA2.x).
    pub share_timeout_secs: u64,
}

impl Default for FtConfig {
    fn default() -> Self {
        // Resolve certs relative to the crate root (src-tauri/).
        let crate_root = std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."));
        let cert_dir = if crate_root.join("certs").exists() {
            crate_root.join("certs")
        } else if crate_root.join("src-tauri/certs").exists() {
            // Running from project root.
            crate_root.join("src-tauri/certs")
        } else {
            PathBuf::from("src-tauri/certs")
        };

        // Resolve file_dir relative to project root.
        let project_root = if crate_root.join("public").exists() {
            crate_root
        } else if crate_root.parent().map(|p| p.join("public").exists()).unwrap_or(false) {
            crate_root.parent().unwrap().to_path_buf()
        } else {
            PathBuf::from(".")
        };

        Self {
            control_port: 19890,
            data_port: 19891,
            cert_path: cert_dir.join("test-cert.pem"),
            key_path: cert_dir.join("test-key.pem"),
            file_dir: project_root.join("public").join("share-files"),
            oem: "svw".to_string(),
            max_parallel: 2,
            share_timeout_secs: 90,
        }
    }
}
