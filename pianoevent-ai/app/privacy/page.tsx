import { AppShell } from '@/components/app-shell'
import { currentAcademy } from '@/lib/session'

export const dynamic = 'force-dynamic'
export const metadata = { title: '개인정보처리방침' }

const OPERATOR = process.env.NEXT_PUBLIC_OPERATOR_NAME ?? '(운영자명을 입력하세요)'
const CONTACT = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? '(문의 이메일을 입력하세요)'
const EFFECTIVE = process.env.NEXT_PUBLIC_PRIVACY_EFFECTIVE_DATE ?? '2026-01-01'

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: '1. 수집하는 개인정보 항목',
    body: [
      '가. 원장(서비스 이용자)이 직접 입력하는 정보 — 학원명, 원장 성함, 행사명·일시·장소, 학생 이름, 연주곡, 난이도, 소요시간, 학생 특징 메모.',
      '나. 학부모가 초대장에서 입력하는 정보 — 보호자 성함, 학생 이름, 참석 여부, 참석 인원, 응원 메시지.',
      '다. 서비스 이용 과정에서 자동 생성되는 정보 — 브라우저 세션 식별 쿠키(pe_academy), 접속 로그.',
      '※ 주민등록번호, 계좌정보, 생체정보 등 민감정보는 수집하지 않습니다.',
    ],
  },
  {
    title: '2. 개인정보의 수집·이용 목적',
    body: [
      '가. 연주 순서표 및 사회자 대본 생성, 인쇄물 출력.',
      '나. 모바일 초대장 발행 및 참석 여부·인원 집계.',
      '다. 시즌 특강 수업 계획서 및 활동지 생성.',
      '라. 서비스 오류 대응 및 문의 처리.',
    ],
  },
  {
    title: '3. 개인정보의 보유 및 이용 기간',
    body: [
      '가. 원장이 행사를 삭제하면 해당 행사의 학생 명단과 참석 회신이 즉시 함께 삭제됩니다.',
      '나. 원장이 계정을 삭제하면 학원 정보와 모든 행사·학생·참석 회신이 즉시 영구 삭제됩니다.',
      '다. 프로그램은 하루에 한 번 행사 자료를 원장 컴퓨터의 "백업" 폴더에 자동 저장하며, 열네 날치만 남기고 오래된 것은 자동으로 지웁니다. 이 파일은 원장 컴퓨터를 벗어나지 않으며, 계정 삭제 시 함께 영구 삭제됩니다.',
      '라. 관계 법령에 따라 보존이 필요한 경우 해당 기간 동안만 분리 보관합니다.',
    ],
  },
  {
    title: '4. 개인정보의 처리 위탁',
    body: [
      '가. 데이터 보관 — Supabase Inc. (데이터베이스 및 파일 저장).',
      '나. AI 생성 처리 — Google LLC (Gemini API). 연주 순서·사회자 대본·특강 계획 생성을 위해 학생 이름, 연주곡, 난이도, 소요시간, 특징 메모가 전송됩니다. 학부모 연락처와 참석 회신 정보는 전송하지 않습니다.',
      '다. 서비스 호스팅 — Vercel Inc.',
      '※ 위탁받은 업체가 위탁 목적 외로 개인정보를 이용하지 않도록 계약을 통해 관리·감독합니다.',
    ],
  },
  {
    title: '5. 만 14세 미만 아동의 개인정보',
    body: [
      '가. 본 서비스에 입력되는 학생 정보는 학원 원장이 학부모의 동의를 받아 입력하는 것을 전제로 합니다.',
      '나. 학부모는 언제든지 학원을 통해 자녀 정보의 열람·정정·삭제를 요청할 수 있으며, 요청 시 지체 없이 처리합니다.',
    ],
  },
  {
    title: '6. 이용자의 권리와 행사 방법',
    body: [
      '가. 이용자는 언제든지 앱 내 [설정] 화면에서 저장된 정보를 확인·수정할 수 있습니다.',
      '나. [설정 → 계정 및 모든 데이터 삭제] 에서 계정과 모든 데이터를 직접 즉시 삭제할 수 있습니다.',
      '다. 삭제 요청은 아래 문의처로도 접수할 수 있으며, 접수 후 지체 없이(늦어도 30일 이내) 처리합니다.',
    ],
  },
  {
    title: '7. 개인정보의 파기 절차 및 방법',
    body: [
      '가. 전자적 파일 형태의 정보는 복구가 불가능한 방법으로 영구 삭제합니다.',
      '나. 종이에 출력된 순서표·활동지는 이용 학원에서 분쇄하거나 소각하여 파기합니다.',
    ],
  },
  {
    title: '8. 개인정보 보호를 위한 기술적·관리적 대책',
    body: [
      '가. 모든 통신은 HTTPS 로 암호화됩니다.',
      '나. AI API 키 등 비밀 정보는 서버에만 보관하며 클라이언트 앱 코드에 포함하지 않습니다.',
      '다. 데이터베이스는 학원 단위 행 수준 보안(RLS) 정책으로 다른 학원의 데이터에 접근할 수 없도록 통제합니다.',
    ],
  },
]

export default async function PrivacyPage() {
  const academy = await currentAcademy()

  return (
    <AppShell academyName={academy.name}>
      <article className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-bold tracking-tight">개인정보처리방침</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          PianoEvent AI(이하 &lsquo;서비스&rsquo;)는 이용자의 개인정보를 중요하게 생각하며, 「개인정보 보호법」 등 관련
          법령을 준수합니다.
        </p>

        <div className="mt-6 rounded-md border border-accent/40 bg-accent/5 px-4 py-3 text-sm">
          <p className="font-medium">배포 전 확인</p>
          <p className="mt-1 text-muted-foreground">
            NEXT_PUBLIC_OPERATOR_NAME · NEXT_PUBLIC_CONTACT_EMAIL · NEXT_PUBLIC_PRIVACY_EFFECTIVE_DATE 환경변수를
            채우면 아래 항목이 자동으로 반영됩니다. 이 URL 을 Google Play Console 의 개인정보처리방침 주소로
            등록하세요.
          </p>
        </div>

        <div className="mt-8 space-y-8">
          {SECTIONS.map((section) => (
            <section key={section.title}>
              <h2 className="text-base font-semibold">{section.title}</h2>
              <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-muted-foreground">
                {section.body.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          ))}

          <section>
            <h2 className="text-base font-semibold">9. 개인정보 보호책임자 및 문의처</h2>
            <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-muted-foreground">
              <li>운영자 · {OPERATOR}</li>
              <li>문의 · {CONTACT}</li>
              <li>삭제 요청 · 앱 내 [설정 → 계정 및 모든 데이터 삭제] 또는 위 이메일</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold">10. 방침의 변경</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              본 방침은 {EFFECTIVE} 부터 적용됩니다. 내용이 변경될 경우 변경 사항을 서비스 화면에 공지하며, 중요한
              변경은 최소 7일 전에 알립니다.
            </p>
          </section>
        </div>
      </article>
    </AppShell>
  )
}
