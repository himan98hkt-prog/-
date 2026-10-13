//! 접속 기록 (JSON Lines). 사용자가 언제, 어떤 기기가 접속했는지 확인할 수 있게 한다.

use serde::Serialize;
use std::io::Write;
use std::path::PathBuf;
use std::sync::Mutex;

pub struct Audit {
    path: PathBuf,
    lock: Mutex<()>,
}

#[derive(Serialize)]
struct Entry<'a> {
    ts: u64,
    event: &'a str,
    client: &'a str,
    fingerprint: &'a str,
    detail: &'a str,
}

impl Audit {
    pub fn new(path: PathBuf) -> Self {
        Self { path, lock: Mutex::new(()) }
    }

    pub fn record(&self, event: &str, client: &str, fingerprint: &str, detail: &str) {
        tracing::info!(event, client, fingerprint, detail, "접속 기록");
        let e = Entry { ts: crate::trust::now_unix(), event, client, fingerprint, detail };
        let Ok(mut line) = serde_json::to_vec(&e) else { return };
        line.push(b'\n');
        let _g = self.lock.lock().unwrap_or_else(|p| p.into_inner());
        let r = std::fs::OpenOptions::new().create(true).append(true).open(&self.path).and_then(|mut f| f.write_all(&line));
        if let Err(err) = r {
            tracing::warn!("접속 기록 저장 실패: {err}");
        }
    }

    /// 최근 n 줄.
    pub fn tail(&self, n: usize) -> Vec<String> {
        let s = std::fs::read_to_string(&self.path).unwrap_or_default();
        let lines: Vec<&str> = s.lines().collect();
        lines[lines.len().saturating_sub(n)..].iter().map(|l| l.to_string()).collect()
    }
}
