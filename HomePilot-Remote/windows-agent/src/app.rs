//! 에이전트 전역 상태. 네트워크(tokio)와 화면 UI(Win32 메시지 루프)가 함께 쓴다.

use crate::audit::Audit;
use crate::config::{Config, Paths};
use crate::trust::TrustStore;
use homepilot_protocol::app::SystemStatus;
use homepilot_protocol::secure::{device_id_from_public, fingerprint, StaticKeypair};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, Instant};
use tokio::sync::watch;

/// 처음 실행했는데 등록 기기가 없으면 자동으로 열리는 등록 대기 시간.
pub const FIRST_RUN_PAIRING: Duration = Duration::from_secs(10 * 60);
/// 트레이 메뉴 "새 휴대폰 등록" 시 등록 대기 시간.
pub const MENU_PAIRING: Duration = Duration::from_secs(5 * 60);

/// UI 에 보여 줄 현재 세션 정보.
#[derive(Debug, Clone)]
pub struct SessionView {
    pub client_name: String,
    pub controlling: bool,
}

pub struct SessionEntry {
    pub view: Option<SessionView>,
    /// Some(사유) 를 보내면 세션이 즉시 종료된다.
    pub cancel: watch::Sender<Option<String>>,
}

/// 등록 승인을 묻는 방법 (Windows: 확인창, 콘솔: 표준입력, 테스트: 자동 거부).
pub type Approver = Arc<dyn Fn(&str, &str, &str) -> bool + Send + Sync>;

pub struct Shared {
    pub paths: Paths,
    pub config: Mutex<Config>,
    pub trust: Mutex<TrustStore>,
    pub audit: Audit,
    pub keypair: StaticKeypair,
    pub device_id: String,
    pub status: Arc<RwLock<SystemStatus>>,
    pub relay_online: AtomicBool,
    pub sessions: Mutex<HashMap<u64, SessionEntry>>,
    next_session: AtomicU64,
    pairing_until: Mutex<Option<Instant>>,
    /// 등록 확인창은 한 번에 하나만 띄운다 (요청 폭주로 사용자가 실수로 승인하는 것을 방지).
    pub pairing_busy: AtomicBool,
    pub approver: Approver,
    /// 휴대폰이 접속할 외부 주소 (터널 사용 시)와 상태 설명.
    pub public_url: Mutex<(Option<String>, Option<String>)>,
    /// 내장 중계 서버에 에이전트로 등록할 때 쓰는 비밀 토큰.
    pub agent_token: Mutex<Option<String>>,
    /// UI 갱신 요청 (Windows 에서는 트레이/표시줄 다시 그리기).
    pub ui_refresh: Mutex<Option<Box<dyn Fn() + Send + Sync>>>,
    /// 트레이 알림으로 보여 줄 안내 (제목, 내용). UI 가 꺼내 간다.
    pub notice: Mutex<Option<(String, String)>>,
}

impl Shared {
    pub fn new(paths: Paths, config: Config, trust: TrustStore, keypair: StaticKeypair, approver: Approver) -> Arc<Self> {
        let device_id = device_id_from_public(&keypair.public);
        let first_run = trust.clients.is_empty();
        let s = Arc::new(Self {
            audit: Audit::new(paths.audit_file()),
            paths,
            config: Mutex::new(config),
            trust: Mutex::new(trust),
            keypair,
            device_id,
            status: Arc::new(RwLock::new(SystemStatus::default())),
            relay_online: AtomicBool::new(false),
            sessions: Mutex::new(HashMap::new()),
            next_session: AtomicU64::new(1),
            pairing_until: Mutex::new(None),
            pairing_busy: AtomicBool::new(false),
            approver,
            public_url: Mutex::new((None, None)),
            agent_token: Mutex::new(None),
            ui_refresh: Mutex::new(None),
            notice: Mutex::new(None),
        });
        if first_run {
            s.open_pairing(FIRST_RUN_PAIRING);
        }
        s
    }

    pub fn fingerprint(&self) -> String {
        fingerprint(&self.keypair.public)
    }

    pub fn display_name(&self) -> String {
        self.config.lock().unwrap().display_name()
    }

    /// 디스크의 등록 목록을 다시 읽는다. 명령줄(`revoke`, `trust-client`)로 바꾼 내용이
    /// 실행 중인 에이전트에도 바로 적용되도록 인증 직전에 호출한다.
    pub fn reload_trust(&self) {
        match TrustStore::load(&self.paths) {
            Ok(t) => *self.trust.lock().unwrap() = t,
            Err(e) => tracing::error!("등록 목록 읽기 실패 (이전 목록 유지): {e:#}"),
        }
    }

    pub fn set_public_url(&self, url: Option<String>, note: Option<String>) {
        let file = self.paths.public_url_file();
        match &url {
            Some(u) => {
                let _ = std::fs::write(&file, u);
            }
            None => {
                let _ = std::fs::remove_file(&file);
            }
        }
        *self.public_url.lock().unwrap() = (url, note);
        self.refresh_ui();
    }

