//! Profile module — vehicle templates and instances (decision 08 D8.9).
//!
//! Templates (`profiles/templates/*.toml`) are built-in vehicle type definitions
//! compiled into the binary via `include_str!`.
//!
//! Instances (`profiles/instances/*.json`) are user-created at runtime,
//! stored on disk in the project's `profiles/instances/` directory.

use std::fs;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

// ── Template ──

/// Vehicle type definition — describes a car model's capabilities and assets.
/// Built-in, loaded from TOML at compile time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VehicleTemplate {
    /// Machine-readable template name, e.g. "aura-t6".
    pub name: String,
    /// Human-readable name, e.g. "AURA T6".
    pub display_name: String,
    /// GLB model path served by the frontend, e.g. "/models/aura-t6.glb".
    pub model_path: String,
    /// Door/window position IDs, e.g. ["fl", "fr", "rl", "rr"].
    pub positions: Vec<String>,
    /// Whether this vehicle has a sunroof.
    pub has_sunroof: bool,
    /// Whether this vehicle has a power tailgate.
    pub has_tailgate: bool,
    /// Whether this vehicle has a hood (front trunk).
    pub has_hood: bool,
}

// Built-in templates compiled into the binary.
const AURA_T6_TOML: &str = include_str!("../../profiles/templates/aura-t6.toml");

/// List all built-in templates.
pub fn list_templates() -> Vec<VehicleTemplate> {
    let mut templates = Vec::new();
    if let Ok(t) = toml::from_str::<VehicleTemplate>(AURA_T6_TOML) {
        templates.push(t);
    }
    templates
}

/// Find a template by name.
pub fn find_template(name: &str) -> Option<VehicleTemplate> {
    list_templates().into_iter().find(|t| t.name == name)
}

// ── Instance ──

/// A specific vehicle instance created by the user (decision 08 D8.9/D8.10).
/// References a template and fills in identity fields like VIN.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VehicleInstance {
    /// Unique instance ID (generated, e.g. "aura-t6-1730200000").
    pub id: String,
    /// Template name this instance is based on, e.g. "aura-t6".
    pub template: String,
    /// User-given display name, e.g. "我的 AURA".
    pub display_name: String,
    /// Vehicle Identification Number (user-provided).
    pub vin: String,
    /// ISO 8601 creation timestamp.
    pub created_at: String,
}

/// Resolve the instances directory: `<project_root>/profiles/instances/`.
/// Uses the same heuristic as log_path() in lib.rs.
fn instances_dir() -> PathBuf {
    let base = std::env::current_dir()
        .ok()
        .and_then(|cwd| {
            let parent = cwd.parent().map(|p| p.to_path_buf());
            parent.filter(|p| p.join("src").exists() || p.join("profiles").exists())
        })
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());
    base.join("profiles").join("instances")
}

/// Resolve the last-instance file path.
fn last_instance_file() -> PathBuf {
    instances_dir().join(".last-instance")
}

/// Ensure the instances directory exists.
fn ensure_instances_dir() -> Result<(), String> {
    let dir = instances_dir();
    if !dir.exists() {
        fs::create_dir_all(&dir).map_err(|e| format!("无法创建实例目录: {e}"))?;
    }
    Ok(())
}

/// List all saved instances from the instances directory.
pub fn list_instances() -> Vec<VehicleInstance> {
    let dir = instances_dir();
    let mut instances = Vec::new();

    let entries = match fs::read_dir(&dir) {
        Ok(e) => e,
        Err(_) => return instances, // Directory doesn't exist yet — empty list.
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().is_none_or(|ext| ext != "json") {
            continue;
        }
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(instance) = serde_json::from_str::<VehicleInstance>(&content) {
                instances.push(instance);
            }
        }
    }

    // Sort by created_at for stable ordering.
    instances.sort_by(|a, b| a.created_at.cmp(&b.created_at));
    instances
}

