'use client'

import { Printer } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function PrintButton({ label = '인쇄 · PDF 저장' }: { label?: string }) {
  return (
    <Button onClick={() => window.print()} variant="outline" size="sm" className="no-print">
      <Printer className="h-4 w-4" aria-hidden />
      {label}
    </Button>
  )
}
