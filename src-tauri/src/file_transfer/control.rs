//! Control channel — TLS connection handler for CEA2.x protocol.
//!
/// Reads and writes 4B-length-prefixed JSON frames, dispatches Action
/// requests to the session manager, and sends responses back.

use std::sync::Arc;

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio_rustls::server::TlsStream;
use tokio::sync::Mutex;

use super::config::FtConfig;
use super::message::*;
use super::session::SessionManager;

/// Maximum frame length for control JSON (4 bytes header + 4096 body).
const MAX_FRAME_LEN: usize = MAX_JSON_BYTES;

/// Run the control channel loop on an accepted TLS connection.
pub async fn handle_control_connection(
    stream: TlsStream<TcpStream>,
    config: Arc<FtConfig>,
    sessions: Arc<Mutex<SessionManager>>,
    log: impl Fn(&str) + Send + Sync + 'static,
) {
    let log = Arc::new(log);
    let log_clone = log.clone();
    log_clone("FT: control connection accepted");

    let (mut reader, mut writer) = tokio::io::split(stream);

    loop {
        // Read 4-byte length header (uint32 BE).
        let mut header = [0u8; 4];
        match reader.read_exact(&mut header).await {
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                log_clone("FT: control connection closed by peer (EOF)");
                break;
            }
            Err(e) => {
                log_clone(&format!("FT: control read error: {e}"));
                break;
            }
        }

        let length = u32::from_be_bytes(header) as usize;
        if length == 0 || length > MAX_FRAME_LEN {
            log_clone(&format!("FT: invalid frame length {length}, closing"));
            break;
        }

        // Read JSON body.
        let mut body = vec![0u8; length];
        if let Err(e) = reader.read_exact(&mut body).await {
            log_clone(&format!("FT: control body read error: {e}"));
            break;
        }

        let json_str = match std::str::from_utf8(&body) {
            Ok(s) => s,
            Err(e) => {
                log_clone(&format!("FT: invalid UTF-8 in control frame: {e}"));
                break;
            }
        };

        // Parse envelope.
        let envelope: Envelope = match serde_json::from_str(json_str) {
            Ok(e) => e,
            Err(e) => {
                log_clone(&format!("FT: JSON parse error: {e}"));
                // Send error response (best effort, no RequestID available).
                continue;
            }
        };

        log_clone(&format!("FT: received Action={:?}", envelope.action));

        // Dispatch based on Action.
        let response = match envelope.action {
            Some(Action::Campability) => handle_campability(&envelope, &sessions, &config, &log_clone).await,
            Some(Action::List) => handle_list(&envelope, &sessions, &log_clone).await,
            Some(Action::Stop) => handle_stop(&envelope, &sessions, &log_clone).await,
            // M3.2: download, pause, resume, cancel
            Some(Action::Download) => {
                log_clone("FT: download not yet implemented (M3.2)");
                make_error_response(&envelope, status_code::INVALID_STATE, "download not implemented")
            }
            Some(Action::Pause) => {
                make_error_response(&envelope, status_code::INVALID_STATE, "pause not implemented")
            }
            Some(Action::Resume) => {
                make_error_response(&envelope, status_code::INVALID_STATE, "resume not implemented")
            }
            Some(Action::Cancel) => {
                make_error_response(&envelope, status_code::INVALID_STATE, "cancel not implemented")
            }
            None => {
                log_clone("FT: no Action in envelope");
                make_error_response(&envelope, status_code::INVALID_ARGUMENT, "missing Action")
            }
        };

        // Send response.
        let response_json = match serde_json::to_string(&response) {
            Ok(s) => s,
            Err(e) => {
                log_clone(&format!("FT: response serialization error: {e}"));
                break;
            }
        };

        let resp_bytes = response_json.as_bytes();
        if resp_bytes.len() > MAX_FRAME_LEN {
            log_clone(&format!("FT: response too large ({} bytes)", resp_bytes.len()));
            break;
        }

        let mut frame = Vec::with_capacity(4 + resp_bytes.len());
        frame.extend_from_slice(&(resp_bytes.len() as u32).to_be_bytes());
        frame.extend_from_slice(resp_bytes);

        if let Err(e) = writer.write_all(&frame).await {
            log_clone(&format!("FT: write error: {e}"));
            break;
        }
    }

    log_clone("FT: control connection handler exited");
}

