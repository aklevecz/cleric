//! Drag-a-box overlay — a native fullscreen, translucent, topmost window you
//! drag a rectangle on (like the old Python tkinter selector). Returns the
//! selected rectangle in screen pixels. Left-drag to select, release to confirm,
//! right-click or Esc to cancel.
//!
//! Win32 only (no extra crates). Note: works for windowed games; a
//! fullscreen-exclusive DirectX window renders above all other windows, so the
//! overlay won't show there (use `calibrate <name> corners` instead).

use std::cell::RefCell;
use std::iter::once;
use std::mem::zeroed;
use std::ptr::null_mut;

use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, RECT, WPARAM};
use windows_sys::Win32::Graphics::Gdi::{
    BeginPaint, CreatePen, CreateSolidBrush, DeleteObject, EndPaint, FillRect, GetStockObject,
    InvalidateRect, Rectangle, SelectObject, UpdateWindow, NULL_BRUSH, PAINTSTRUCT, PS_SOLID,
};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW, GetClientRect, GetMessageW,
    GetSystemMetrics, LoadCursorW, PostQuitMessage, RegisterClassW,
    SetForegroundWindow, SetLayeredWindowAttributes, ShowWindow, TranslateMessage,
    UnregisterClassW, IDC_CROSS, LWA_ALPHA, MSG, SM_CXVIRTUALSCREEN,
    SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SW_SHOW, WM_DESTROY, WM_KEYDOWN,
    WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE, WM_PAINT, WM_RBUTTONDOWN, WNDCLASSW, WS_EX_LAYERED,
    WS_EX_TOPMOST, WS_POPUP,
};

#[derive(Default, Clone, Copy)]
struct Draw {
    dragging: bool,
    have: bool,
    sx: i32,
    sy: i32,
    cx: i32,
    cy: i32,
    ox: i32, // screen origin (virtual-screen left/top) to map client -> screen
    oy: i32,
    cancelled: bool,
}

thread_local! {
    static STATE: RefCell<Draw> = RefCell::new(Draw::default());
}

fn rgb(r: u8, g: u8, b: u8) -> u32 {
    (r as u32) | ((g as u32) << 8) | ((b as u32) << 16)
}

fn lparam_xy(lp: LPARAM) -> (i32, i32) {
    let x = (lp & 0xFFFF) as u16 as i16 as i32;
    let y = ((lp >> 16) & 0xFFFF) as u16 as i16 as i32;
    (x, y)
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(once(0)).collect()
}

unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_LBUTTONDOWN => {
            let (x, y) = lparam_xy(lp);
            STATE.with(|s| {
                let mut s = s.borrow_mut();
                s.dragging = true;
                s.have = true;
                s.sx = x;
                s.sy = y;
                s.cx = x;
                s.cy = y;
            });
            InvalidateRect(hwnd, null_mut(), 1);
            0
        }
        WM_MOUSEMOVE => {
            let mut redraw = false;
            STATE.with(|s| {
                let mut s = s.borrow_mut();
                if s.dragging {
                    let (x, y) = lparam_xy(lp);
                    s.cx = x;
                    s.cy = y;
                    redraw = true;
                }
            });
            if redraw {
                InvalidateRect(hwnd, null_mut(), 1);
            }
            0
        }
        WM_LBUTTONUP => {
            STATE.with(|s| s.borrow_mut().dragging = false);
            PostQuitMessage(0);
            0
        }
        WM_RBUTTONDOWN => {
            STATE.with(|s| s.borrow_mut().cancelled = true);
            PostQuitMessage(0);
            0
        }
        WM_KEYDOWN => {
            if (wp as i32) == 0x1B {
                // Esc
                STATE.with(|s| s.borrow_mut().cancelled = true);
                PostQuitMessage(0);
            }
            0
        }
        WM_PAINT => {
            paint(hwnd);
            0
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

unsafe fn paint(hwnd: HWND) {
    let mut ps: PAINTSTRUCT = zeroed();
    let hdc = BeginPaint(hwnd, &mut ps);

    let mut rc: RECT = zeroed();
    GetClientRect(hwnd, &mut rc);
    let dim = CreateSolidBrush(rgb(15, 15, 18));
    FillRect(hdc, &rc, dim);
    DeleteObject(dim);

    let (have, sx, sy, cx, cy) = STATE.with(|s| {
        let s = s.borrow();
        (s.have, s.sx, s.sy, s.cx, s.cy)
    });
    if have {
        let pen = CreatePen(PS_SOLID, 2, rgb(255, 50, 50));
        let old_pen = SelectObject(hdc, pen);
        let old_brush = SelectObject(hdc, GetStockObject(NULL_BRUSH));
        Rectangle(hdc, sx.min(cx), sy.min(cy), sx.max(cx), sy.max(cy));
        SelectObject(hdc, old_pen);
        SelectObject(hdc, old_brush);
        DeleteObject(pen);
    }
    EndPaint(hwnd, &ps);
}

/// Show the overlay and return the selected rectangle (left, top, width,
/// height) in screen pixels, or None if cancelled / too small.
pub fn draw_box() -> Option<(i32, i32, i32, i32)> {
    unsafe {
        let hinst = GetModuleHandleW(null_mut());
        let class = wide("cleric_overlay");

        let wc = WNDCLASSW {
            style: 0,
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: hinst,
            hIcon: null_mut(),
            hCursor: LoadCursorW(null_mut(), IDC_CROSS),
            hbrBackground: null_mut(),
            lpszMenuName: null_mut(),
            lpszClassName: class.as_ptr(),
        };
        RegisterClassW(&wc);

        let vx = GetSystemMetrics(SM_XVIRTUALSCREEN);
        let vy = GetSystemMetrics(SM_YVIRTUALSCREEN);
        let vw = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        let vh = GetSystemMetrics(SM_CYVIRTUALSCREEN);

        STATE.with(|s| {
            let mut s = s.borrow_mut();
            *s = Draw::default();
            s.ox = vx;
            s.oy = vy;
        });

        let hwnd = CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST,
            class.as_ptr(),
            wide("cleric overlay").as_ptr(),
            WS_POPUP,
            vx,
            vy,
            vw,
            vh,
            null_mut(),
            null_mut(),
            hinst,
            null_mut(),
        );
        if hwnd.is_null() {
            UnregisterClassW(class.as_ptr(), hinst);
            eprintln!("[draw] could not create overlay window");
            return None;
        }

        // ~45% opaque dim so the game shows through.
        SetLayeredWindowAttributes(hwnd, 0, 115, LWA_ALPHA);
        ShowWindow(hwnd, SW_SHOW);
        SetForegroundWindow(hwnd);
        UpdateWindow(hwnd);

        let mut msg: MSG = zeroed();
        while GetMessageW(&mut msg, null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        DestroyWindow(hwnd);
        UnregisterClassW(class.as_ptr(), hinst);

        STATE.with(|s| {
            let s = s.borrow();
            if s.cancelled || !s.have {
                return None;
            }
            let left = s.sx.min(s.cx) + s.ox;
            let top = s.sy.min(s.cy) + s.oy;
            let width = (s.sx - s.cx).abs();
            let height = (s.sy - s.cy).abs();
            if width < 2 || height < 2 {
                None
            } else {
                Some((left, top, width, height))
            }
        })
    }
}
