//! Native bounding-box calibration — replaces the Python tkinter draw-a-box
//! tool. You point at the two corners of a health bar and tap F8; the screen
//! coordinates are captured (globally, regardless of which window has focus)
//! and saved to config.json. Esc cancels.

use std::mem::zeroed;
use std::thread::sleep;
use std::time::Duration;

use windows_sys::Win32::Foundation::POINT;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
use windows_sys::Win32::UI::WindowsAndMessaging::GetCursorPos;

use crate::capture::{red_percentage, Capturer};
use crate::config::{self, BBox};

const VK_F8: i32 = 0x77;
const VK_ESC: i32 = 0x1B;

fn key_down(vk: i32) -> bool {
    unsafe { (GetAsyncKeyState(vk) as u16 & 0x8000) != 0 }
}

fn cursor_pos() -> (i32, i32) {
    unsafe {
        let mut p: POINT = zeroed();
        GetCursorPos(&mut p);
        (p.x, p.y)
    }
}

/// Block until F8 is tapped (returns Some(pos) on the release) or Esc cancels
/// (returns None).
fn wait_for_corner() -> Option<(i32, i32)> {
    loop {
        if key_down(VK_ESC) {
            return None;
        }
        if key_down(VK_F8) {
            let pos = cursor_pos();
            while key_down(VK_F8) {
                sleep(Duration::from_millis(10));
            }
            return Some(pos);
        }
        sleep(Duration::from_millis(15));
    }
}

/// Capture a rectangle by pointing at its two corners (F8 each, Esc cancels).
/// Returns (left, top, width, height) in screen pixels. Shared by the CLI
/// `calibrate` command and the web UI. Prints console hints (harmless if driven
/// from the browser).
pub fn capture_box() -> Option<(i32, i32, i32, i32)> {
    println!("1) Move the mouse to the bar's TOP-LEFT corner, then tap F8  (Esc to cancel)");
    let (x1, y1) = wait_for_corner()?;
    println!("   top-left     = ({x1}, {y1})");
    println!("2) Move the mouse to the bar's BOTTOM-RIGHT corner, then tap F8");
    let (x2, y2) = wait_for_corner()?;
    println!("   bottom-right = ({x2}, {y2})");

    let left = x1.min(x2);
    let top = y1.min(y2);
    let width = (x1 - x2).abs();
    let height = (y1 - y2).abs();
    if width < 2 || height < 2 {
        eprintln!("box is too small ({width}x{height}) — try again.");
        return None;
    }
    Some((left, top, width, height))
}

/// Save a captured rectangle as a named bounding box, make it the default guy,
/// and read it back. Returns the live fill % on success. Shared by the CLI
/// `calibrate` command (drag overlay or F8 corners) and the web UI.
pub fn save_box(name: &str, left: i32, top: i32, width: i32, height: i32) -> Result<f32, String> {
    let mut cfg = config::load();
    cfg.bounding_boxes.insert(
        name.to_string(),
        BBox {
            left: left as f64,
            top: top as f64,
            width: width as f64,
            height: height as f64,
        },
    );
    cfg.default_guy = name.to_string();
    config::save(&cfg).map_err(|e| e.to_string())?;

    // Immediate read-back so you can confirm the box lines up.
    let pct = Capturer::new()
        .and_then(|cap| cap.grab(left, top, width, height))
        .map(|buf| red_percentage(&buf, width, height))
        .unwrap_or(0.0);
    Ok(pct)
}