/// Handle campability action.
async fn handle_campability(
    envelope: &Envelope,
    sessions: &Arc<Mutex<SessionManager>>,
    config: &Arc<FtConfig>,
    log: &Arc<impl Fn(&str)>,
) -> Envelope {
    // Parse parameter.
    let param: CampabilityParam = match envelope.parameter.as_ref()
        .and_then(|p| serde_json::from_value(p.clone()).ok())
    {
        Some(p) => p,
        None => {
            return make_error_response(envelope, status_code::INVALID_ARGUMENT, "invalid campability parameter");
        }
    };

    let now_secs = chrono::Utc::now().timestamp();
    let mut mgr = sessions.lock().await;
    match mgr.campability(&param.share_id, &param.share_secret, now_secs).await {
        Ok(session_id) => {
            log(&format!("FT: campability success, session_id={session_id}"));

            // Get share files (available for future use, currently unused in campability response).
            let share = mgr.get_share(&param.share_id);
            let _files = share
                .and_then(|s| s.try_lock().ok().map(|s| s.files.clone()))
                .unwrap_or_default();

            let response_param = CampabilityResponse {
                share_id: param.share_id.clone(),
                session_id: session_id.clone(),
                limits: Limits {
                    max_parallel_files: config.max_parallel,
                    data_idle_timeout_ms: 30000,
                    session_idle_timeout_ms: 120000,
                },
            };

            make_success_response(envelope, serde_json::to_value(&response_param).unwrap_or_default())
        }
        Err(code) => {
            log(&format!("FT: campability failed, code={code}"));
            make_error_response(envelope, code, &format!("campability error {code}"))
        }
    }
}

/// Handle list action.
async fn handle_list(
    envelope: &Envelope,
    sessions: &Arc<Mutex<SessionManager>>,
    log: &Arc<impl Fn(&str)>,
) -> Envelope {
    let param: ListParam = match envelope.parameter.as_ref()
        .and_then(|p| serde_json::from_value(p.clone()).ok())
    {
        Some(p) => p,
        None => {
            return make_error_response(envelope, status_code::INVALID_ARGUMENT, "invalid list parameter");
        }
    };

    let mgr = sessions.lock().await;
    let session_arc = match mgr.get_session(&param.session_id) {
        Some(s) => s,
        None => {
            return make_error_response(envelope, status_code::SHARE_EXPIRED, "session not found");
        }
    };

    let session = session_arc.lock().await;
    let share_arc = match mgr.get_share(&session.share_id) {
        Some(s) => s,
        None => {
            return make_error_response(envelope, status_code::SHARE_EXPIRED, "share not found");
        }
    };

    let share = share_arc.lock().await;
    let files: Vec<WireFile> = share.files.iter().map(|f| f.to_wire()).collect();

    log(&format!("FT: list returning {} files for session {}", files.len(), param.session_id));

    let response_param = ListResponse {
        session_id: param.session_id.clone(),
        files,
    };

    make_success_response(envelope, serde_json::to_value(&response_param).unwrap_or_default())
}

/// Handle stop action (end share).
async fn handle_stop(
    envelope: &Envelope,
    sessions: &Arc<Mutex<SessionManager>>,
    log: &Arc<impl Fn(&str)>,
) -> Envelope {
    let param: StopParam = match envelope.parameter.as_ref()
        .and_then(|p| serde_json::from_value(p.clone()).ok())
    {
        Some(p) => p,
        None => {
            return make_error_response(envelope, status_code::INVALID_ARGUMENT, "invalid stop parameter");
        }
    };

    log(&format!("FT: stop sessionId={} scope={} reason={}", param.session_id, param.scope, param.reason));

    let mut mgr = sessions.lock().await;
    match mgr.end_share(&param.session_id).await {
        Ok(()) => {
            log("FT: share ended successfully");
            make_success_response(envelope, serde_json::json!({
                "sessionId": param.session_id,
                "scope": param.scope,
                "reason": param.reason
            }))
        }
        Err(code) => {
            log(&format!("FT: stop failed, code={code}"));
            make_error_response(envelope, code, "stop failed")
        }
    }
}

