//! Wire message types for CEA2.x file transfer protocol.
//!
//! All control messages share a common envelope and are serialized as JSON
//! with a 4-byte uint32 big-endian length prefix.

use serde::{Deserialize, Serialize};

// ─── Envelope ───

/// Top-level message envelope (decision 6, §control报文).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Envelope {
    pub ver: String,
    #[serde(rename = "Type")]
    pub msg_type: MessageType,
    #[serde(rename = "ID")]
    pub id: String,
    #[serde(rename = "From")]
    pub from: From,
    #[serde(rename = "Direction")]
    pub direction: Direction,
    #[serde(rename = "Security")]
    pub security: serde_json::Value,
    #[serde(rename = "Priority")]
    pub priority: u8,
    #[serde(rename = "TimeStamp")]
    pub timestamp: i64,
    /// Present on Request only.
    #[serde(rename = "Action", default, skip_serializing_if = "Option::is_none")]
    pub action: Option<Action>,
    /// Present on Request only.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parameter: Option<serde_json::Value>,
    /// Present on Response only.
    #[serde(rename = "RequestID", default, skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    /// Present on Response only; 0 = success.
    #[serde(rename = "StatusCode", default, skip_serializing_if = "Option::is_none")]
    pub status_code: Option<i32>,
    /// Present on Notification only.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code: Option<i32>,
    /// Present on Notification only.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub info: Option<serde_json::Value>,
    /// Request timeout in ms; 0 = no timeout.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires: Option<u64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum MessageType {
    Request,
    Response,
    Notification,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct From {
    #[serde(rename = "OEM")]
    pub oem: String,
    #[serde(rename = "Device")]
    pub device: String,
    #[serde(rename = "App")]
    pub app: String,
    #[serde(rename = "OS")]
    pub os: String,
    #[serde(rename = "Port", default, skip_serializing_if = "Option::is_none")]
    pub port: Option<u16>,
    #[serde(rename = "IPv4", default, skip_serializing_if = "Option::is_none")]
    pub ipv4: Option<String>,
    #[serde(rename = "IPv6", default, skip_serializing_if = "Option::is_none")]
    pub ipv6: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Direction {
    P2v,
    V2p,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Action {
    Campability,
    List,
    Download,
    Pause,
    Resume,
    Cancel,
    Stop,
}

// ─── Action Parameters ───

/// campability request parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CampabilityParam {
    #[serde(rename = "shareId")]
    pub share_id: String,
    #[serde(rename = "shareSecret")]
    pub share_secret: String,
}

/// campability response parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CampabilityResponse {
    #[serde(rename = "shareId")]
    pub share_id: String,
    #[serde(rename = "sessionId")]
    pub session_id: String,
    pub limits: Limits,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Limits {
    #[serde(rename = "maxParallelFiles")]
    pub max_parallel_files: u8,
    #[serde(rename = "dataIdleTimeoutMs")]
    pub data_idle_timeout_ms: u64,
    #[serde(rename = "sessionIdleTimeoutMs")]
    pub session_idle_timeout_ms: u64,
}

/// list request parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListParam {
    #[serde(rename = "sessionId")]
    pub session_id: String,
}

/// list response parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListResponse {
    #[serde(rename = "sessionId")]
    pub session_id: String,
    pub files: Vec<WireFile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WireFile {
    #[serde(rename = "fileId")]
    pub file_id: String,
    #[serde(rename = "filePath", default, skip_serializing_if = "Option::is_none")]
    pub file_path: Option<String>,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub size: Option<u64>,
    pub kind: FileKind,
    pub status: FileStatus,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FileKind {
    Image,
    Video,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FileStatus {
    Available,
    Missing,
    Denied,
    Unavailable,
}

/// download request parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadParam {
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "fileId")]
    pub file_id: String,
    pub token: String,
    #[serde(rename = "filePath")]
    pub file_path: String,
    pub offset: u64,
}

/// download response parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadResponse {
    #[serde(rename = "sessionId")]
    pub session_id: String,
    #[serde(rename = "fileId")]
    pub file_id: String,
    #[serde(rename = "dataPort")]
    pub data_port: u16,
    pub size: u64,
    #[serde(rename = "acceptedOffset")]
    pub accepted_offset: u64,
    #[serde(rename = "contentLength")]
    pub content_length: u64,
}

/// stop request parameter (share scope).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StopParam {
    #[serde(rename = "sessionId")]
    pub session_id: String,
    pub scope: String,
    pub reason: String,
}

/// Error response parameter.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorParam {
    pub message: String,
    pub retryable: bool,
}

// ─── Status Codes ───

pub mod status_code {
    pub const OK: i32 = 0;
    pub const OEM_MISMATCH: i32 = 1;
    pub const VERSION_UNSUPPORTED: i32 = 2;
    pub const INVALID_ARGUMENT: i32 = 100;
    pub const SHARE_EXPIRED: i32 = 101;
    pub const FILE_MISSING: i32 = 102;
    pub const RESOURCE_CHANGED: i32 = 103;
    pub const INVALID_TOKEN: i32 = 104;
    pub const INVALID_STATE: i32 = 105;
    pub const OFFSET_MISMATCH: i32 = 106;
    pub const BUSY: i32 = 107;
    pub const METADATA_TOO_LARGE: i32 = 108;
    pub const INTERNAL_ERROR: i32 = 109;
    pub const AUTH_FAILED: i32 = 110;
}

// ─── Notification Codes ───

pub mod notif_code {
    /// Resource status changed.
    pub const RESOURCE_CHANGED: i32 = 1001;
    /// Session invalidated.
    pub const SESSION_INVALID: i32 = 1002;
    /// File error.
    pub const FILE_ERROR: i32 = -2001;
}

/// Max JSON byte length for control frames (per CEA2.x §05).
pub const MAX_JSON_BYTES: usize = 4096;

/// Max QR payload size in UTF-8 bytes (per CEA2.x §02).
pub const MAX_QR_BYTES: usize = 2048;
