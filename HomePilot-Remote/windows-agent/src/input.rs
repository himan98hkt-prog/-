//! 휴대폰에서 온 입력 메시지를 PC 입력 동작으로 바꾼다.

use crate::platform::InputAction;
use homepilot_protocol::app::{ClientMsg, MonitorInfo};

/// 키 이름 → Windows 가상 키 코드.
pub fn key_name_to_vk(name: &str) -> Option<u16> {
    let n = name.trim().to_ascii_lowercase();
    let b = n.as_bytes();
    if b.len() == 1 {
        return match b[0] {
            c @ b'a'..=b'z' => Some((c - b'a' + 0x41) as u16),
            c @ b'0'..=b'9' => Some((c - b'0' + 0x30) as u16),
            _ => None,
        };
    }
    if let Some(num) = n.strip_prefix('f').and_then(|s| s.parse::<u16>().ok()) {
        return (1..=24).contains(&num).then(|| 0x70 + num - 1);
    }
    Some(match n.as_str() {
        "enter" | "return" => 0x0D,
        "backspace" => 0x08,
        "tab" => 0x09,
        "escape" | "esc" => 0x1B,
        "space" => 0x20,
        "pageup" => 0x21,
        "pagedown" => 0x22,
        "end" => 0x23,
        "home" => 0x24,
        "left" => 0x25,
        "up" => 0x26,
        "right" => 0x27,
        "down" => 0x28,
        "printscreen" => 0x2C,
        "insert" => 0x2D,
        "delete" | "del" => 0x2E,
        "shift" => 0x10,
        "ctrl" | "control" => 0x11,
        "alt" => 0x12,
        "pause" => 0x13,
        "capslock" => 0x14,
        "hangul" | "hanyeong" => 0x15, // 한/영
        "hanja" => 0x19,
        "win" | "meta" => 0x5B,
        "menu" | "apps" => 0x5D,
        _ => return None,
    })
}

/// 확장 키(스캔코드 E0 접두) 여부. Windows SendInput 에 KEYEVENTF_EXTENDEDKEY 로 전달해야 한다.
pub fn is_extended_vk(vk: u16) -> bool {
    matches!(vk, 0x21..=0x28 | 0x2C | 0x2D | 0x2E | 0x5B | 0x5D)
}

/// 비율 좌표(0~1)를 가상 데스크톱 픽셀 좌표로.
pub fn to_screen(mon: &MonitorInfo, x: f32, y: f32) -> (i32, i32) {
    let cx = x.clamp(0.0, 1.0);
    let cy = y.clamp(0.0, 1.0);
    let px = mon.x + (cx * (mon.width.saturating_sub(1)) as f32).round() as i32;
    let py = mon.y + (cy * (mon.height.saturating_sub(1)) as f32).round() as i32;
    (px, py)
}

/// 입력 메시지 → 동작 목록. 입력 메시지가 아니면 None.
pub fn translate(msg: &ClientMsg, mon: &MonitorInfo) -> Option<Vec<InputAction>> {
    use InputAction as A;
    Some(match msg {
        ClientMsg::MouseMove { x, y } => {
            let (x, y) = to_screen(mon, *x, *y);
            vec![A::MoveAbs { x, y }]
        }
        ClientMsg::MouseDelta { dx, dy } => {
            // 한 번에 너무 크게 튀지 않도록 제한
            let c = |v: i32| v.clamp(-2000, 2000);
            vec![A::MoveRel { dx: c(*dx), dy: c(*dy) }]
        }
        ClientMsg::MouseButton { button, down } => vec![A::Button { button: *button, down: *down }],
        ClientMsg::MouseClick { button, double } => {
            let mut v = vec![A::Button { button: *button, down: true }, A::Button { button: *button, down: false }];
            if *double {
                v.extend(v.clone());
            }
            v
        }
        ClientMsg::Wheel { dx, dy } => {
            // 한 칸 = WHEEL_DELTA(120). 과도한 값은 잘라낸다.
            let c = |v: f32| (v.clamp(-20.0, 20.0) * 120.0).round() as i32;
            vec![A::Wheel { dx: c(*dx), dy: c(*dy) }]
        }
        ClientMsg::KeyText { text } => {
            // 제어문자는 걸러 내고 길이를 제한한다 (붙여넣기 폭주 방지).
            let t: String = text.chars().filter(|c| !c.is_control() || *c == '\n' || *c == '\t').take(4096).collect();
            if t.is_empty() {
                vec![]
            } else {
                vec![A::Text(t)]
            }
        }
        ClientMsg::Key { key, down } => vec![A::Key { key: key.clone(), down: *down }],
        ClientMsg::KeyCombo { keys } => {
            let keys: Vec<&String> = keys.iter().take(5).collect();
            let mut v: Vec<A> = keys.iter().map(|k| A::Key { key: (*k).clone(), down: true }).collect();
            v.extend(keys.iter().rev().map(|k| A::Key { key: (*k).clone(), down: false }));
            v
        }
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use homepilot_protocol::app::MouseButton;

    fn mon() -> MonitorInfo {
        MonitorInfo { index: 1, name: "B".into(), x: -1920, y: 0, width: 1920, height: 1080, primary: false }
    }

    #[test]
    fn coordinates_respect_monitor_offset() {
        assert_eq!(to_screen(&mon(), 0.0, 0.0), (-1920, 0));
        assert_eq!(to_screen(&mon(), 1.0, 1.0), (-1, 1079));
        assert_eq!(to_screen(&mon(), 5.0, -1.0), (-1, 0));
    }

    #[test]
    fn key_names() {
        assert_eq!(key_name_to_vk("A"), Some(0x41));
        assert_eq!(key_name_to_vk("f12"), Some(0x7B));
        assert_eq!(key_name_to_vk("f25"), None);
        assert_eq!(key_name_to_vk("hangul"), Some(0x15));
        assert_eq!(key_name_to_vk("rm -rf"), None);
        assert!(is_extended_vk(key_name_to_vk("delete").unwrap()));
    }

    #[test]
    fn combo_releases_in_reverse() {
        let v = translate(&ClientMsg::KeyCombo { keys: vec!["ctrl".into(), "c".into()] }, &mon()).unwrap();
        assert_eq!(
            v,
            vec![
                InputAction::Key { key: "ctrl".into(), down: true },
                InputAction::Key { key: "c".into(), down: true },
                InputAction::Key { key: "c".into(), down: false },
                InputAction::Key { key: "ctrl".into(), down: false },
            ]
        );
    }

    #[test]
    fn double_click_and_korean_text() {
        let v = translate(&ClientMsg::MouseClick { button: MouseButton::Left, double: true }, &mon()).unwrap();
        assert_eq!(v.len(), 4);
        let v = translate(&ClientMsg::KeyText { text: "한글\u{1b}입력".into() }, &mon()).unwrap();
        assert_eq!(v, vec![InputAction::Text("한글입력".into())]);
        assert!(translate(&ClientMsg::GetStatus, &mon()).is_none());
    }

    #[test]
    fn mouse_delta_is_clamped() {
        let v = translate(&ClientMsg::MouseDelta { dx: 15, dy: -99999 }, &mon()).unwrap();
        assert_eq!(v, vec![InputAction::MoveRel { dx: 15, dy: -2000 }]);
    }
}
