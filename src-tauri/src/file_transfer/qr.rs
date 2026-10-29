//! QR payload generation (decision 6 D6.4).
//!
//! Rust generates the QR JSON string (≤2048 UTF-8 bytes); the frontend
//! renders the actual QR image.

use serde::{Deserialize, Serialize};

use super::config::FtConfig;
use super::files::FileInfo;
use super::message::MAX_QR_BYTES;

/// The complete QR payload structure (CEA2.x §02).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QrPayload {
    #[serde(rename = "OEM")]
    pub oem: String,
    /// Placeholder in LAN mode — phone is already on the same network.
    #[serde(rename = "WIFI")]
    pub wifi: String,
    #[serde(rename = "Server")]
    pub server: QrServer,
    #[serde(rename = "App")]
    pub app: String,
    #[serde(rename = "Files")]
    pub files: Vec<crate::file_transfer::files::QrFileEntry>,
    #[serde(rename = "ShareId")]
    pub share_id: String,
    #[serde(rename = "EndTime")]
    pub end_time: i64,
    #[serde(rename = "Security")]
    pub security: QrSecurity,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QrServer {
    #[serde(rename = "IPv4")]
    pub ipv4: String,
    pub port: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QrSecurity {
    pub mode: String,
    #[serde(rename = "certSha256")]
    pub cert_sha256: String,
    #[serde(rename = "shareSecret")]
    pub share_secret: String,
}

/// Build a QR payload, serialize to JSON, and verify byte length.
///
/// - `local_ip`: the LAN IPv4 address the phone will connect to.
/// - `cert_sha256`: hex SHA-256 of the DER certificate (64 hex chars).
/// - `share_id`: UUID v4 string.
/// - `share_secret`: 43-char Base64URL (no padding) from 32 random bytes.
/// - `files`: 1-9 file entries.
/// - `end_time`: UTC seconds when the share expires.
pub fn build_qr_json(
    config: &FtConfig,
    local_ip: &str,
    cert_sha256: &str,
    share_id: &str,
    share_secret: &str,
    files: &[FileInfo],
    end_time: i64,
) -> Result<String, QrError> {
    if files.is_empty() || files.len() > 9 {
        return Err(QrError::FileCountInvalid(files.len()));
    }

    let payload = QrPayload {
        oem: config.oem.clone(),
        wifi: "T:SAE;S:lan-mode;P:;;;;".to_string(), // placeholder
        server: QrServer {
            ipv4: local_ip.to_string(),
            port: config.control_port,
        },
        app: "com.vehicle.simulator.share".to_string(),
        files: files.iter().map(|f| f.to_qr_entry()).collect(),
        share_id: share_id.to_string(),
        end_time,
        security: QrSecurity {
            mode: "tls13-qr-v1".to_string(),
            cert_sha256: cert_sha256.to_string(),
            share_secret: share_secret.to_string(),
        },
    };

    let json = serde_json::to_string(&payload).map_err(|e| QrError::Json(e.to_string()))?;

    let byte_len = json.len();
    if byte_len > MAX_QR_BYTES {
        return Err(QrError::TooLarge { actual: byte_len, max: MAX_QR_BYTES });
    }

    Ok(json)
}

/// Generate a 32-byte random share secret as 43-char Base64URL (no padding).
pub fn generate_share_secret() -> String {
    use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
    let mut bytes = [0u8; 32];
    use std::io::Read;
    // Use /dev/urandom on Unix, or fall back to a simple PRNG seeded by time.
    // For a test simulator this is sufficient.
    if let Ok(mut f) = std::fs::File::open("/dev/urandom") {
        let _ = f.read_exact(&mut bytes);
    } else {
        // Fallback: use uuid + timestamp for entropy (test only).
        let seed = format!("{}{}", uuid::Uuid::new_v4(), chrono::Local::now().timestamp_nanos_opt().unwrap_or(0));
        for (i, b) in seed.bytes().enumerate() {
            if i < 32 {
                bytes[i] = b;
            }
        }
    }
    URL_SAFE_NO_PAD.encode(bytes)
}

#[derive(Debug)]
pub enum QrError {
    FileCountInvalid(usize),
    Json(String),
    TooLarge { actual: usize, max: usize },
}

impl std::fmt::Display for QrError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            QrError::FileCountInvalid(n) => write!(f, "file count {n} not in 1..=9"),
            QrError::Json(s) => write!(f, "JSON serialization error: {s}"),
            QrError::TooLarge { actual, max } => write!(f, "QR payload {actual} bytes exceeds {max}"),
        }
    }
}

impl std::error::Error for QrError {}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::file_transfer::config::FtConfig;
    use crate::file_transfer::files::FileInfo;
    use crate::file_transfer::message::FileKind;

    fn make_test_files(n: usize) -> Vec<FileInfo> {
        (0..n)
            .map(|i| FileInfo {
                file_id: format!("f-{:04}", i + 1),
                path: std::path::PathBuf::from(format!("/share/file-{i}.jpg")),
                name: format!("file-{i}.jpg"),
                size: 65536,
                kind: FileKind::Image,
            })
            .collect()
    }

    #[test]
    fn test_qr_json_valid() {
        let config = FtConfig::default();
        let files = make_test_files(3);
        let json = build_qr_json(
            &config,
            "192.168.1.100",
            &"aa".repeat(32), // 64 hex chars
            "11111111-1111-4111-8111-111111111111",
            "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU",
            &files,
            1792569690,
        );
        assert!(json.is_ok());
        let json = json.unwrap();
        assert!(json.len() <= MAX_QR_BYTES);
        assert!(json.contains("tls13-qr-v1"));
        assert!(json.contains("192.168.1.100"));
        assert!(json.contains("19890"));
    }

    #[test]
    fn test_qr_empty_files_rejected() {
        let config = FtConfig::default();
        let result = build_qr_json(
            &config,
            "127.0.0.1",
            &"a".repeat(64),
            "test-share-id",
            &"x".repeat(43),
            &[],
            0,
        );
        assert!(matches!(result, Err(QrError::FileCountInvalid(0))));
    }

    #[test]
    fn test_share_secret_43_chars() {
        let secret = generate_share_secret();
        assert_eq!(secret.len(), 43);
        assert!(secret.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_'));
    }
}
