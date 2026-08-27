'use client'

import { Check, Minus, Wifi, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * 이 컴퓨터에서 지금 무엇이 되는가.
 *
 * "AI 키가 있어야 되나요", "인터넷이 끊기면요" 는 구매 전에도 구매 후에도 가장 많이 나오는 질문이다.
 * 답을 설명서에 적어 두는 대신, 원장님 컴퓨터의 실제 상태를 화면에서 보여 준다.
 */
export function SystemCheck({ driver, ai }: { driver: 'demo' | 'supabase'; ai: boolean }) {
  // 인터넷 여부는 브라우저만 안다
  const [online, setOnline] = useState<boolean | null>(null)

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    update()
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])

  const ALWAYS = [
    '학생 명단 등록 · 지난 행사에서 가져오기',
    '곡 사전 78곡 — 작곡가 · 난이도 · 연주시간 자동',
    '연주 순서 자동 배치 · 직접 조정 · 러닝타임 계산',
    '사회자 대본 곡별 생성',
    '순서표 정밀 점검 8가지',
    '인쇄물 32종 × 테마 40종 · 인쇄 · PDF 저장',
    '리허설 소집 시각 · 참가비 · 좌석 배치 계산',
    '학부모 안내 문자 · 리허설 소집 문자 만들기',
    '준비 체크리스트 · 당일 진행표',
    '시즌 특강 커리큘럼 · 활동지',
    '이미지 보관함 (사진 축소도 이 컴퓨터에서)',
  ]

  const NEEDS_NET = [
    { label: '학부모가 초대장 링크를 여는 것', why: '학부모 휴대폰에서 접속해야 하므로' },
    { label: '인쇄물 웹폰트', why: '없으면 바탕·맑은 고딕으로 대체됩니다' },
    { label: '카카오톡 공유 버튼', why: '없으면 링크 복사로 보냅니다' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>이 컴퓨터에서 지금 되는 것</CardTitle>
        <CardDescription>
          AI 키도, 인터넷도, 별도 설정도 필요 없습니다. 아래는 실제 상태입니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-2 sm:grid-cols-3">
          <StatusTile
            label="데이터 저장"
            value={driver === 'supabase' ? '서버 (Supabase)' : '이 컴퓨터'}
            note={driver === 'supabase' ? '여러 기기에서 이어서 씁니다' : '밖으로 나가지 않습니다'}
            good
          />
          <StatusTile
            label="순서표 · 대본 생성"
            value={ai ? 'AI + 규칙 엔진' : '내장 규칙 엔진'}
            note={ai ? 'AI 가 실패하면 규칙 엔진으로 넘어갑니다' : 'AI 키 없이도 전부 만들어집니다'}
            good
          />
          <StatusTile
            label="인터넷"
            value={online === null ? '확인 중' : online ? '연결됨' : '끊김'}
            note={online === false ? '아래 세 가지만 대체 동작합니다' : '전 기능 사용 가능'}
            good={online !== false}
            icon={online === false ? <WifiOff className="h-3.5 w-3.5" /> : <Wifi className="h-3.5 w-3.5" />}
          />
        </div>

        <div>
          <p className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Check className="h-4 w-4 text-accent" aria-hidden />
            인터넷도 AI 키도 없이 되는 것
          </p>
          <ul className="grid gap-1 text-sm text-muted-foreground sm:grid-cols-2">
            {ALWAYS.map((item) => (
              <li key={item} className="flex gap-1.5">
                <span aria-hidden className="text-accent">
                  ·
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Minus className="h-4 w-4 text-muted-foreground" aria-hidden />
            인터넷이 있어야 하는 것 — 이 셋뿐입니다
          </p>
          <ul className="grid gap-1.5 text-sm">
            {NEEDS_NET.map((item) => (
              <li key={item.label} className="flex flex-wrap items-baseline gap-x-2">
                <span>{item.label}</span>
                <span className="text-xs text-muted-foreground">— {item.why}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="rounded-md border border-border bg-secondary px-3 py-2.5 text-sm">
          <strong>정리하면</strong> — 연주회 준비의 모든 결과물은 <strong>이 프로그램 안에서</strong> 만들어집니다.
          AI 키를 넣으면 사회자 멘트의 표현이 조금 더 다양해질 뿐, 없다고 못 만드는 것은 없습니다.
        </p>
      </CardContent>
    </Card>
  )
}

function StatusTile({
  label,
  value,
  note,
  good,
  icon,
}: {
  label: string
  value: string
  note: string
  good: boolean
  icon?: React.ReactNode
}) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 flex items-center gap-1.5 font-medium">
        {icon}
        {value}
        <Badge variant={good ? 'accent' : 'outline'} className="ml-auto text-[10px]">
          {good ? '정상' : '대체 동작'}
        </Badge>
      </p>
      <p className={cn('mt-1 text-[11px]', good ? 'text-muted-foreground' : 'text-foreground')}>{note}</p>
    </div>
  )
}
