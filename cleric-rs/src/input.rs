//! Keyboard output via SendInput with hardware scan codes (games ignore zero
//! scan-code synthetic keys — same reason the Python/eq-bot code uses scancodes).
//!
//! Supports the binding mini-DSL from the Python version: `;`-separated steps,
//! each a `+`-joined combo, e.g. "shift+x" or "ctrl+s". Mouse bindings
//! (`mouse.scroll(...)`) are not ported yet and are skipped with a warning.

use std::mem::{size_of, zeroed};
use std::thread::sleep;
use std::time::Duration;

use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    MapVirtualKeyW, SendInput, INPUT, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
    KEYEVENTF_SCANCODE, MAPVK_VK_TO_VSC,
};

fn vk_to_scan(vk: u16) -> u16 {
    unsafe { MapVirtualKeyW(vk as u32, MAPVK_VK_TO_VSC) as u16 }
}

fn send_scan(scan: u16, up: bool) {
    unsafe {
        let mut input: INPUT = zeroed();
        input.r#type = INPUT_KEYBOARD;
        input.Anonymous.ki = KEYBDINPUT {
            wVk: 0,
            wScan: scan,
            dwFlags: KEYEVENTF_SCANCODE | if up { KEYEVENTF_KEYUP } else { 0 },
            time: 0,
            dwExtraInfo: 0,
        };
        SendInput(1, &input as *const INPUT, size_of::<INPUT>() as i32);
    }
}

/// Map a key name to a Win32 virtual-key code.
fn name_to_vk(name: &str) -> Option<u16> {
    let n = name.trim().to_lowercase();
    if n.chars().count() == 1 {
        let c = n.chars().next().unwrap();
        if c.is_ascii_digit() {
            return Some(c as u16); // '0'..'9' VK == ASCII
        }
        if c.is_ascii_lowercase() {
            return Some((c as u8 - b'a' + b'A') as u16); // letter VK == uppercase ASCII
        }
    }
    Some(match n.as_str() {
        "shift" => 0x10,
        "ctrl" | "control" => 0x11,
        "alt" => 0x12,
        "enter" | "return" => 0x0D,
        "space" => 0x20,
        "esc" | "escape" => 0x1B,
        "tab" => 0x09,
        "f1" => 0x70,
        "f2" => 0x71,
        "f3" => 0x72,
        "f4" => 0x73,
        "f5" => 0x74,
        "f6" => 0x75,
        "f7" => 0x76,
        "f8" => 0x77,
        "f9" => 0x78,
        "f10" => 0x79,
        "f11" => 0x7A,
        "f12" => 0x7B,
        _ => return None,
    })
}

/// Press a single key (down + up) by name.
pub fn tap(name: &str) {
    if let Some(vk) = name_to_vk(name) {
        let scan = vk_to_scan(vk);
        send_scan(scan, false);
        sleep(Duration::from_millis(20));
        send_scan(scan, true);
    }
}

/// Run a binding string: `;`-separated steps, each a `+`-joined chord.
pub fn press_binding(binding: &str) {
    for step in binding.split(';') {
        let step = step.trim();
        if step.is_empty() {
            continue;
        }
        if step.contains("mouse") {
            eprintln!("[input] mouse bindings not supported yet, skipping: {step}");
            continue;
        }
        let vks: Vec<u16> = step.split('+').filter_map(name_to_vk).collect();
        if vks.is_empty() {
            continue;
        }
        for &vk in &vks {
            send_scan(vk_to_scan(vk), false);
        }
        sleep(Duration::from_millis(120));
        for &vk in vks.iter().rev() {
            send_scan(vk_to_scan(vk), true);
        }
    }
}

/// Sit (Ctrl+S in the Python version).
pub fn sit() {
    press_binding("ctrl+s");
}

/// Duck to cancel an in-progress cast — tap crouch twice, like the Python duck().
pub fn duck() {
    tap("x");
    sleep(Duration::from_millis(200));
    tap("x");
}
