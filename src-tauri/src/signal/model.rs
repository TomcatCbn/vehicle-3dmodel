//! SignalModel — runtime state machine (decisions 3 + 5 + 7).
//! Holds three-layer VehicleState, ticks actual positions toward targets,
//! and applies commands through interlock checks.

use std::collections::HashMap;

use crate::signal::command::{TailgateAction, VehicleCommand};
use crate::signal::interlock;
use crate::signal::state::{
    DoorState, HoodState, LightingState, PowerState, SunroofState, TailgateState,
    VehicleState, WindowState, AURA_T6_POSITIONS,
};

fn clamp(v: f32, min: f32, max: f32) -> f32 {
    v.max(min).min(max)
}

pub struct SignalModel {
    state: VehicleState,
}

impl SignalModel {
    /// Instantiate from a profile's door/window position ids.
    /// For AURA T6: ["fl", "fr", "rl", "rr"].
    pub fn new(positions: &[&str]) -> Self {
        let mut doors = HashMap::new();
        let mut windows = HashMap::new();
        for &id in positions {
            doors.insert(id.to_string(), DoorState { open: false, angle: 0.0 });
            windows.insert(id.to_string(), WindowState { target: 0.0, open: 0.0 });
        }
        Self {
            state: VehicleState {
                locked: true,
                doors,
                windows,
                hood: HoodState { open: false, angle: 0.0 },
                sunroof: SunroofState { target: 0.0, position: 0.0 },
                tailgate: TailgateState { target: 0.0, position: 0.0 },
                ac: false,
                temperature: 22,
                plugged: false,
                charging: false,
                battery: 68.0,
                lighting: LightingState::default(),
                power_state: PowerState::Standby,
                driving: false,
            },
        }
    }

    /// Default AURA T6 model.
    pub fn aura_t6() -> Self {
        Self::new(AURA_T6_POSITIONS)
    }

    /// Advance actual positions toward targets. Rust port of stepVehicle
    /// (src/state.js L7-22). Called at ~30-50Hz by the backend tick loop.
    /// Skipped entirely when power_state is Sleep (decision 8 D8.3).
    pub fn tick(&mut self, dt: f32) {
        if self.state.power_state == PowerState::Sleep {
            return;
        }
        let dt = if dt.is_finite() && dt > 0.0 { dt } else { 0.0 };

        // Windows: lerp open toward target (speed 0.5/s)
        for win in self.state.windows.values_mut() {
            let target = clamp(win.target, 0.0, 1.0);
            let delta = target - win.open;
            win.open = clamp(
                win.open + delta.signum() * delta.abs().min(dt * 0.5),
                0.0,
                1.0,
            );
        }

        // Doors: lerp angle toward open(1)/closed(0) (speed 1.5/s)
        for door in self.state.doors.values_mut() {
            let target = if door.open { 1.0 } else { 0.0 };
            let delta = target - door.angle;
            door.angle += delta.signum() * delta.abs().min(dt * 1.5);
            door.angle = clamp(door.angle, 0.0, 1.0);
        }

        // Hood (speed 1.25/s)
        let hood_target = if self.state.hood.open { 1.0 } else { 0.0 };
        let hood_delta = hood_target - self.state.hood.angle;
        self.state.hood.angle += hood_delta.signum() * hood_delta.abs().min(dt * 1.25);
        self.state.hood.angle = clamp(self.state.hood.angle, 0.0, 1.0);

        // Sunroof (speed 0.38/s)
        let sr_target = clamp(self.state.sunroof.target, 0.0, 1.0);
        let sr_delta = sr_target - self.state.sunroof.position;
        self.state.sunroof.position = clamp(
            self.state.sunroof.position + sr_delta.signum() * sr_delta.abs().min(dt * 0.38),
            0.0,
            1.0,
        );

        // Tailgate (speed 0.34/s)
        let tg_target = clamp(self.state.tailgate.target, 0.0, 1.0);
        let tg_delta = tg_target - self.state.tailgate.position;
        self.state.tailgate.position = clamp(
            self.state.tailgate.position + tg_delta.signum() * tg_delta.abs().min(dt * 0.34),
            0.0,
            1.0,
        );

        // Charging / battery
        if !self.state.plugged {
            self.state.charging = false;
        }
        if self.state.charging {
            self.state.battery = clamp(self.state.battery + dt * 0.08, 0.0, 100.0);
        }
        if self.state.battery >= 100.0 {
            self.state.charging = false;
        }
    }