/// Build a success response envelope.
fn make_success_response(request: &Envelope, parameter: serde_json::Value) -> Envelope {
    Envelope {
        ver: "2.0".to_string(),
        msg_type: MessageType::Response,
        id: uuid::Uuid::new_v4().to_string(),
        from: From {
            oem: "svw".to_string(),
            device: "vehicle".to_string(),
            app: "com.vehicle.simulator.share".to_string(),
            os: std::env::consts::OS.to_string(),
            port: None,
            ipv4: None,
            ipv6: None,
        },
        direction: Direction::V2p,
        security: serde_json::json!({}),
        priority: request.priority,
        timestamp: chrono::Utc::now().timestamp_millis(),
        action: None,
        parameter: Some(parameter),
        request_id: Some(request.id.clone()),
        status_code: Some(status_code::OK),
        code: None,
        info: None,
        expires: None,
    }
}

/// Build an error response envelope.
fn make_error_response(request: &Envelope, status_code: i32, message: &str) -> Envelope {
    let parameter = ErrorParam {
        message: message.to_string(),
        retryable: !matches!(status_code, status_code::AUTH_FAILED | status_code::SHARE_EXPIRED),
    };

    Envelope {
        ver: "2.0".to_string(),
        msg_type: MessageType::Response,
        id: uuid::Uuid::new_v4().to_string(),
        from: From {
            oem: "svw".to_string(),
            device: "vehicle".to_string(),
            app: "com.vehicle.simulator.share".to_string(),
            os: std::env::consts::OS.to_string(),
            port: None,
            ipv4: None,
            ipv6: None,
        },
        direction: Direction::V2p,
        security: serde_json::json!({}),
        priority: request.priority,
        timestamp: chrono::Utc::now().timestamp_millis(),
        action: None,
        parameter: Some(serde_json::to_value(&parameter).unwrap_or_default()),
        request_id: Some(request.id.clone()),
        status_code: Some(status_code),
        code: None,
        info: None,
        expires: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_make_success_response() {
        let req = Envelope {
            ver: "2.0".to_string(),
            msg_type: MessageType::Request,
            id: "req-123".to_string(),
            from: From {
                oem: "svw".to_string(),
                device: "phone".to_string(),
                app: "com.test".to_string(),
                os: "android".to_string(),
                port: Some(12345),
                ipv4: Some("192.0.2.20".to_string()),
                ipv6: None,
            },
            direction: Direction::P2v,
            security: serde_json::json!({}),
            priority: 2,
            timestamp: 1792569603000,
            action: Some(Action::List),
            parameter: Some(serde_json::json!({"sessionId": "test"})),
            request_id: None,
            status_code: None,
            code: None,
            info: None,
            expires: Some(5000),
        };

        let resp = make_success_response(&req, serde_json::json!({"ok": true}));
        assert_eq!(resp.msg_type, MessageType::Response);
        assert_eq!(resp.request_id, Some("req-123".to_string()));
        assert_eq!(resp.status_code, Some(0));
    }

    #[test]
    fn test_make_error_response() {
        let req = Envelope {
            ver: "2.0".to_string(),
            msg_type: MessageType::Request,
            id: "req-456".to_string(),
            from: From {
                oem: "svw".to_string(),
                device: "phone".to_string(),
                app: "com.test".to_string(),
                os: "android".to_string(),
                port: None,
                ipv4: None,
                ipv6: None,
            },
            direction: Direction::P2v,
            security: serde_json::json!({}),
            priority: 2,
            timestamp: 0,
            action: Some(Action::Campability),
            parameter: None,
            request_id: None,
            status_code: None,
            code: None,
            info: None,
            expires: None,
        };

        let resp = make_error_response(&req, status_code::AUTH_FAILED, "bad secret");
        assert_eq!(resp.status_code, Some(110));
        assert_eq!(resp.request_id, Some("req-456".to_string()));
    }
}
