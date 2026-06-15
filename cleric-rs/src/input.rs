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
    MapVirtualKeyW, SendInput, INPUT, INPUT_KEYBOARD, INPUT_MOUSE, KEYBDINPUT, KEYEVENTF_KEYUP,
    KEYEVENTF_SCANCODE, MAPVK_VK_TO_VSC, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_WHEEL, MOUSEINPUT,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    GetSystemMetrics, SetCursorPos, SM_CXSCREEN, SM_CYSCREEN,
};

const WHEEL_DELTA: i32 = 120;

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

fn send_mouse(flags: u32, data: i32) {
    unsafe {
        let mut input: INPUT = zeroed();
        input.r#type = INPUT_MOUSE;
        input.Anonymous.mi = MOUSEINPUT {
            dx: 0,
            dy: 0,
            mouseData: data as u32,
            dwFlags: flags,
            time: 0,
            dwExtraInfo: 0,
        };
        SendInput(1, &input as *const INPUT, size_of::<INPUT>() as i32);
    }
}

/// Move the cursor to screen center (matches the Python center_mouse before a
/// mouse binding, so scroll/click land on the game viewport).
fn center_mouse() {
    unsafe {
        let cx = GetSystemMetrics(SM_CXSCREEN) / 2;
        let cy = GetSystemMetrics(SM_CYSCREEN) / 2;
        SetCursorPos(cx, cy);
    }
}

fn mouse_click() {
    send_mouse(MOUSEEVENTF_LEFTDOWN, 0);
    sleep(Duration::from_millis(200));
    send_mouse(MOUSEEVENTF_LEFTUP, 0);
}

/// Scroll `notches` wheel steps (sign = direction). Capped so a huge value like
/// -10000 ("zoom all the way out") doesn't fire thousands of events.
fn mouse_scroll(notches: i32) {
    let n = notches.abs().min(500);
    let dir = if notches < 0 { -1 } else { 1 };
    for _ in 0..n {
        send_mouse(MOUSEEVENTF_WHEEL, dir * WHEEL_DELTA);
        sleep(Duration::from_millis(2));
    }
}

/// Parse the Python mouse mini-DSL: `mouse.scroll(x,y)` or `mouse.click()`.
fn run_mouse_step(step: &str) {
    center_mouse();
    if let Some(args) = step.strip_prefix("mouse.scroll(").and_then(|s| s.strip_suffix(')')) {
        // args = "x,y"; the y component is the wheel amount, like pynput.
        let parts: Vec<&str> = args.split(',').collect();
        if let Some(y) = parts.get(1).and_then(|s| s.trim().parse::<i32>().ok()) {
            mouse_scroll(y);
        }
    } else if step.contains("mouse.click()") {
        mouse_click();
    } else {
        eprintln!("[input] unrecognized mouse step: {step}");
    }
}

/// Run a binding string: `;`-separated steps, each a `+`-joined chord or a
/// `mouse.*` action.
pub fn press_binding(binding: &str) {
    for step in binding.split(';') {
        let step = step.trim();
        if step.is_empty() {
            continue;
        }
        if step.contains("mouse") {
            run_mouse_step(step);
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
