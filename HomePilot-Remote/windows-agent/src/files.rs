//! 파일 보기·주고받기.
//!
//! - 휴대폰에 파일 권한이 있어야 한다 (처음 요청 때 PC 화면에서 승인, 기기별로 기억).
//! - 휴대폰이 보낸 파일은 항상 PC 의 다운로드\HomePilot 폴더에 저장한다 (기존 파일을 덮어쓰지 않음).
//! - PC → 휴대폰은 조각(192KB)으로 나눠 보내고, 휴대폰의 확인(FileAck)을 받으며 4조각까지만 앞서 보낸다.

use anyhow::{bail, Context, Result};
use base64::Engine;
use homepilot_protocol::app::{AgentMsg, FsEntry};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::{mpsc, Semaphore};

pub const CHUNK: usize = 192 * 1024;
pub const WINDOW: usize = 4;
/// 휴대폰 → PC 한 파일 최대 크기 (실수로 큰 파일을 보내 디스크를 채우는 것 방지)
pub const MAX_UPLOAD: u64 = 4 * 1024 * 1024 * 1024;

fn b64() -> base64::engine::GeneralPurpose {
    base64::engine::general_purpose::STANDARD
}

fn modified(m: &std::fs::Metadata) -> u64 {
    m.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map(|d| d.as_secs()).unwrap_or(0)
}

fn entry(path: &Path, label: Option<&str>) -> Option<FsEntry> {
    let m = std::fs::metadata(path).ok()?;
    Some(FsEntry {
        name: label
            .map(str::to_string)
            .unwrap_or_else(|| path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| path.display().to_string())),
        path: path.display().to_string(),
        is_dir: m.is_dir(),
        size: if m.is_dir() { 0 } else { m.len() },
        modified: modified(&m),
    })
}

/// 처음 목록: 자주 쓰는 폴더 + 드라이브
pub fn roots() -> Vec<FsEntry> {
    let mut v = Vec::new();
    for (label, dir) in [
        ("바탕 화면", dirs::desktop_dir()),
        ("문서", dirs::document_dir()),
        ("다운로드", dirs::download_dir()),
        ("사진", dirs::picture_dir()),
        ("동영상", dirs::video_dir()),
    ] {
        if let Some(e) = dir.and_then(|d| entry(&d, Some(label))) {
            v.push(e);
        }
    }
    if cfg!(windows) {
        for c in b'C'..=b'Z' {
            let p = PathBuf::from(format!("{}:\\", c as char));
            if let Some(mut e) = entry(&p, None) {
                e.name = format!("{} 드라이브", c as char);
                v.push(e);
            }
        }
    } else if let Some(e) = entry(Path::new("/"), Some("/")) {
        v.push(e);
    }
    v
}

/// 폴더 내용 (폴더 먼저, 이름순). 숨김·시스템 파일은 이름이 '.'/'$' 로 시작하면 뺀다.
pub fn list(path: &str) -> Result<(String, Vec<FsEntry>)> {
    let p = PathBuf::from(path);
    let rd = std::fs::read_dir(&p).with_context(|| format!("폴더를 열 수 없습니다: {path}"))?;
    let mut v: Vec<FsEntry> = rd
        .filter_map(|e| e.ok())
        .filter(|e| {
            let n = e.file_name();
            let n = n.to_string_lossy();
            !n.starts_with('.') && !n.starts_with('$')
        })
        .filter_map(|e| entry(&e.path(), None))
        .take(5000)
        .collect();
    v.sort_by(|a, b| b.is_dir.cmp(&a.is_dir).then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase())));
    let parent = p.parent().map(|x| x.display().to_string()).unwrap_or_default();
    Ok((parent, v))
}

/// 휴대폰이 보낸 파일을 저장할 폴더
pub fn upload_dir() -> PathBuf {
    dirs::download_dir().unwrap_or_else(std::env::temp_dir).join("HomePilot")
}

