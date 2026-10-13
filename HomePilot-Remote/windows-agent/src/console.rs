//! 콘솔 모드(--headless --console): 표준입력으로 에이전트를 조작한다.
//! 서버형 PC 나 자동 테스트에서 트레이 메뉴 대신 쓴다.
//!   y / n      등록 요청 승인 / 거부
//!   block      긴급 차단        unblock   차단 해제
//!   pair       새 기기 등록 5분  end       현재 연결 끊기
//!   status     상태 출력

use crate::app::{Approver, Shared, MENU_PAIRING};
use std::io::BufRead;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::Duration;

static PENDING: Mutex<Option<mpsc::Sender<bool>>> = Mutex::new(None);

pub fn approver() -> Approver {
    Arc::new(|name: &str, fp: &str, sas: &str| {
        let (tx, rx) = mpsc::channel();
        *PENDING.lock().unwrap() = Some(tx);
        println!("[등록 요청] 이름: {name}  지문: {fp}  확인 코드: {sas}  → 같으면 y, 아니면 n 입력");
        let ok = rx.recv_timeout(Duration::from_secs(120)).unwrap_or(false);
        *PENDING.lock().unwrap() = None;
        ok
    })
}

pub fn spawn_reader(shared: Arc<Shared>) {
    std::thread::Builder::new()
        .name("console".into())
        .spawn(move || {
            for line in std::io::stdin().lock().lines() {
                let Ok(line) = line else { break };
                match line.trim() {
                    "y" | "n" => {
                        if let Some(tx) = PENDING.lock().unwrap().take() {
                            let _ = tx.send(line.trim() == "y");
                        } else {
                            println!("대기 중인 등록 요청이 없습니다");
                        }
                    }
                    "block" => shared.emergency_block(),
                    "unblock" => shared.unblock(),
                    "pair" => shared.open_pairing(MENU_PAIRING),
                    "end" => shared.end_all_sessions("PC 사용자가 연결을 끊었습니다"),
                    "status" => println!(
                        "온라인:{} 차단:{} 세션:{:?} 등록대기:{:?}",
                        shared.relay_online.load(std::sync::atomic::Ordering::Relaxed),
                        shared.is_blocked(),
                        shared.active_sessions().iter().map(|s| s.client_name.clone()).collect::<Vec<_>>(),
                        shared.pairing_remaining().map(|d| d.as_secs())
                    ),
                    "" => {}
                    other => println!("알 수 없는 명령: {other}"),
                }
            }
        })
        .expect("콘솔 스레드 시작 실패");
}
