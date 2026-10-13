//! CPU·RAM·GPU·디스크 사용률을 2초마다 측정해 캐시한다.

use crate::platform::GpuSampler;
use homepilot_protocol::app::{DiskStatus, SystemStatus};
use std::sync::{Arc, RwLock};
use std::time::Duration;

pub fn spawn_collector(out: Arc<RwLock<SystemStatus>>) {
    std::thread::Builder::new()
        .name("metrics".into())
        .spawn(move || {
            let mut sys = sysinfo::System::new();
            let mut disks = sysinfo::Disks::new_with_refreshed_list();
            let mut gpu = GpuSampler::new();
            let hostname = sysinfo::System::host_name().unwrap_or_default();
            let os = sysinfo::System::long_os_version().unwrap_or_else(|| std::env::consts::OS.into());
            let mut n: u64 = 0;
            loop {
                sys.refresh_cpu_usage();
                sys.refresh_memory();
                if n.is_multiple_of(15) {
                    disks.refresh_list();
                } else {
                    disks.refresh();
                }
                let s = SystemStatus {
                    hostname: hostname.clone(),
                    os: os.clone(),
                    uptime_secs: sysinfo::System::uptime(),
                    cpu_percent: sys.global_cpu_usage(),
                    mem_total_bytes: sys.total_memory(),
                    mem_used_bytes: sys.used_memory(),
                    gpu_percent: gpu.sample(),
                    disks: disks
                        .list()
                        .iter()
                        .filter(|d| d.total_space() > 0)
                        .map(|d| DiskStatus {
                            mount: d.mount_point().display().to_string(),
                            total_bytes: d.total_space(),
                            available_bytes: d.available_space(),
                        })
                        .collect(),
                    active_sessions: 0,
                };
                if let Ok(mut w) = out.write() {
                    *w = s;
                }
                n += 1;
                std::thread::sleep(Duration::from_secs(2));
            }
        })
        .expect("metrics 스레드 시작 실패");
}
