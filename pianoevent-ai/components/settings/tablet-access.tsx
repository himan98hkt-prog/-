import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { QrCode } from '@/components/qr-code'
import { lanAddresses, lanOpen, serverPort } from '@/lib/net'

/**
 * 태블릿·휴대폰에서 같은 화면 열기.
 *
 * 당일 진행(순서 넘기기 · 출석 확인)은 **손에 들고 다니는 것**이 훨씬 편하다.
 * 그런데 자료는 학원 컴퓨터 안에 있으므로, 태블릿은 그 컴퓨터를 **같은 공유기에서**
 * 들여다보는 방식이 된다 — 인터넷으로 나가는 것이 아니다.
 *
 * 기본은 **꺼짐**이다. 공유 와이파이에서 늘 열려 있으면 안 되기 때문이다.
 * 켜신 뒤에는 아이 명단이 같은 공유기의 다른 기기에서도 보인다는 것을 분명히 적는다.
 */
export function TabletAccess() {
  const open = lanOpen()
  const addresses = lanAddresses()
  const port = serverPort()
  const url = addresses.length > 0 ? `http://${addresses[0]}:${port}` : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>태블릿 · 휴대폰에서 열기</CardTitle>
        <CardDescription>
          당일 진행과 출석 확인은 태블릿이 훨씬 편합니다. 같은 와이파이에 있으면 이 컴퓨터의 화면을 그대로 엽니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm">
        {!open && (
          <div className="rounded-lg border border-border bg-secondary/40 p-4">
            <p className="font-medium text-foreground">지금은 꺼져 있습니다.</p>
            <p className="mt-1.5 text-muted-foreground">
              프로그램 메뉴에서 <span className="font-medium text-foreground">[연주회 매니저 → 태블릿에서 열기]</span> 를
              누르시고, 프로그램을 닫았다가 다시 열면 켜집니다.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              켜 두면 <span className="font-medium">같은 와이파이에 있는 다른 기기</span>에서도 아이 명단이 보입니다.
              학원 와이파이가 손님과 함께 쓰는 것이라면 행사 날에만 켜 두세요.
            </p>
          </div>
        )}

        {open && url && (
          <div className="grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center">
            <div className="justify-self-center rounded-lg border border-border bg-white p-2 sm:justify-self-start">
              <QrCode path="/events" size={116} href={url} />
            </div>
            <div className="grid gap-1.5">
              <p className="text-muted-foreground">태블릿 카메라로 비추시거나, 주소창에 그대로 치세요.</p>
              <p className="select-all rounded-md border border-border bg-secondary/50 px-3 py-2 font-mono text-base text-foreground">
                {url}
              </p>
              {addresses.length > 1 && (
                <p className="text-xs text-muted-foreground">
                  안 열리면 이 주소도 해 보세요 —{' '}
                  {addresses.slice(1).map((at) => `http://${at}:${port}`).join(' · ')}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                태블릿과 이 컴퓨터가 <span className="font-medium">같은 와이파이</span>에 있어야 합니다.
              </p>
            </div>
          </div>
        )}

        {open && !url && (
          <p className="text-muted-foreground">
            공유기 주소를 찾지 못했습니다. 이 컴퓨터가 와이파이나 인터넷선에 연결돼 있는지 확인해 주세요.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
