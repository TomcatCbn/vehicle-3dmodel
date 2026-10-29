//! Session state machine — Share → Session → File states.
//!
//! Per CEA2.x: a Share is created with a QR, consumed by a campability
//! request that creates a Session. Each Session tracks file download states.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use tokio::sync::Mutex;

use super::files::FileInfo;

/// Share lifecycle states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShareStatus {
    /// QR generated, waiting for campability.
    Pending,
    /// campability succeeded, session created.
    Claimed,
    /// Expired (EndTime passed) or explicitly ended.
    Expired,
}

/// Session lifecycle states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionStatus {
    /// Ready for a download batch.
    Ready,
    /// A batch is in progress.
    Downloading,
    /// finishShare called, cleaning up.
    Closing,
    /// Fully closed.
    Closed,
}

/// Per-file download state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FileState {
    Waiting,
    Downloading,
    Paused,
    Completed,
    Failed,
    Cancelled,
}

/// A share — created when QR is generated, consumed on first campability.
pub struct Share {
    pub share_id: String,
    pub share_secret: String,
    pub end_time: i64,
    pub files: Vec<FileInfo>,
    pub status: ShareStatus,
    pub created_at: Instant,
}

/// A session — created by campability, bound to one TLS control connection.
pub struct Session {
    pub session_id: String,
    pub share_id: String,
    pub files: HashMap<String, FileDownloadState>,
    pub status: SessionStatus,
    pub created_at: Instant,
    pub last_activity: Instant,
}

#[derive(Debug, Clone)]
pub struct FileDownloadState {
    pub file_id: String,
    pub token: Option<String>,
    pub offset: u64,
    pub state: FileState,
}

/// Central state manager for all shares and sessions.
pub struct SessionManager {
    shares: HashMap<String, Arc<Mutex<Share>>>,
    sessions: HashMap<String, Arc<Mutex<Session>>>,
    /// Map share_id → session_id (one share = one session).
    share_to_session: HashMap<String, String>,
}

impl SessionManager {
    pub fn new() -> Self {
        Self {
            shares: HashMap::new(),
            sessions: HashMap::new(),
            share_to_session: HashMap::new(),
        }
    }

    /// Create a new share with a generated share_id and share_secret.
    pub fn create_share(
        &mut self,
        share_id: String,
        share_secret: String,
        end_time: i64,
        files: Vec<FileInfo>,
    ) -> Arc<Mutex<Share>> {
        let share = Arc::new(Mutex::new(Share {
            share_id: share_id.clone(),
            share_secret,
            end_time,
            files,
            status: ShareStatus::Pending,
            created_at: Instant::now(),
        }));
        self.shares.insert(share_id, share.clone());
        share
    }

    /// Find a share by ID.
    pub fn get_share(&self, share_id: &str) -> Option<Arc<Mutex<Share>>> {
        self.shares.get(share_id).cloned()
    }

    /// Attempt campability: verify secret, consume it, create session.
    ///
    /// Returns the session_id on success, or an error code (status_code constant).
    pub async fn campability(
        &mut self,
        share_id: &str,
        share_secret: &str,
        now_secs: i64,
    ) -> Result<String, i32> {
        use super::message::status_code;

        let share_arc = self.shares.get(share_id).cloned()
            .ok_or(status_code::SHARE_EXPIRED)?;

        let mut share = share_arc.lock().await;

        // Check expiry.
        if now_secs > share.end_time {
            share.status = ShareStatus::Expired;
            return Err(status_code::SHARE_EXPIRED);
        }

        // Check if already claimed.
        if share.status == ShareStatus::Claimed {
            return Err(status_code::BUSY);
        }
        if share.status == ShareStatus::Expired {
            return Err(status_code::SHARE_EXPIRED);
        }

        // Verify secret (constant-time-ish comparison).
        if !constant_time_eq(share_secret.as_bytes(), share.share_secret.as_bytes()) {
            return Err(status_code::AUTH_FAILED);
        }

        // Consume secret — one-time use.
        share.share_secret.clear();
        share.status = ShareStatus::Claimed;

        let share_id_owned = share.share_id.clone();
        let files = share.files.clone();
        drop(share); // release lock before creating session

        // Create session.
        let session_id = uuid::Uuid::new_v4().to_string();
        let mut files_map = HashMap::new();
        for f in &files {
            files_map.insert(
                f.file_id.clone(),
                FileDownloadState {
                    file_id: f.file_id.clone(),
                    token: None,
                    offset: 0,
                    state: FileState::Waiting,
                },
            );
        }

        let now = Instant::now();
        let session = Arc::new(Mutex::new(Session {
            session_id: session_id.clone(),
            share_id: share_id_owned.clone(),
            files: files_map,
            status: SessionStatus::Ready,
            created_at: now,
            last_activity: now,
        }));

        self.sessions.insert(session_id.clone(), session);
        self.share_to_session.insert(share_id_owned, session_id.clone());

        Ok(session_id)
    }

