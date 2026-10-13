//! AI 작업 관리: 휴대폰에서 PC 의 AI 도구에 일을 시키고, 연결을 끊어도 PC 에서 계속 실행된다.
//!
//! - Claude Code: PC 에 설치·로그인된 공식 CLI 를 그대로 실행 (`claude -p`, 사용자의 구독으로 동작).
//!   API 키를 쓰지 않는다. 프롬프트는 명령줄이 아니라 표준 입력으로 넘겨 명령 주입을 막는다.
//!   기본은 읽기 전용, "수정 허용" 을 고른 경우에만 `--permission-mode acceptEdits`.
//!   (모든 권한 건너뛰기 모드는 쓰지 않는다)
//! - Ollama: 이 PC 의 로컬 모델 (http://127.0.0.1:11434, 무료).
//! - 작업 기록(최근 30개)과 출력(작업당 최대 200KB)은 메모리에 두고, 접속한 휴대폰에 실시간으로 보낸다.

use crate::app::Shared;
use homepilot_protocol::app::{AgentMsg, AiTask, AiTool};
use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::sync::broadcast;

const MAX_TASKS: usize = 30;
const MAX_OUTPUT: usize = 200 * 1024;
const OLLAMA: &str = "http://127.0.0.1:11434";

pub struct TaskState {
    pub info: AiTask,
    pub output: String,
    cancel: Option<tokio::sync::oneshot::Sender<()>>,
}

pub struct AiManager {
    tasks: Mutex<VecDeque<TaskState>>,
    /// 접속한 휴대폰들에게 보낼 실시간 알림 (작업 출력·상태)
    pub events: broadcast::Sender<AgentMsg>,
}

impl Default for AiManager {
    fn default() -> Self {
        Self { tasks: Mutex::new(VecDeque::new()), events: broadcast::channel(256).0 }
    }
}

fn now() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// Claude Code 실행 파일 찾기 (PATH 의 claude.exe → npm 전역 claude.cmd)
pub fn find_claude() -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        for n in ["claude.exe", "claude.cmd", "claude"] {
            let p = dir.join(n);
            if p.is_file() {
                return Some(p);
            }
        }
    }
    if let Some(a) = dirs::data_dir() {
        let p = a.join("npm").join("claude.cmd");
        if p.is_file() {
            return Some(p);
        }
    }
    None
}

/// Ollama 에 설치된 모델 이름들 (실행 중이 아니면 빈 목록)
fn ollama_models() -> Vec<String> {
    let Ok(r) = ureq::get(&format!("{OLLAMA}/api/tags")).timeout(std::time::Duration::from_secs(2)).call() else { return vec![] };
    let Ok(v) = r.into_json::<serde_json::Value>() else { return vec![] };
    v["models"].as_array().map(|a| a.iter().filter_map(|m| m["name"].as_str().map(str::to_string)).collect()).unwrap_or_default()
}

/// 이 PC 에서 쓸 수 있는 AI 도구
pub fn tools() -> Vec<AiTool> {
    let mut v = vec![match find_claude() {
        Some(p) => AiTool { id: "claude".into(), name: "Claude Code".into(), available: true, note: p.display().to_string() },
        None => AiTool {
            id: "claude".into(),
            name: "Claude Code".into(),
            available: false,
            note: "PC 에 Claude Code 가 설치되어 있지 않습니다 (npm i -g @anthropic-ai/claude-code)".into(),
        },
    }];
    for m in ollama_models() {
        v.push(AiTool {
            id: format!("ollama:{m}"),
            name: format!("Ollama · {m}"),
            available: true,
            note: "이 PC 의 로컬 모델 (무료)".into(),
        });
    }
    v
}

impl AiManager {
    pub fn list(&self) -> Vec<AiTask> {
        self.tasks.lock().unwrap().iter().map(|t| t.info.clone()).collect()
    }

    pub fn output(&self, id: u32) -> Option<String> {
        self.tasks.lock().unwrap().iter().find(|t| t.info.id == id).map(|t| t.output.clone())
    }

    pub fn cancel(&self, id: u32) {
        if let Some(t) = self.tasks.lock().unwrap().iter_mut().find(|t| t.info.id == id) {
            if let Some(c) = t.cancel.take() {
                let _ = c.send(());
            }
        }
    }

    fn append(&self, id: u32, kind: &str, text: &str) {
        {
            let mut ts = self.tasks.lock().unwrap();
            if let Some(t) = ts.iter_mut().find(|t| t.info.id == id) {
                if t.output.len() < MAX_OUTPUT {
                    if !t.output.is_empty() && !t.output.ends_with('\n') && kind != "text" {
                        t.output.push('\n');
                    }
                    if kind == "tool" {
                        t.output.push_str("▶ ");
                    }
                    t.output.push_str(text);
                    if kind == "tool" {
                        t.output.push('\n');
                    }
                }
            }
        }
        let _ = self.events.send(AgentMsg::AiOutput { id, kind: kind.into(), text: text.into() });
    }

