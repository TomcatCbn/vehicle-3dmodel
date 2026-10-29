//! Interlock checks — consolidated from three existing locations
//! (main.js event handlers, state.js setCharging, drive-state.js setDriving).
//! Per decision 5 D5.4 and AGENTS.md interlock conventions.
//! Power state interlocks per decision 8 D8.6.

use crate::signal::state::VehicleState;

/// "解锁后才能开门" — unlock before open door.
pub fn can_open_door(state: &VehicleState) -> Result<(), &'static str> {
    if state.locked {
        return Err("请先解锁车辆");
    }
    Ok(())
}

/// "关门后才能上锁" — close door before lock.
pub fn can_lock(state: &VehicleState) -> Result<(), &'static str> {
    let any_door_open = state.doors.values().any(|d| d.open);
    if any_door_open {
        return Err("请先关闭车门，再锁定车辆");
    }
    Ok(())
}

/// "插枪后才能充电" — plug before charge.
pub fn can_charge(state: &VehicleState, on: bool) -> Result<(), &'static str> {
    if on && !state.plugged {
        return Err("请先连接充电枪");
    }
    if on && state.battery >= 100.0 {
        return Err("电量已满");
    }
    Ok(())
}

/// "车门/机盖/尾门未关拢或充电枪连接时禁止起步" — no start when parts open or plugged.
/// Checks actual positions (angle/position), not just logical open flags,
/// matching drive-state.js setDriving L13.
pub fn can_start_driving(state: &VehicleState) -> Result<(), &'static str> {
    let any_door_not_closed = state
        .doors
        .values()
        .any(|d| d.open || d.angle > 0.01);
    if any_door_not_closed {
        return Err("请先关好车门");
    }
    if state.hood.open || state.hood.angle > 0.01 {
        return Err("请先关好机盖");
    }
    if state.tailgate.target > 0.001 || state.tailgate.position > 0.001 {
        return Err("请先关好尾门");
    }
    if state.plugged {
        return Err("请拔出充电枪");
    }
    Ok(())
}

/// "行驶中不能熄火" — cannot shutdown while driving (decision 8 D8.6).
pub fn can_shutdown(state: &VehicleState) -> Result<(), &'static str> {
    if state.driving {
        return Err("请先停止行驶");
    }
    Ok(())
}

/// Check if a command requires high-voltage (Ready) power state.
/// Returns true for AC, charging, and driving start (decision 8 D8.12).
pub fn is_high_voltage_command(cmd: &crate::signal::command::VehicleCommand) -> bool {
    use crate::signal::command::VehicleCommand;
    matches!(
        cmd,
        VehicleCommand::ToggleAc
            | VehicleCommand::ToggleCharging
            | VehicleCommand::ToggleDriving { on: true }
    )
}
