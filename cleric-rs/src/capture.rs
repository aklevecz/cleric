//! Screen-region capture via GDI (BitBlt + GetDIBits) and the HP-bar red-fill
//! analysis. No third-party deps — straight Win32. Captures only the requested
//! rectangle (not the whole screen), so it stays cheap at higher poll rates.
//!
//! Like the Python version, this reads the composited desktop: the watched bar
//! must be visible/unoccluded, and a fullscreen-exclusive DirectX window can
//! return a black frame (would need the Desktop Duplication API to fix).

use std::mem::{size_of, zeroed};
use std::ptr::null_mut;

use windows_sys::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject, GetDC, GetDIBits,
    ReleaseDC, SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, HDC, SRCCOPY,
};

/// Holds the screen device context, reused across grabs to avoid re-acquiring
/// it every frame.
pub struct Capturer {
    screen_dc: HDC,
}

impl Capturer {
    pub fn new() -> Option<Self> {
        let dc = unsafe { GetDC(null_mut()) };
        if dc.is_null() {
            None
        } else {
            Some(Capturer { screen_dc: dc })
        }
    }

    /// Capture a rectangle of the desktop and return its pixels as BGRA bytes
    /// (4 per pixel, top-down rows). None if capture fails.
    pub fn grab(&self, left: i32, top: i32, width: i32, height: i32) -> Option<Vec<u8>> {
        if width <= 0 || height <= 0 {
            return None;
        }
        unsafe {
            let mem_dc = CreateCompatibleDC(self.screen_dc);
            if mem_dc.is_null() {
                return None;
            }
            let bmp = CreateCompatibleBitmap(self.screen_dc, width, height);
            if bmp.is_null() {
                DeleteDC(mem_dc);
                return None;
            }
            let old = SelectObject(mem_dc, bmp);

            let ok = BitBlt(mem_dc, 0, 0, width, height, self.screen_dc, left, top, SRCCOPY);

            let mut bmi: BITMAPINFO = zeroed();
            bmi.bmiHeader = BITMAPINFOHEADER {
                biSize: size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: width,
                biHeight: -height, // negative => top-down rows
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB as u32,
                biSizeImage: 0,
                biXPelsPerMeter: 0,
                biYPelsPerMeter: 0,
                biClrUsed: 0,
                biClrImportant: 0,
            };

            let mut buf = vec![0u8; (width * height * 4) as usize];
            let scanned = GetDIBits(
                mem_dc,
                bmp,
                0,
                height as u32,
                buf.as_mut_ptr() as *mut core::ffi::c_void,
                &mut bmi,
                DIB_RGB_COLORS,
            );

            SelectObject(mem_dc, old);
            DeleteObject(bmp);
            DeleteDC(mem_dc);

            if ok == 0 || scanned == 0 {
                None
            } else {
                Some(buf)
            }
        }
    }
}

impl Drop for Capturer {
    fn drop(&mut self) {
        unsafe {
            ReleaseDC(null_mut(), self.screen_dc);
        }
    }
}

/// Percentage of the bar that is filled, using the rightmost "red" column.
/// Pixels are BGRA; "red" matches the Python heuristic r>100 & r>1.5g & r>1.5b.
pub fn red_percentage(buf: &[u8], width: i32, height: i32) -> f32 {
    let w = width.max(0) as usize;
    let h = height.max(0) as usize;
    if w == 0 || h == 0 || buf.len() < w * h * 4 {
        return 0.0;
    }
    let mut rightmost: i32 = -1;
    for x in 0..w {
        for y in 0..h {
            let i = (y * w + x) * 4;
            let b = buf[i] as i32;
            let g = buf[i + 1] as i32;
            let r = buf[i + 2] as i32;
            // r > 100 && r > 1.5*g && r > 1.5*b  (integer form: 2r > 3g, 2r > 3b)
            if r > 100 && 2 * r > 3 * g && 2 * r > 3 * b {
                rightmost = x as i32;
                break; // this column has red; move on
            }
        }
    }
    if rightmost < 0 {
        return 0.0;
    }
    let total = (width - 1).max(1) as f32;
    ((rightmost as f32 / total) * 100.0 * 100.0).round() / 100.0
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_bar(width: i32, height: i32, red_cols: i32) -> Vec<u8> {
        let (w, h) = (width as usize, height as usize);
        let mut buf = vec![0u8; w * h * 4];
        for y in 0..h {
            for x in 0..w {
                let i = (y * w + x) * 4;
                if (x as i32) < red_cols {
                    buf[i] = 0; // B
                    buf[i + 1] = 0; // G
                    buf[i + 2] = 200; // R
                    buf[i + 3] = 255; // A
                }
            }
        }
        buf
    }

    #[test]
    fn half_full_bar() {
        // 10 wide, red in columns 0..5 -> rightmost red col = 4, 4/9*100 = 44.44
        let buf = make_bar(10, 3, 5);
        let p = red_percentage(&buf, 10, 3);
        assert!((p - 44.44).abs() < 0.01, "expected ~44.44, got {p}");
    }

    #[test]
    fn full_bar() {
        let buf = make_bar(10, 3, 10); // rightmost = 9 -> 100%
        assert!((red_percentage(&buf, 10, 3) - 100.0).abs() < 0.01);
    }

    #[test]
    fn empty_bar() {
        let buf = make_bar(10, 3, 0);
        assert_eq!(red_percentage(&buf, 10, 3), 0.0);
    }
}
