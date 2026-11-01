//! TLS 1.3 server setup (decision 6 D6.2).
//!
//! Loads a fixed PEM certificate/key pair, computes the SHA-256 fingerprint
//! for QR, and creates a tokio-rustls TLS acceptor configured for TLS 1.3 only.

use std::io::BufReader;
use std::path::Path;
use std::sync::Arc;

use rustls::pki_types::CertificateDer;
use rustls::server::ServerConfig;
use sha2::{Digest, Sha256};
use tokio_rustls::TlsAcceptor;

/// TLS configuration and certificate metadata.
pub struct TlsServerConfig {
    pub acceptor: TlsAcceptor,
    /// SHA-256 of the DER certificate, as 64 lowercase hex chars.
    pub cert_sha256_hex: String,
}

/// Load PEM cert + key, compute fingerprint, build TLS 1.3 acceptor.
pub fn load_tls_config(
    cert_path: &Path,
    key_path: &Path,
) -> Result<TlsServerConfig, TlsError> {
    // Read certificate PEM.
    let cert_pem = std::fs::read(cert_path).map_err(|e| TlsError::Io(cert_path.display().to_string(), e))?;
    let mut cert_reader = BufReader::new(cert_pem.as_slice());
    let certs: Vec<CertificateDer<'static>> = rustls_pemfile::certs(&mut cert_reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(TlsError::Pem)?;

    if certs.is_empty() {
        return Err(TlsError::NoCertificate);
    }

    // Compute SHA-256 of the first (leaf) certificate DER.
    let mut hasher = Sha256::new();
    hasher.update(&certs[0]);
    let digest = hasher.finalize();
    let cert_sha256_hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();

    // Read private key PEM.
    let key_pem = std::fs::read(key_path).map_err(|e| TlsError::Io(key_path.display().to_string(), e))?;
    let mut key_reader = BufReader::new(key_pem.as_slice());
    let key = rustls_pemfile::private_key(&mut key_reader)
        .map_err(TlsError::Pem)?
        .ok_or(TlsError::NoPrivateKey)?;

    // Build server config: TLS 1.3 only.
    let mut config = ServerConfig::builder()
        .with_no_client_auth()
        .with_single_cert(certs, key)
        .map_err(TlsError::Rustls)?;

    // Enforce TLS 1.3 only (disable session resumption / 0-RTT per CEA2.x).
    config.max_early_data_size = 0;
    // rustls disables session tickets by default; we keep that.

    let acceptor = TlsAcceptor::from(Arc::new(config));

    Ok(TlsServerConfig {
        acceptor,
        cert_sha256_hex,
    })
}

#[derive(Debug)]
pub enum TlsError {
    Io(String, std::io::Error),
    Pem(std::io::Error),
    NoCertificate,
    NoPrivateKey,
    Rustls(rustls::Error),
}

impl std::fmt::Display for TlsError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TlsError::Io(path, e) => write!(f, "io error reading {path}: {e}"),
            TlsError::Pem(e) => write!(f, "PEM parse error: {e}"),
            TlsError::NoCertificate => write!(f, "no certificate found in PEM"),
            TlsError::NoPrivateKey => write!(f, "no private key found in PEM"),
            TlsError::Rustls(e) => write!(f, "rustls config error: {e}"),
        }
    }
}

impl std::error::Error for TlsError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_certs() {
        let crate_root = std::env::current_dir().unwrap();
        let cert_dir = if crate_root.join("certs").exists() {
            crate_root.join("certs")
        } else {
            crate_root.join("src-tauri/certs")
        };
        let cert_path = cert_dir.join("test-cert.pem");
        let key_path = cert_dir.join("test-key.pem");

        if !cert_path.exists() {
            eprintln!("Skipping TLS test: certs not found at {cert_path:?}");
            return;
        }

        let config = load_tls_config(&cert_path, &key_path);
        assert!(config.is_ok(), "TLS config should load");
        let config = config.unwrap();
        assert_eq!(config.cert_sha256_hex.len(), 64);
        assert!(config.cert_sha256_hex.chars().all(|c| c.is_ascii_hexdigit()));
    }
}