    /// 휴대폰 앱에 입력할 중계 주소 설명 (UI 용).
    pub fn phone_relay_text(&self) -> String {
        let cfg = self.config.lock().unwrap();
        if cfg.local_relay && cfg.tunnel == "quick" {
            let (url, note) = self.public_url.lock().unwrap().clone();
            return url.unwrap_or_else(|| note.unwrap_or_else(|| "준비 중…".into()));
        }
        if cfg.local_relay {
            return format!("ws://<이 PC 의 IP>:{} (같은 Wi-Fi 전용, 터널 꺼짐)", cfg.local_relay_port);
        }
        cfg.relay_url.replace("ws://", "http://").replace("wss://", "https://")
    }

    pub fn refresh_ui(&self) {
        if let Some(f) = self.ui_refresh.lock().unwrap().as_ref() {
            f();
        }
    }

    pub fn is_blocked(&self) -> bool {
        self.config.lock().unwrap().remote_blocked
    }

    /// PC 화면에 트레이 알림을 띄운다.
    pub fn notify(&self, title: &str, text: &str) {
        *self.notice.lock().unwrap() = Some((title.into(), text.into()));
        self.refresh_ui();
    }

    /// 명령줄(`homepilot-cli unblock`)로 바꾼 차단 상태를 실행 중인 에이전트에도 반영한다.
    /// 인증 직전에 호출 (등록 목록 `reload_trust` 와 같은 이유).
    pub fn reload_block_state(&self) {
        let Ok(disk) = Config::load(&self.paths.config_file()) else { return };
        let changed = {
            let mut c = self.config.lock().unwrap();
            let changed = c.remote_blocked != disk.remote_blocked;
            c.remote_blocked = disk.remote_blocked;
            changed
        };
        if changed {
            self.refresh_ui();
        }
    }

    pub fn open_pairing(&self, dur: Duration) {
        *self.pairing_until.lock().unwrap() = Some(Instant::now() + dur);
        tracing::info!("새 기기 등록 대기 {}분", dur.as_secs() / 60);
        self.refresh_ui();
    }

    pub fn close_pairing(&self) {
        *self.pairing_until.lock().unwrap() = None;
        self.refresh_ui();
    }

    /// 남은 등록 대기 시간 (없으면 None).
    pub fn pairing_remaining(&self) -> Option<Duration> {
        let g = self.pairing_until.lock().unwrap();
        g.and_then(|t| t.checked_duration_since(Instant::now()))
    }

    pub fn register_session(&self) -> (u64, watch::Receiver<Option<String>>) {
        let id = self.next_session.fetch_add(1, Ordering::Relaxed);
        let (tx, rx) = watch::channel(None);
        self.sessions.lock().unwrap().insert(id, SessionEntry { view: None, cancel: tx });
        (id, rx)
    }

    pub fn set_session_view(&self, id: u64, view: SessionView) {
        if let Some(e) = self.sessions.lock().unwrap().get_mut(&id) {
            e.view = Some(view);
        }
        self.refresh_ui();
    }

    pub fn unregister_session(&self, id: u64) {
        let had_view = self.sessions.lock().unwrap().remove(&id).and_then(|e| e.view).is_some();
        if had_view {
            self.refresh_ui();
        }
    }

    /// 인증이 끝난(화면에 표시해야 하는) 세션 목록.
    pub fn active_sessions(&self) -> Vec<SessionView> {
        self.sessions.lock().unwrap().values().filter_map(|e| e.view.clone()).collect()
    }

    pub fn end_all_sessions(&self, reason: &str) {
        for e in self.sessions.lock().unwrap().values() {
            let _ = e.cancel.send(Some(reason.to_string()));
        }
    }

    /// 긴급 차단: 모든 세션 즉시 종료 + 다시 허용할 때까지 접속 거부 (재부팅 후에도 유지).
    pub fn emergency_block(&self) {
        {
            let mut c = self.config.lock().unwrap();
            c.remote_blocked = true;
            if let Err(e) = c.save(&self.paths.config_file()) {
                tracing::error!("차단 상태 저장 실패: {e:#}");
            }
        }
        self.close_pairing();
        self.end_all_sessions("PC 사용자가 원격 제어를 차단했습니다");
        self.audit.record("emergency_block", "-", "-", "PC 에서 긴급 차단");
        self.refresh_ui();
    }

    pub fn unblock(&self) {
        {
            let mut c = self.config.lock().unwrap();
            c.remote_blocked = false;
            if let Err(e) = c.save(&self.paths.config_file()) {
                tracing::error!("차단 해제 저장 실패: {e:#}");
            }
        }
        self.audit.record("unblock", "-", "-", "PC 에서 원격 제어 다시 허용");
        self.refresh_ui();
    }

    /// 모든 등록 기기 해제 + 연결 종료.
    pub fn revoke_all(&self) {
        {
            let mut t = self.trust.lock().unwrap();
            t.clients.clear();
            if let Err(e) = t.save() {
                tracing::error!("등록 목록 저장 실패: {e:#}");
            }
        }
        self.end_all_sessions("PC 에서 기기 등록이 해제되었습니다");
        self.audit.record("revoke_all", "-", "-", "모든 등록 기기 해제");
        self.refresh_ui();
    }
}