    /// Apply a command (from local UI / MQTT / BLE). Runs interlock checks,
    /// mutates logic state / targets, returns Ok or an error message.
    /// Power state gating per decision 8 D8.12:
    ///   - Sleep: all commands rejected except SetPower and Reset
    ///   - Standby: high-voltage commands rejected (AC, charging, driving start)
    ///   - Ready: all commands allowed
    pub fn apply_command(&mut self, cmd: &VehicleCommand) -> Result<(), &'static str> {
        // Power state gating
        match self.state.power_state {
            PowerState::Sleep => {
                if !matches!(cmd, VehicleCommand::SetPower { .. } | VehicleCommand::Reset) {
                    return Err("车辆处于休眠状态，请先上电");
                }
            }
            PowerState::Standby => {
                if interlock::is_high_voltage_command(cmd) {
                    return Err("高压未闭合，请先上电至 Ready");
                }
            }
            PowerState::Ready => {}
        }

        match cmd {
            VehicleCommand::ToggleLock => {
                // Locking requires all doors closed; unlocking is always allowed.
                if !self.state.locked {
                    interlock::can_lock(&self.state)?;
                }
                self.state.locked = !self.state.locked;
            }
            VehicleCommand::ToggleDoor { id } => {
                interlock::can_open_door(&self.state)?;
                match id {
                    Some(door_id) => {
                        if let Some(door) = self.state.doors.get_mut(door_id) {
                            door.open = !door.open;
                        }
                    }
                    None => {
                        // Toggle all doors together (current UI behavior).
                        let any_open = self.state.doors.values().any(|d| d.open);
                        let next = !any_open;
                        for door in self.state.doors.values_mut() {
                            door.open = next;
                        }
                    }
                }
            }
            VehicleCommand::SetWindow { id, target } => {
                let t = clamp(*target, 0.0, 1.0);
                match id {
                    Some(win_id) => {
                        if let Some(win) = self.state.windows.get_mut(win_id) {
                            win.target = t;
                        }
                    }
                    None => {
                        for win in self.state.windows.values_mut() {
                            win.target = t;
                        }
                    }
                }
            }
            VehicleCommand::SetSunroof { target } => {
                self.state.sunroof.target = clamp(*target, 0.0, 1.0);
            }
            VehicleCommand::Tailgate { action } => match action {
                TailgateAction::Open => self.state.tailgate.target = 1.0,
                TailgateAction::Close => self.state.tailgate.target = 0.0,
                TailgateAction::Stop => {
                    self.state.tailgate.target = self.state.tailgate.position;
                }
            },
            VehicleCommand::ToggleHood => {
                self.state.hood.open = !self.state.hood.open;
            }
            VehicleCommand::ToggleAc => {
                self.state.ac = !self.state.ac;
            }
            VehicleCommand::SetTemperature { value } => {
                self.state.temperature = (*value).max(16).min(30);
            }
            VehicleCommand::TogglePlug => {
                self.state.plugged = !self.state.plugged;
                if !self.state.plugged {
                    self.state.charging = false;
                }
            }
            VehicleCommand::ToggleCharging => {
                let on = !self.state.charging;
                interlock::can_charge(&self.state, on)?;
                self.state.charging = on;
            }
            VehicleCommand::SetHeadlight { mode } => {
                self.state.lighting.headlights = *mode;
            }
            VehicleCommand::ToggleTailLight => {
                self.state.lighting.tail_lights = !self.state.lighting.tail_lights;
            }
            VehicleCommand::SetAmbient { color } => {
                self.state.lighting.ambient = *color;
            }
            VehicleCommand::ToggleDriving { on } => {
                // Only starting requires interlock; stopping is always allowed.
                // Driving animation itself stays frontend-side (D5.5).
                if *on {
                    interlock::can_start_driving(&self.state)?;
                }
                self.state.driving = *on;
            }
            VehicleCommand::SetPower { state: target } => {
                // Shutdown interlock: cannot enter Sleep while driving (D8.6)
                if *target == PowerState::Sleep {
                    interlock::can_shutdown(&self.state)?;
                }
                self.state.power_state = *target;
            }
            VehicleCommand::Reset => {
                let positions: Vec<String> = self.state.doors.keys().cloned().collect();
                let pos_refs: Vec<&str> = positions.iter().map(|s| s.as_str()).collect();
                self.state = SignalModel::new(&pos_refs).into_state();
            }
        }
        Ok(())
    }

    /// Immutable snapshot for serialization to frontend / MQTT / BLE.
    pub fn snapshot(&self) -> &VehicleState {
        &self.state
    }

    /// Consume the model and return the inner state (used by Reset).
    pub fn into_state(self) -> VehicleState {
        self.state
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::signal::state::{HeadlightMode, AmbientColor};

    #[test]
    fn defaults_match_legacy_state_js() {
        let m = SignalModel::aura_t6();
        let s = m.snapshot();
        assert!(s.locked);
        assert_eq!(s.temperature, 22);
        assert!((s.battery - 68.0).abs() < 1e-6);
        assert_eq!(s.doors.len(), 4);
        assert_eq!(s.windows.len(), 4);
        assert!(s.doors["fl"].open == false);
        assert_eq!(s.lighting.headlights, HeadlightMode::Low);
        assert!(s.lighting.tail_lights);
        assert_eq!(s.lighting.ambient, AmbientColor::Off);
    }

    #[test]
    fn unlock_then_open_door_works() {
        let mut m = SignalModel::aura_t6();
        // Locked → cannot open door
        assert!(m.apply_command(&VehicleCommand::ToggleDoor { id: None }).is_err());
        // Unlock
        m.apply_command(&VehicleCommand::ToggleLock).unwrap();
        assert!(!m.snapshot().locked);
        // Now open doors
        m.apply_command(&VehicleCommand::ToggleDoor { id: None }).unwrap();
        assert!(m.snapshot().doors["fl"].open);
    }

    #[test]
    fn cannot_lock_with_door_open() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::ToggleLock).unwrap();
        m.apply_command(&VehicleCommand::ToggleDoor { id: None }).unwrap();
        // Cannot re-lock
        assert!(m.apply_command(&VehicleCommand::ToggleLock).is_err());
    }

    #[test]
    fn cannot_charge_without_plug() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Ready }).unwrap();
        assert!(m.apply_command(&VehicleCommand::ToggleCharging).is_err());
        m.apply_command(&VehicleCommand::TogglePlug).unwrap();
        m.apply_command(&VehicleCommand::ToggleCharging).unwrap();
        assert!(m.snapshot().charging);
    }

    #[test]
    fn cannot_start_driving_with_door_open() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::ToggleLock).unwrap();
        m.apply_command(&VehicleCommand::ToggleDoor { id: None }).unwrap();
        assert!(m.apply_command(&VehicleCommand::ToggleDriving { on: true }).is_err());
    }

    #[test]
    fn tick_advances_door_angle() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::ToggleLock).unwrap();
        m.apply_command(&VehicleCommand::ToggleDoor { id: None }).unwrap();
        // Before tick, angle is 0
        assert!((m.snapshot().doors["fl"].angle - 0.0).abs() < 1e-6);
        // After 1 second of ticks, angle should advance (speed 1.5 → ~1.0 but clamped)
        m.tick(1.0);
        assert!(m.snapshot().doors["fl"].angle > 0.5);
        // After enough time, reaches 1.0
        m.tick(1.0);
        assert!((m.snapshot().doors["fl"].angle - 1.0).abs() < 1e-3);
    }

    #[test]
    fn tick_advances_battery_when_charging() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Ready }).unwrap();
        m.apply_command(&VehicleCommand::TogglePlug).unwrap();
        m.apply_command(&VehicleCommand::ToggleCharging).unwrap();
        let b0 = m.snapshot().battery;
        m.tick(1.0);
        assert!(m.snapshot().battery > b0);
    }

    #[test]
    fn toggle_driving_stop_always_ok() {
        let mut m = SignalModel::aura_t6();
        // Stopping driving never needs interlock
        assert!(m.apply_command(&VehicleCommand::ToggleDriving { on: false }).is_ok());
    }

    #[test]
    fn serde_toggle_door_with_null_id() {
        let json = r#"{"type":"toggle_door","id":null}"#;
        let cmd: VehicleCommand = serde_json::from_str(json).unwrap();
        match cmd {
            VehicleCommand::ToggleDoor { id } => assert!(id.is_none()),
            other => panic!("expected ToggleDoor, got {other:?}"),
        }
    }

    #[test]
    fn serde_toggle_door_without_id() {
        let json = r#"{"type":"toggle_door"}"#;
        let cmd: VehicleCommand = serde_json::from_str(json).unwrap();
        match cmd {
            VehicleCommand::ToggleDoor { id } => assert!(id.is_none()),
            other => panic!("expected ToggleDoor, got {other:?}"),
        }
    }

    #[test]
    fn serde_toggle_hood() {
        let json = r#"{"type":"toggle_hood"}"#;
        let cmd: VehicleCommand = serde_json::from_str(json).unwrap();
        assert!(matches!(cmd, VehicleCommand::ToggleHood));
    }

    #[test]
    fn serde_set_window_with_null_id() {
        let json = r#"{"type":"set_window","id":null,"target":0.5}"#;
        let cmd: VehicleCommand = serde_json::from_str(json).unwrap();
        match cmd {
            VehicleCommand::SetWindow { id, target } => {
                assert!(id.is_none());
                assert!((target - 0.5).abs() < 1e-6);
            }
            other => panic!("expected SetWindow, got {other:?}"),
        }
    }

    // --- Power state tests (decision 8) ---

    #[test]
    fn defaults_power_state_is_standby() {
        let m = SignalModel::aura_t6();
        assert_eq!(m.snapshot().power_state, PowerState::Standby);
        assert!(!m.snapshot().driving);
    }

    #[test]
    fn sleep_rejects_all_commands_except_setpower_and_reset() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Sleep }).unwrap();
        assert_eq!(m.snapshot().power_state, PowerState::Sleep);

        // Regular commands rejected
        assert!(m.apply_command(&VehicleCommand::ToggleLock).is_err());
        assert!(m.apply_command(&VehicleCommand::ToggleDoor { id: None }).is_err());
        assert!(m.apply_command(&VehicleCommand::ToggleAc).is_err());

        // SetPower and Reset still work
        assert!(m.apply_command(&VehicleCommand::SetPower { state: PowerState::Standby }).is_ok());
        assert_eq!(m.snapshot().power_state, PowerState::Standby);
    }

    #[test]
    fn standby_rejects_high_voltage_commands() {
        let mut m = SignalModel::aura_t6();
        // Already at Standby by default
        assert_eq!(m.snapshot().power_state, PowerState::Standby);

        // High-voltage commands rejected
        assert!(m.apply_command(&VehicleCommand::ToggleAc).is_err());
        assert!(m.apply_command(&VehicleCommand::ToggleCharging).is_err());
        assert!(m.apply_command(&VehicleCommand::ToggleDriving { on: true }).is_err());

        // Non-high-voltage commands still work
        assert!(m.apply_command(&VehicleCommand::ToggleLock).is_ok());
    }

    #[test]
    fn ready_allows_all_commands() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Ready }).unwrap();
        assert_eq!(m.snapshot().power_state, PowerState::Ready);

        // High-voltage commands now work (with their own interlocks)
        assert!(m.apply_command(&VehicleCommand::ToggleAc).is_ok());
        assert!(m.snapshot().ac);
    }

    #[test]
    fn cannot_shutdown_while_driving() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Ready }).unwrap();
        // Unlock + close doors to allow driving
        m.apply_command(&VehicleCommand::ToggleLock).unwrap(); // unlock
        // Doors are already closed by default
        m.apply_command(&VehicleCommand::ToggleDriving { on: true }).unwrap();
        assert!(m.snapshot().driving);

        // Cannot shutdown while driving
        assert!(m.apply_command(&VehicleCommand::SetPower { state: PowerState::Sleep }).is_err());

        // Stop driving first, then shutdown works
        m.apply_command(&VehicleCommand::ToggleDriving { on: false }).unwrap();
        assert!(!m.snapshot().driving);
        assert!(m.apply_command(&VehicleCommand::SetPower { state: PowerState::Sleep }).is_ok());
    }

    #[test]
    fn tick_skipped_in_sleep() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::ToggleLock).unwrap();
        m.apply_command(&VehicleCommand::ToggleDoor { id: None }).unwrap();
        // Door angle is 0 before tick
        assert!((m.snapshot().doors["fl"].angle - 0.0).abs() < 1e-6);

        // Go to Sleep — tick should be skipped
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Sleep }).unwrap();
        m.tick(1.0);
        // Angle still 0 — tick was skipped
        assert!((m.snapshot().doors["fl"].angle - 0.0).abs() < 1e-6);

        // Back to Standby — tick works
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Standby }).unwrap();
        m.tick(1.0);
        assert!(m.snapshot().doors["fl"].angle > 0.5);
    }

    #[test]
    fn serde_set_power() {
        let json = r#"{"type":"set_power","state":"ready"}"#;
        let cmd: VehicleCommand = serde_json::from_str(json).unwrap();
        match cmd {
            VehicleCommand::SetPower { state } => assert_eq!(state, PowerState::Ready),
            other => panic!("expected SetPower, got {other:?}"),
        }
    }

    #[test]
    fn toggle_driving_sets_driving_flag() {
        let mut m = SignalModel::aura_t6();
        m.apply_command(&VehicleCommand::SetPower { state: PowerState::Ready }).unwrap();
        m.apply_command(&VehicleCommand::ToggleLock).unwrap(); // unlock
        m.apply_command(&VehicleCommand::ToggleDriving { on: true }).unwrap();
        assert!(m.snapshot().driving);
        m.apply_command(&VehicleCommand::ToggleDriving { on: false }).unwrap();
        assert!(!m.snapshot().driving);
    }
}
