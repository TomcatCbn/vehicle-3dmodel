use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoorState {
    pub open: bool,
    pub angle: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowState {
    pub target: f32,
    pub open: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HoodState {
    pub open: bool,
    pub angle: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SunroofState {
    pub target: f32,
    pub position: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TailgateState {
    pub target: f32,
    pub position: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HeadlightMode {
    Off,
    Low,
    High,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AmbientColor {
    Off,
    Warm,
    Ice,
    Purple,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LightingState {
    pub headlights: HeadlightMode,
    pub tail_lights: bool,
    pub ambient: AmbientColor,
}

impl Default for LightingState {
    fn default() -> Self {
        Self {
            headlights: HeadlightMode::Low,
            tail_lights: true,
            ambient: AmbientColor::Off,
        }
    }
}

/// VehicleState — three-layer state per decision 5/7.
/// Logic fields (locked/doors.*.open/hood.open/ac/plugged/charging/lighting)
/// are changed by commands. Position fields (doors.*.angle/windows.*.open/
/// hood.angle/sunroof.position/tailgate.position/battery) are advanced by tick().
/// Targets (sunroof.target/tailgate.target/windows.*.target) are logic-driven.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VehicleState {
    pub locked: bool,
    pub doors: HashMap<String, DoorState>,
    pub windows: HashMap<String, WindowState>,
    pub hood: HoodState,
    pub sunroof: SunroofState,
    pub tailgate: TailgateState,
    pub ac: bool,
    pub temperature: i8,
    pub plugged: bool,
    pub charging: bool,
    pub battery: f32,
    pub lighting: LightingState,
}

/// AURA T6 door/window position ids (per profile, decision 7).
pub const AURA_T6_POSITIONS: &[&str] = &["fl", "fr", "rl", "rr"];
