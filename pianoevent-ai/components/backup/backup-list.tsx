'use client'

import { Check, Copy, FolderOpen, HardDriveDownload, RotateCcw } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { describeBackup, type BackupDay } from '@/lib/events/backup'

/**
 * 자동 저장 — 무엇이 언제 떠졌고, 어떻게 되살리는지.
 *
 * 백업은 "있다"는 사실만으로는 쓸모가 없다. 사고가 난 날 **되살릴 수 있어야** 쓸모가 있다.
 * 그래서 목록과 [되살리기] 를 한자리에 둔다. 되살린 것은 늘 **새 행사**로 들어온다 —
 * 지금 것을 덮어쓰면 되살리다 하나를 더 잃으신다.
 */
export function BackupList() {
  const router = useRouter()
  const [days, setDays] = useState<BackupDay[]>([])
  const [folder, setFolder] = useState('백업')
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  /** 탐색기가 안 뜨는 자리도 있다 — 그때 보여 드릴 실제 경로 */
  const [fullPath, setFullPath] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  function load() {
    fetch('/api/backup')
      .then((res) => res.json())
      .then((data) => {
        setDays(data.days ?? [])
        if (data.folder) setFolder(data.folder)
      })
      .catch(() => {
        /* 아직 한 번도 안 떴다 */
      })
      .finally(() => setLoaded(true))
  }

  useEffect(load, [])

  async function backupNow() {
    setBusy('now')
    setMessage(null)
    try {
      const res = await fetch('/api/backup', { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '저장하지 못했습니다.')
      setMessage(
        data.saved > 0
          ? `행사 ${data.saved}개를 ${data.folder} 에 떠 두었습니다.`
          : '떠 둘 행사가 없습니다. 명단이 있는 행사만 뜹니다.',
      )
      load()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '저장하지 못했습니다.')
    } finally {
      setBusy(null)
    }
  }

  async function restore(day: string, name: string) {
    setBusy(`${day}/${name}`)
    setMessage(null)
    try {
      const file = await fetch(`/api/backup?day=${encodeURIComponent(day)}&name=${encodeURIComponent(name)}`, {
        method: 'PUT',
      })
      const got = await file.json()
      if (!file.ok || !got.text) throw new Error(got.error ?? '그 백업을 읽지 못했습니다.')

      const res = await fetch('/api/events/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: got.text }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '되살리지 못했습니다.')
      setMessage(`"${name}" 을(를) 새 행사로 되살렸습니다. 행사 목록에서 여세요.`)
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '되살리지 못했습니다.')
    } finally {
      setBusy(null)
    }
  }

  /** 폴더를 탐색기로 열어 드린다. 못 열면 경로를 보여 드린다 */
  async function openFolder() {
    setBusy('open')
    setMessage(null)
    try {
      const res = await fetch('/api/backup/open', { method: 'POST' })
      const data = await res.json()
      setFullPath(data.folder ?? null)
      setMessage(
        data.opened
          ? '폴더를 열었습니다. 창이 뒤에 떠 있을 수 있습니다.'
          : '이 컴퓨터에서는 폴더를 바로 열 수 없습니다. 아래 경로로 찾아가세요.',
      )
    } catch {
      setMessage('폴더를 열지 못했습니다.')
    } finally {
      setBusy(null)
    }
  }

  async function copyPath() {
    if (!fullPath) return
    try {
      await navigator.clipboard.writeText(fullPath)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* 복사가 막힌 브라우저 — 아래 글을 직접 긁어 복사하시면 된다 */
    }
  }

  return (
    <section className="grid gap-3 rounded-lg border border-border bg-card p-4" data-testid="backup-list">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <HardDriveDownload className="h-4 w-4 text-accent" aria-hidden />
          자동 저장
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          하루에 한 번, 명단이 있는 행사를 <strong className="text-foreground">이 컴퓨터의 {folder} 폴더</strong>에
          알아서 떠 둡니다. 원장님이 하실 일은 없습니다. 열네 날치만 남기고 오래된 것은 지웁니다.{' '}
          <strong className="text-foreground">인터넷으로 나가는 것은 하나도 없습니다.</strong>
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={backupNow} disabled={busy !== null}>
          지금 한 번 떠 두기
        </Button>
        <Button variant="outline" size="sm" onClick={openFolder} disabled={busy !== null} data-testid="backup-open">
          <FolderOpen className="h-4 w-4" aria-hidden />
          폴더 열기
        </Button>
      </div>

      {fullPath && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2">
          <code className="mr-auto break-all text-xs" data-testid="backup-path">
            {fullPath}
          </code>
          <Button variant="ghost" size="sm" onClick={copyPath}>
            {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
            {copied ? '복사했습니다' : '경로 복사'}
          </Button>
        </div>
      )}

      {loaded && days.length === 0 && (
        <p className="text-sm text-muted-foreground">
          아직 떠 둔 것이 없습니다. 명단이 있는 행사가 생기면 하루 안에 저절로 떠집니다.
        </p>
      )}

      {days.length > 0 && (
        <ul className="grid gap-2">
          {days.slice(0, 5).map((day) => (
            <li key={day.day} className="rounded-md border border-border bg-muted/30 p-3">
              <p className="text-sm font-medium">{describeBackup(day)}</p>
              <ul className="mt-1.5 grid gap-1">
                {day.files.map((file) => (
                  <li key={file.name} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="mr-auto truncate">{file.name}</span>
                    <span className="text-xs text-muted-foreground">{Math.max(1, Math.round(file.bytes / 1024))}KB</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => restore(day.day, file.name)}
                      disabled={busy !== null}
                    >
                      <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                      되살리기
                    </Button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {message && <p className="text-sm text-muted-foreground">{message}</p>}

      <p className="text-xs text-muted-foreground">
        되살리면 <strong>늘 새 행사</strong>로 들어옵니다 — 지금 있는 행사를 덮어쓰지 않습니다.
      </p>
    </section>
  )
}
