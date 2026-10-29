use serde::{Deserialize, Serialize};

use crate::signal::state::{AmbientColor, HeadlightMode, PowerState};

/// VehicleCommand — unified command enum (decision 5 D5.3 + decision 7).
/// Three sources (local UI, MQTT downstream, BLE RKE) all map to this enum,
/// converging at SignalModel::apply_command.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum VehicleCommand {
    ToggleLock,
    /// id = None toggles all doors; Some("fl") toggles a single door.
    ToggleDoor {
        #[serde(default)]
        id: Option<String>,
    },
    /// id = None sets all windows; Some("fl") sets a single window.
    SetWindow {
        #[serde(default)]
        id: Option<String>,
        target: f32,
    },
    SetSunroof { target: f32 },
    Tailgate { action: TailgateAction },
    ToggleHood,
    ToggleAc,
    SetTemperature { value: i8 },
    TogglePlug,
    ToggleCharging,
    SetHeadlight { mode: HeadlightMode },
    ToggleTailLight,
    SetAmbient { color: AmbientColor },
    /// on = true requests start (interlock checked); on = false is stop (no check).
    /// Driving animation itself stays frontend-side (decision 5 D5.5).
    ToggleDriving { on: bool },
    /// Change power state (decision 8 D8.2). Shutdown checks driving interlock.
    SetPower { state: PowerState },
    /// Reset to default state (all closed, locked, battery 68%).
    Reset,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TailgateAction {
    Open,
    Close,
    Stop,
}
