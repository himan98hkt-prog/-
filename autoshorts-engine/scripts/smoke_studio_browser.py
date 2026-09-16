"""Real browser: account, projects, factory planning, refresh and paid-job block."""
import secrets
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8765")
        page.get_by_label("이메일", exact=True).fill(f"browser-{secrets.token_hex(5)}@example.com")
        page.get_by_label("비밀번호 · 12자 이상").fill(secrets.token_urlsafe(18))
        page.get_by_role("button", name="가입", exact=True).click()
        page.locator("#account").wait_for(state="visible")
        page.get_by_label("새 프로젝트 이름").fill("통합 스튜디오 테스트")
        page.get_by_role("button", name="프로젝트 만들기", exact=True).click()
        page.wait_for_function("document.querySelector('#message').textContent.includes('프로젝트를 만들었습니다')")
        page.locator("#tab-factory").click()
        page.get_by_label("주제", exact=True).fill("우주에서 소리가 들리지 않는 이유")
        page.get_by_label("직접 작성한 대본").fill("소리는 전달할 매질이 필요합니다.")
        page.get_by_role("button", name="기획 저장", exact=True).click()
        page.wait_for_function("document.querySelector('#message').textContent.includes('기획을 저장')")
        page.reload()
        page.wait_for_function("document.querySelector('#topic').value.includes('우주')")
        page.locator("#tab-factory").click()
        assert page.get_by_label("직접 작성한 대본").input_value() == "소리는 전달할 매질이 필요합니다."
        assert page.get_by_role("button", name="자동 생성 일시중지").is_disabled()
        blocked = page.evaluate("""async () => {
          const response = await fetch('/v1/projects/'+document.querySelector('#projects').value+'/factory-jobs',
            {method:'POST', headers:{Authorization:'Bearer '+sessionStorage.getItem('studio-token')}});
          return response.status;
        }""")
        assert blocked == 409
        page.locator("#tab-analysis").click()
        page.get_by_role("button", name="쇼츠 만들기", exact=True).click()
        page.wait_for_function("document.querySelector('#message').textContent.includes('영상을 선택')")
        page.screenshot(path="studio-browser.png", full_page=True)
        assert not errors, errors
        browser.close()
        print("Studio browser checks passed: account, project, persisted plan, generation block, input guard")


if __name__ == "__main__":
    main()
