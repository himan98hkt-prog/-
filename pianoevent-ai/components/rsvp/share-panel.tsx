'use client'

import { Link2, MessageCircle, Share2 } from 'lucide-react'
import Script from 'next/script'
import { useEffect, useState } from 'react'
import { CopyButton } from '@/components/copy-button'
import { Button } from '@/components/ui/button'

interface KakaoSdk {
  isInitialized: () => boolean
  init: (key: string) => void
  Share: { sendDefault: (options: Record<string, unknown>) => void }
}

declare global {
  interface Window {
    Kakao?: KakaoSdk
  }
}

/**
 * 초대장 공유.
 * 카카오 JS 키가 있으면 카카오톡 공유 SDK 를, 없으면 Web Share API → 링크 복사 순으로 내려간다.
 */
export function SharePanel({
  path,
  title,
  description,
}: {
  path: string
  title: string
  description: string
}) {
  const kakaoKey = process.env.NEXT_PUBLIC_KAKAO_JS_KEY
  const [url, setUrl] = useState(path)
  const [kakaoReady, setKakaoReady] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    setUrl(`${window.location.origin}${path}`)
  }, [path])

  function initKakao() {
    if (!kakaoKey || !window.Kakao) return
    if (!window.Kakao.isInitialized()) window.Kakao.init(kakaoKey)
    setKakaoReady(true)
  }

  async function share() {
    if (kakaoReady && window.Kakao) {
      window.Kakao.Share.sendDefault({
        objectType: 'text',
        text: `${title}\n${description}`,
        link: { mobileWebUrl: url, webUrl: url },
      })
      return
    }
    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({ title, text: description, url })
        return
      } catch {
        // 사용자가 공유 시트를 닫은 경우 — 조용히 넘어간다
        return
      }
    }
    await navigator.clipboard.writeText(url)
    setNotice('링크를 복사했습니다. 카카오톡 대화창에 붙여넣어 보내세요.')
  }

  const messageText = `[${title}]\n${description}\n\n참석 여부를 아래 링크에서 알려 주세요.\n${url}`

  return (
    <div className="grid gap-3">
      {kakaoKey && (
        <Script src="https://t1.kakaocdn.net/kakao_js_sdk/2.7.2/kakao.min.js" onLoad={initKakao} strategy="lazyOnload" />
      )}

      <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2">
        <Link2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <code className="min-w-0 flex-1 truncate text-xs">{url}</code>
        <CopyButton text={url} label="링크 복사" variant="ghost" />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={share}>
          {kakaoReady ? <MessageCircle className="h-4 w-4" aria-hidden /> : <Share2 className="h-4 w-4" aria-hidden />}
          {kakaoReady ? '카카오톡으로 공유' : '초대장 공유'}
        </Button>
        <CopyButton text={messageText} label="안내 문구 통째로 복사" />
      </div>

      {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
      {!kakaoKey && (
        <p className="text-xs text-muted-foreground">
          NEXT_PUBLIC_KAKAO_JS_KEY 를 설정하면 카카오톡 공유 버튼이 켜집니다. 지금은 링크 복사·기기 공유로 동작합니다.
        </p>
      )}
    </div>
  )
}