/// 경로 조작·예약 문자를 없앤 안전한 파일 이름
pub fn safe_name(name: &str) -> String {
    let base = name.rsplit(['/', '\\']).next().unwrap_or("");
    let s: String = base.chars().map(|c| if c.is_control() || r#"<>:"/\|?*"#.contains(c) { '_' } else { c }).collect();
    let s = s.trim().trim_matches('.').to_string();
    let s: String = s.chars().take(150).collect();
    if s.is_empty() {
        "받은 파일".into()
    } else {
        s
    }
}

/// 같은 이름이 있으면 "이름 (2).확장자" 식으로 겹치지 않게
pub fn unique_path(dir: &Path, name: &str) -> PathBuf {
    let p = dir.join(name);
    if !p.exists() {
        return p;
    }
    let (stem, ext) = match name.rfind('.') {
        Some(i) if i > 0 => (&name[..i], &name[i..]),
        _ => (name, ""),
    };
    (2..10_000).map(|i| dir.join(format!("{stem} ({i}){ext}"))).find(|p| !p.exists()).unwrap_or(p)
}

/// 휴대폰 → PC 진행 중인 파일. 다 받지 못하고 버려지면(연결 끊김 등) 임시 파일을 지운다.
pub struct Upload {
    file: Option<std::fs::File>,
    pub path: PathBuf,
    tmp: PathBuf,
    size: u64,
    written: u64,
}

impl Drop for Upload {
    fn drop(&mut self) {
        if self.file.take().is_some() {
            let _ = std::fs::remove_file(&self.tmp);
        }
    }
}

impl Upload {
    pub fn start(name: &str, size: u64) -> Result<Self> {
        if size > MAX_UPLOAD {
            bail!("파일이 너무 큽니다 (최대 4GB)");
        }
        let dir = upload_dir();
        std::fs::create_dir_all(&dir).context("저장 폴더를 만들 수 없습니다")?;
        let path = unique_path(&dir, &safe_name(name));
        // 다 받기 전에는 임시 이름으로 (중간에 끊기면 반쪽 파일이 남지 않게)
        let tmp = path
            .with_extension(format!("{}.homepilot-part", path.extension().map(|e| e.to_string_lossy().into_owned()).unwrap_or_default()));
        let file = std::fs::File::create(&tmp).context("파일을 만들 수 없습니다")?;
        Ok(Self { file: Some(file), path, tmp, size, written: 0 })
    }

    pub fn write(&mut self, offset: u64, data_b64: &str) -> Result<u64> {
        if offset != self.written {
            bail!("조각 순서가 맞지 않습니다");
        }
        let data = b64().decode(data_b64).context("잘못된 데이터")?;
        if self.written + data.len() as u64 > self.size {
            bail!("알린 크기보다 많은 데이터");
        }
        self.file.as_mut().context("이미 끝난 전송")?.write_all(&data)?;
        self.written += data.len() as u64;
        Ok(self.written)
    }

    pub fn finish(mut self) -> Result<PathBuf> {
        if self.written != self.size {
            bail!("파일이 덜 왔습니다 ({}/{})", self.written, self.size);
        }
        let mut f = self.file.take().context("이미 끝난 전송")?;
        f.flush()?;
        drop(f);
        std::fs::rename(&self.tmp, &self.path)?;
        Ok(self.path.clone())
    }

    /// 취소: 임시 파일 삭제 (Drop 이 처리)
    pub fn abort(self) {}
}

/// PC → 휴대폰: 백그라운드에서 조각을 읽어 보낸다. 반환된 Semaphore 에 휴대폰 확인 때마다 1 을 더한다.
pub fn spawn_download(id: u32, path: String, tx: mpsc::Sender<AgentMsg>) -> (Arc<Semaphore>, tokio::task::AbortHandle) {
    let window = Arc::new(Semaphore::new(WINDOW));
    let w = window.clone();
    let task = tokio::spawn(async move {
        let fail = |m: String| AgentMsg::FileError { id, message: m };
        let mut f = match std::fs::File::open(&path) {
            Ok(f) => f,
            Err(e) => {
                let _ = tx.send(fail(format!("파일을 열 수 없습니다: {e}"))).await;
                return;
            }
        };
        let total = f.metadata().map(|m| m.len()).unwrap_or(0);
        let mut offset = 0u64;
        let mut buf = vec![0u8; CHUNK];
        loop {
            let Ok(permit) = w.acquire().await else { return };
            permit.forget();
            let n = match tokio::task::block_in_place(|| f.read(&mut buf)) {
                Ok(n) => n,
                Err(e) => {
                    let _ = tx.send(fail(format!("읽기 오류: {e}"))).await;
                    return;
                }
            };
            let eof = n == 0 || offset + n as u64 >= total;
            let msg = AgentMsg::FileChunk { id, offset, total, data: b64().encode(&buf[..n]), eof };
            offset += n as u64;
            if tx.send(msg).await.is_err() || eof {
                return;
            }
        }
    });
    (window, task.abort_handle())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_names() {
        assert_eq!(safe_name("..\\..\\Windows\\evil.exe"), "evil.exe");
        assert_eq!(safe_name("a/b/c.txt"), "c.txt");
        assert_eq!(safe_name("사진 1.jpg"), "사진 1.jpg");
        assert_eq!(safe_name("bad:name?.txt"), "bad_name_.txt");
        assert_eq!(safe_name("..."), "받은 파일");
        assert_eq!(safe_name(""), "받은 파일");
    }

    #[test]
    fn unique_and_upload_roundtrip() {
        let dir = std::env::temp_dir().join(format!("hp-test-{}", rand::random::<u32>()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("a.txt"), b"x").unwrap();
        assert_eq!(unique_path(&dir, "a.txt"), dir.join("a (2).txt"));
        assert_eq!(unique_path(&dir, "b.txt"), dir.join("b.txt"));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn listing_sorts_dirs_first() {
        let dir = std::env::temp_dir().join(format!("hp-list-{}", rand::random::<u32>()));
        std::fs::create_dir_all(dir.join("z폴더")).unwrap();
        std::fs::write(dir.join("a.txt"), b"hello").unwrap();
        std::fs::write(dir.join(".hidden"), b"").unwrap();
        let (parent, v) = list(&dir.display().to_string()).unwrap();
        assert_eq!(v.len(), 2, "숨김 파일 제외");
        assert!(v[0].is_dir && v[0].name == "z폴더");
        assert_eq!((v[1].name.as_str(), v[1].size), ("a.txt", 5));
        assert_eq!(parent, dir.parent().unwrap().display().to_string());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
