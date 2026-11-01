//! File management — scan a directory, produce metadata for QR and list responses.

use std::path::Path;

use super::message::{FileKind, FileStatus, WireFile};

/// A discoverable shareable file on disk.
#[derive(Debug, Clone)]
pub struct FileInfo {
    /// Stable id assigned by index: "f-0001" .. "f-0009".
    pub file_id: String,
    /// Absolute path on the vehicle side.
    pub path: std::path::PathBuf,
    /// Display name (file name without directory).
    pub name: String,
    /// Size in bytes.
    pub size: u64,
    /// Image or video.
    pub kind: FileKind,
}

impl FileInfo {
    /// Convert to WireFile for list response.
    pub fn to_wire(&self) -> WireFile {
        WireFile {
            file_id: self.file_id.clone(),
            file_path: Some(self.path.to_string_lossy().to_string()),
            name: self.name.clone(),
            size: Some(self.size),
            kind: self.kind,
            status: FileStatus::Available,
        }
    }

    /// Convert to QR file entry (FileName/Path/Size).
    pub fn to_qr_entry(&self) -> QrFileEntry {
        QrFileEntry {
            file_name: self.name.clone(),
            path: self.path.to_string_lossy().to_string(),
            size: self.size,
        }
    }
}

/// QR Files[] entry.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct QrFileEntry {
    #[serde(rename = "FileName")]
    pub file_name: String,
    #[serde(rename = "Path")]
    pub path: String,
    #[serde(rename = "Size")]
    pub size: u64,
}

/// Determine file kind from a lowercase extension.
/// Returns None for unsupported (non-media) extensions.
pub fn file_kind_from_ext(ext: &str) -> Option<FileKind> {
    match ext {
        "jpg" | "jpeg" | "png" | "gif" | "bmp" | "webp" => Some(FileKind::Image),
        "mp4" | "mov" | "avi" | "mkv" | "webm" => Some(FileKind::Video),
        _ => None,
    }
}

/// Create a FileInfo from an arbitrary path, assigning the given 1-based index.
/// Returns None if the path is not a file or not a supported media type.
pub fn file_info_from_path(path: &Path, idx: u32) -> Option<FileInfo> {
    if !path.is_file() {
        return None;
    }
    let name = path.file_name()?.to_string_lossy().to_string();
    let ext = path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();
    let kind = file_kind_from_ext(&ext)?;
    let size = std::fs::metadata(path).map(|m| m.len()).unwrap_or(0);
    Some(FileInfo {
        file_id: format!("f-{idx:04}"),
        path: path.to_path_buf(),
        name,
        size,
        kind,
    })
}

/// Reassign file_ids sequentially: f-0001 .. f-000N.
pub fn reindex_files(files: &mut [FileInfo]) {
    for (i, f) in files.iter_mut().enumerate() {
        f.file_id = format!("f-{:04}", i + 1);
    }
}

/// Scan a directory for shareable files (images and videos).
/// Returns at most 9 files (per CEA2.x: 1-9 files per share).
pub fn scan_dir(dir: &Path) -> Vec<FileInfo> {
    let mut files = Vec::new();

    let read = match std::fs::read_dir(dir) {
        Ok(rd) => rd,
        Err(_) => return files,
    };

    for entry in read.flatten() {
        if files.len() >= 9 {
            break;
        }
        let path = entry.path();
        let idx = (files.len() + 1) as u32;
        if let Some(info) = file_info_from_path(&path, idx) {
            files.push(info);
        }
    }

    files
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scan_empty_dir() {
        let tmp = std::env::temp_dir().join("ft_test_empty");
        let _ = std::fs::create_dir_all(&tmp);
        // Ensure directory exists but is empty (or at least has no media).
        let files = scan_dir(&tmp);
        // May find files if temp is shared; just check it doesn't panic.
        assert!(files.len() <= 9);
    }

    #[test]
    fn test_scan_with_files() {
        let tmp = std::env::temp_dir().join("ft_test_media");
        let _ = std::fs::create_dir_all(&tmp);
        let _ = std::fs::write(tmp.join("test.jpg"), b"fake jpg");
        let _ = std::fs::write(tmp.join("test.mp4"), b"fake mp4");
        let _ = std::fs::write(tmp.join("test.txt"), b"not media");

        let files = scan_dir(&tmp);
        assert_eq!(files.len(), 2);
        assert!(files.iter().any(|f| f.name == "test.jpg"));
        assert!(files.iter().any(|f| f.name == "test.mp4"));

        // Cleanup
        let _ = std::fs::remove_file(tmp.join("test.jpg"));
        let _ = std::fs::remove_file(tmp.join("test.mp4"));
        let _ = std::fs::remove_file(tmp.join("test.txt"));
    }

    #[test]
    fn test_file_id_format() {
        let info = FileInfo {
            file_id: "f-0001".to_string(),
            path: std::path::PathBuf::from("/share/image.jpg"),
            name: "image.jpg".to_string(),
            size: 65536,
            kind: FileKind::Image,
        };
        let wire = info.to_wire();
        assert_eq!(wire.file_id, "f-0001");
        assert_eq!(wire.size, Some(65536));
    }

    #[test]
    fn test_file_kind_from_ext() {
        assert_eq!(file_kind_from_ext("jpg"), Some(FileKind::Image));
        assert_eq!(file_kind_from_ext("jpeg"), Some(FileKind::Image));
        assert_eq!(file_kind_from_ext("png"), Some(FileKind::Image));
        assert_eq!(file_kind_from_ext("mp4"), Some(FileKind::Video));
        assert_eq!(file_kind_from_ext("mov"), Some(FileKind::Video));
        assert_eq!(file_kind_from_ext("txt"), None);
        assert_eq!(file_kind_from_ext(""), None);
    }

    #[test]
    fn test_file_info_from_path() {
        let tmp = std::env::temp_dir().join("ft_test_from_path");
        let _ = std::fs::create_dir_all(&tmp);
        let img_path = tmp.join("photo.jpg");
        let _ = std::fs::write(&img_path, b"fake jpg content");
        let txt_path = tmp.join("notes.txt");
        let _ = std::fs::write(&txt_path, b"not media");

        let info = file_info_from_path(&img_path, 1);
        assert!(info.is_some());
        let info = info.unwrap();
        assert_eq!(info.file_id, "f-0001");
        assert_eq!(info.name, "photo.jpg");
        assert_eq!(info.kind, FileKind::Image);
        assert_eq!(info.size, 16);

        // Non-media file returns None.
        assert!(file_info_from_path(&txt_path, 2).is_none());

        // Non-existent file returns None.
        assert!(file_info_from_path(&tmp.join("missing.jpg"), 3).is_none());

        // Cleanup
        let _ = std::fs::remove_file(&img_path);
        let _ = std::fs::remove_file(&txt_path);
    }

    #[test]
    fn test_reindex_files() {
        let mut files = vec![
            FileInfo {
                file_id: "f-0001".to_string(),
                path: std::path::PathBuf::from("/a.jpg"),
                name: "a.jpg".to_string(),
                size: 100,
                kind: FileKind::Image,
            },
            FileInfo {
                file_id: "f-0003".to_string(),
                path: std::path::PathBuf::from("/b.mp4"),
                name: "b.mp4".to_string(),
                size: 200,
                kind: FileKind::Video,
            },
        ];
        reindex_files(&mut files);
        assert_eq!(files[0].file_id, "f-0001");
        assert_eq!(files[1].file_id, "f-0002");
    }
}
