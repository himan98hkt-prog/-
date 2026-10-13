fn main() {
    // 실행 파일 아이콘 (탐색기·작업 표시줄·설치 프로그램 바로가기에 보임)
    println!("cargo:rerun-if-changed=assets/homepilot.rc");
    println!("cargo:rerun-if-changed=assets/homepilot.ico");
    embed_resource::compile("assets/homepilot.rc", embed_resource::NONE).manifest_optional().unwrap();
}