    fn finish(&self, shared: &Shared, id: u32, status: &str, summary: &str) {
        let info = {
            let mut ts = self.tasks.lock().unwrap();
            let Some(t) = ts.iter_mut().find(|t| t.info.id == id) else { return };
            t.info.status = status.into();
            t.info.finished = now();
            t.info.summary = summary.chars().take(300).collect();
            t.cancel = None;
            t.info.clone()
        };
        let _ = self.events.send(AgentMsg::AiTaskUpdate { task: info.clone() });
        let title = match status {
            "done" => "AI 작업 완료",
            "cancelled" => "AI 작업 취소됨",
            _ => "AI 작업 실패",
        };
        shared.notify(title, &format!("{} · {}", info.tool_name, info.prompt.chars().take(60).collect::<String>()));
    }

    /// 새 작업 시작. 성공하면 작업 정보.
    pub fn start(
        self: &Arc<Self>,
        shared: Arc<Shared>,
        tool: &str,
        prompt: &str,
        folder: &str,
        allow_edits: bool,
    ) -> Result<AiTask, String> {
        let prompt = prompt.trim();
        if prompt.is_empty() {
            return Err("요청 내용을 입력하세요".into());
        }
        if prompt.len() > 32 * 1024 {
            return Err("요청이 너무 깁니다 (32KB 이하)".into());
        }
        let id = rand::random::<u32>() & 0x7fff_ffff;
        let (tool_name, kind) = if tool == "claude" {
            ("Claude Code".to_string(), Kind::Claude(find_claude().ok_or("PC 에 Claude Code 가 설치되어 있지 않습니다")?))
        } else if let Some(m) = tool.strip_prefix("ollama:") {
            (format!("Ollama · {m}"), Kind::Ollama(m.to_string()))
        } else {
            return Err(format!("알 수 없는 도구: {tool}"));
        };
        let folder = if folder.trim().is_empty() { dirs::home_dir().unwrap_or_default() } else { PathBuf::from(folder.trim()) };
        if matches!(kind, Kind::Claude(_)) && !folder.is_dir() {
            return Err(format!("폴더가 없습니다: {}", folder.display()));
        }
        let (ctx, crx) = tokio::sync::oneshot::channel();
        let info = AiTask {
            id,
            tool: tool.into(),
            tool_name,
            prompt: prompt.chars().take(500).collect(),
            folder: folder.display().to_string(),
            allow_edits: allow_edits && matches!(kind, Kind::Claude(_)),
            status: "running".into(),
            started: now(),
            finished: 0,
            summary: String::new(),
        };
        {
            let mut ts = self.tasks.lock().unwrap();
            ts.push_front(TaskState { info: info.clone(), output: String::new(), cancel: Some(ctx) });
            while ts.len() > MAX_TASKS {
                // 끝난 오래된 작업부터 정리
                if let Some(i) = ts.iter().rposition(|t| t.info.status != "running") {
                    ts.remove(i);
                } else {
                    break;
                }
            }
        }
        let _ = self.events.send(AgentMsg::AiTaskUpdate { task: info.clone() });
        let me = self.clone();
        let p = prompt.to_string();
        let edits = info.allow_edits;
        tokio::spawn(async move {
            let r = tokio::select! {
                r = run(&me, id, kind, &p, &folder, edits) => r,
                _ = crx => Err("cancelled".to_string()),
            };
            match r {
                Ok(summary) => me.finish(&shared, id, "done", &summary),
                Err(e) if e == "cancelled" => me.finish(&shared, id, "cancelled", "휴대폰에서 취소"),
                Err(e) => {
                    me.append(id, "error", &e);
                    me.finish(&shared, id, "failed", &e);
                }
            }
        });
        Ok(info)
    }
}

enum Kind {
    Claude(PathBuf),
    Ollama(String),
}

async fn run(me: &Arc<AiManager>, id: u32, kind: Kind, prompt: &str, folder: &Path, allow_edits: bool) -> Result<String, String> {
    match kind {
        Kind::Claude(exe) => run_claude(me, id, &exe, prompt, folder, allow_edits).await,
        Kind::Ollama(model) => run_ollama(me, id, &model, prompt).await,
    }
}