    /// Get a session by ID.
    pub fn get_session(&self, session_id: &str) -> Option<Arc<Mutex<Session>>> {
        self.sessions.get(session_id).cloned()
    }

    /// End a share/session (stop action).
    pub async fn end_share(&mut self, session_id: &str) -> Result<(), i32> {
        use super::message::status_code;

        let session_arc = self.sessions.get(session_id).cloned()
            .ok_or(status_code::SHARE_EXPIRED)?;

        let mut session = session_arc.lock().await;
        session.status = SessionStatus::Closing;

        // Cancel all unfinished files.
        for f in session.files.values_mut() {
            match f.state {
                FileState::Waiting | FileState::Downloading | FileState::Paused => {
                    f.state = FileState::Cancelled;
                }
                _ => {}
            }
        }

        session.status = SessionStatus::Closed;
        Ok(())
    }

    /// Remove expired shares (called periodically or on access).
    pub fn cleanup_expired(&mut self, now_secs: i64) {
        let mut to_remove = Vec::new();
        for (id, share_arc) in &self.shares {
            if let Ok(share) = share_arc.try_lock() {
                if share.status == ShareStatus::Expired || now_secs > share.end_time {
                    to_remove.push(id.clone());
                }
            }
        }
        for id in to_remove {
            self.shares.remove(&id);
        }
    }
}

impl Default for SessionManager {
    fn default() -> Self {
        Self::new()
    }
}

/// Constant-time byte comparison to prevent timing attacks on share_secret.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut result = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        result |= x ^ y;
    }
    result == 0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::file_transfer::files::FileInfo;
    use crate::file_transfer::message::FileKind;

    fn make_files() -> Vec<FileInfo> {
        vec![FileInfo {
            file_id: "f-0001".to_string(),
            path: std::path::PathBuf::from("/share/test.jpg"),
            name: "test.jpg".to_string(),
            size: 65536,
            kind: FileKind::Image,
        }]
    }

    #[tokio::test]
    async fn test_campability_success() {
        let mut mgr = SessionManager::new();
        mgr.create_share(
            "share-1".to_string(),
            "secret-123".to_string(),
            i64::MAX,
            make_files(),
        );

        let result = mgr.campability("share-1", "secret-123", 0).await;
        assert!(result.is_ok());
        let session_id = result.unwrap();
        assert!(!session_id.is_empty());

        // Session should exist.
        assert!(mgr.get_session(&session_id).is_some());
    }

    #[tokio::test]
    async fn test_campability_wrong_secret() {
        let mut mgr = SessionManager::new();
        mgr.create_share(
            "share-1".to_string(),
            "correct".to_string(),
            i64::MAX,
            make_files(),
        );

        let result = mgr.campability("share-1", "wrong", 0).await;
        assert!(matches!(result, Err(110))); // AUTH_FAILED
    }

    #[tokio::test]
    async fn test_campability_already_claimed() {
        let mut mgr = SessionManager::new();
        mgr.create_share(
            "share-1".to_string(),
            "secret".to_string(),
            i64::MAX,
            make_files(),
        );

        // First campability succeeds.
        let _ = mgr.campability("share-1", "secret", 0).await.unwrap();
        // Second should fail with BUSY (107).
        let result = mgr.campability("share-1", "secret", 0).await;
        assert!(matches!(result, Err(107))); // BUSY
    }

    #[tokio::test]
    async fn test_campability_expired() {
        let mut mgr = SessionManager::new();
        mgr.create_share(
            "share-1".to_string(),
            "secret".to_string(),
            100, // end_time in the past
            make_files(),
        );

        let result = mgr.campability("share-1", "secret", 200).await;
        assert!(matches!(result, Err(101))); // SHARE_EXPIRED
    }

    #[tokio::test]
    async fn test_end_share() {
        let mut mgr = SessionManager::new();
        mgr.create_share(
            "share-1".to_string(),
            "secret".to_string(),
            i64::MAX,
            make_files(),
        );

        let session_id = mgr.campability("share-1", "secret", 0).await.unwrap();

        // End the share.
        let result = mgr.end_share(&session_id).await;
        assert!(result.is_ok());

        let session = mgr.get_session(&session_id).unwrap();
        let session = session.lock().await;
        assert_eq!(session.status, SessionStatus::Closed);
        assert!(session.files.values().all(|f| f.state == FileState::Cancelled));
    }

    #[test]
    fn test_constant_time_eq() {
        assert!(constant_time_eq(b"hello", b"hello"));
        assert!(!constant_time_eq(b"hello", b"world"));
        assert!(!constant_time_eq(b"hello", b"hell"));
    }
}
