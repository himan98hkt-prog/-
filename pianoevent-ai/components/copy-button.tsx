'use client'

import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export function CopyButton({
  text,
  label = '복사',
  variant = 'outline',
}: {
  text: string
  label?: string
  variant?: 'outline' | 'ghost' | 'default' | 'accent'
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // clipboard 권한이 없는 브라우저(구형 iOS 등) 폴백
      const area = document.createElement('textarea')
      area.value = text
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      document.body.removeChild(area)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <Button onClick={copy} variant={variant} size="sm" className="no-print">
      {copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
      {copied ? '복사됨' : label}
    </Button>
  )
}