async fn run_claude(me: &Arc<AiManager>, id: u32, exe: &Path, prompt: &str, folder: &Path, allow_edits: bool) -> Result<String, String> {
    // 명령줄 인수는 모두 고정값. 사용자 글은 표준 입력으로만 전달한다.
    let mut cmd = if exe.extension().is_some_and(|e| e.eq_ignore_ascii_case("cmd")) {
        let mut c = tokio::process::Command::new("cmd.exe");
        c.arg("/d").arg("/c").arg(exe);
        c
    } else {
        tokio::process::Command::new(exe)
    };
    cmd.args(["-p", "--output-format", "stream-json", "--verbose"]);
    if allow_edits {
        cmd.args(["--permission-mode", "acceptEdits"]);
    }
    cmd.current_dir(folder).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).kill_on_drop(true);
    #[cfg(windows)]
    cmd.creation_flags(0x0800_0000); // 콘솔 창 숨김
    let mut child = cmd.spawn().map_err(|e| format!("Claude Code 실행 실패: {e}"))?;
    crate::platform::bind_child_to_agent(&child);
    if let Some(mut stdin) = child.stdin.take() {
        stdin.write_all(prompt.as_bytes()).await.map_err(|e| e.to_string())?;
        drop(stdin); // 입력 끝
    }
    let mut lines = BufReader::new(child.stdout.take().unwrap()).lines();
    let mut result = String::new();
    let mut failed = None;
    while let Ok(Some(line)) = lines.next_line().await {
        let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) else { continue };
        match v["type"].as_str() {
            Some("assistant") => {
                for c in v["message"]["content"].as_array().into_iter().flatten() {
                    match c["type"].as_str() {
                        Some("text") => me.append(id, "text", c["text"].as_str().unwrap_or("")),
                        Some("tool_use") => {
                            let name = c["name"].as_str().unwrap_or("도구");
                            let hint = c["input"]["file_path"]
                                .as_str()
                                .or(c["input"]["command"].as_str())
                                .or(c["input"]["pattern"].as_str())
                                .unwrap_or("");
                            me.append(id, "tool", &format!("{name} {}", hint.chars().take(120).collect::<String>()));
                        }
                        _ => {}
                    }
                }
            }
            Some("result") => {
                result = v["result"].as_str().unwrap_or("").to_string();
                if v["is_error"].as_bool() == Some(true) {
                    failed = Some(if result.contains("/login") || result.contains("Not logged in") {
                        "PC 의 Claude Code 가 로그인되어 있지 않습니다. PC 에서 터미널을 열고 'claude' 를 실행해 로그인하세요.".to_string()
                    } else {
                        result.clone()
                    });
                }
            }
            _ => {}
        }
    }
    let status = child.wait().await.map_err(|e| e.to_string())?;
    if let Some(e) = failed {
        return Err(e);
    }
    if !status.success() && result.is_empty() {
        let mut err = String::new();
        if let Some(mut e) = child.stderr.take() {
            use tokio::io::AsyncReadExt;
            let _ = e.read_to_string(&mut err).await;
        }
        return Err(format!("Claude Code 오류 ({status}): {}", err.chars().take(500).collect::<String>()));
    }
    Ok(result)
}

async fn run_ollama(me: &Arc<AiManager>, id: u32, model: &str, prompt: &str) -> Result<String, String> {
    let (tx, mut rx) = tokio::sync::mpsc::channel::<Result<String, String>>(64);
    let body = serde_json::json!({ "model": model, "prompt": prompt, "stream": true });
    tokio::task::spawn_blocking(move || {
        let r = match ureq::post(&format!("{OLLAMA}/api/generate")).timeout(std::time::Duration::from_secs(1800)).send_json(body) {
            Ok(r) => r,
            Err(e) => {
                let _ = tx.blocking_send(Err(format!("Ollama 에 연결할 수 없습니다 (PC 에서 Ollama 를 실행하세요): {e}")));
                return;
            }
        };
        use std::io::BufRead;
        for line in std::io::BufReader::new(r.into_reader()).lines() {
            let Ok(line) = line else { break };
            let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) else { continue };
            if let Some(t) = v["response"].as_str() {
                if tx.blocking_send(Ok(t.to_string())).is_err() {
                    return; // 취소됨
                }
            }
            if v["done"].as_bool() == Some(true) {
                break;
            }
        }
    });
    let mut all = String::new();
    while let Some(m) = rx.recv().await {
        let t = m?;
        me.append(id, "text", &t);
        all.push_str(&t);
    }
    Ok(all.chars().rev().take(300).collect::<String>().chars().rev().collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_empty_and_unknown() {
        let rt = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
        rt.block_on(async {
            let m = Arc::new(AiManager::default());
            let s = crate::app::tests_support::shared();
            assert!(m.start(s.clone(), "claude", "   ", "", false).is_err());
            assert!(m.start(s.clone(), "gpt", "hi", "", false).is_err());
            assert!(m.start(s, "claude", "hi", "Z:\\없는\\폴더", false).is_err());
        });
    }
}