/// Create a new instance and save it to disk.
pub fn create_instance(
    template_name: &str,
    display_name: &str,
    vin: &str,
) -> Result<VehicleInstance, String> {
    // Validate template exists.
    let template = find_template(template_name)
        .ok_or_else(|| format!("模板 '{template_name}' 不存在"))?;

    ensure_instances_dir()?;

    let id = format!("{}-{}", template.name, chrono::Local::now().format("%Y%m%d%H%M%S"));
    let instance = VehicleInstance {
        id: id.clone(),
        template: template.name,
        display_name: display_name.to_string(),
        vin: vin.to_string(),
        created_at: chrono::Local::now().to_rfc3339(),
    };

    let path = instances_dir().join(format!("{id}.json"));
    let json = serde_json::to_string_pretty(&instance)
        .map_err(|e| format!("序列化实例失败: {e}"))?;
    fs::write(&path, json).map_err(|e| format!("写入实例文件失败: {e}"))?;

    Ok(instance)
}

/// Delete an instance by ID.
pub fn delete_instance(id: &str) -> Result<(), String> {
    let path = instances_dir().join(format!("{id}.json"));
    if !path.exists() {
        return Err(format!("实例 '{id}' 不存在"));
    }
    fs::remove_file(&path).map_err(|e| format!("删除实例失败: {e}"))?;

    // Clear last-instance if it was this one.
    if let Ok(last) = fs::read_to_string(last_instance_file()) {
        if last.trim() == id {
            let _ = fs::remove_file(last_instance_file());
        }
    }
    Ok(())
}

/// Get the last selected instance ID (for app startup, D8.15).
pub fn get_last_instance_id() -> Option<String> {
    fs::read_to_string(last_instance_file())
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

/// Save the last selected instance ID.
pub fn set_last_instance_id(id: &str) -> Result<(), String> {
    ensure_instances_dir()?;
    fs::write(last_instance_file(), id)
        .map_err(|e| format!("写入上次实例记录失败: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn list_templates_includes_aura_t6() {
        let templates = list_templates();
        assert!(templates.iter().any(|t| t.name == "aura-t6"));
    }

    #[test]
    fn aura_t6_template_has_correct_fields() {
        let t = find_template("aura-t6").expect("aura-t6 template must exist");
        assert_eq!(t.display_name, "AURA T6");
        assert_eq!(t.model_path, "/models/aura-t6.glb");
        assert_eq!(t.positions, vec!["fl", "fr", "rl", "rr"]);
        assert!(t.has_sunroof);
        assert!(t.has_tailgate);
        assert!(t.has_hood);
    }

    #[test]
    fn find_template_returns_none_for_unknown() {
        assert!(find_template("nonexistent").is_none());
    }

    #[test]
    fn create_and_list_instance() {
        // Create instance
        let instance = create_instance("aura-t6", "测试车辆", "LSVAA000000000001")
            .expect("create should succeed");
        assert_eq!(instance.template, "aura-t6");
        assert_eq!(instance.display_name, "测试车辆");
        assert_eq!(instance.vin, "LSVAA000000000001");
        assert!(!instance.id.is_empty());

        // List should include it
        let list = list_instances();
        assert!(list.iter().any(|i| i.id == instance.id));

        // Last instance
        set_last_instance_id(&instance.id).expect("set last should succeed");
        assert_eq!(get_last_instance_id(), Some(instance.id.clone()));

        // Delete
        delete_instance(&instance.id).expect("delete should succeed");
        let list_after = list_instances();
        assert!(!list_after.iter().any(|i| i.id == instance.id));

        // Last instance cleared
        assert!(get_last_instance_id().is_none());
    }

    #[test]
    fn create_instance_rejects_unknown_template() {
        let result = create_instance("nonexistent", "test", "VIN");
        assert!(result.is_err());
    }

    #[test]
    fn instance_serializes_to_json() {
        let instance = VehicleInstance {
            id: "test-001".to_string(),
            template: "aura-t6".to_string(),
            display_name: "Test".to_string(),
            vin: "VIN001".to_string(),
            created_at: "2026-01-01T00:00:00+08:00".to_string(),
        };
        let json = serde_json::to_string(&instance).unwrap();
        let parsed: VehicleInstance = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.id, "test-001");
        assert_eq!(parsed.template, "aura-t6");
    }
}
