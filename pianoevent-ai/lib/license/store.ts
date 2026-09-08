import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { licenseFile } from '@/lib/paths'
import { checkKey, normalizeKey, type LicenseCheck } from '@/lib/license/key'

/**
 * 넣으신 인증키를 이 컴퓨터에 적어 둔다.
 *
 * 한 번 넣으시면 다시 묻지 않는다. 프로그램을 지웠다 다시 까셔도 **학원 자료 폴더**가
 * 남아 있으면 그대로 열린다 — 원장님이 키를 다시 찾으실 일이 없어야 한다.
 * 밖으로 보내는 것은 없다. 이 파일은 그 컴퓨터에만 있다.
 */
export interface StoredLicense {
  key: string
  /** 넣으신 날 */
  activatedAt: string
  /** 누구 것인지 — 문의하실 때 저희가 찾아보는 이름. 밖으로 나가지 않는다 */
  academyName?: string
}

export function readLicense(): StoredLicense | null {
  try {
    const raw = readFileSync(licenseFile(), 'utf8')
    const parsed = JSON.parse(raw) as StoredLicense
    return typeof parsed?.key === 'string' ? parsed : null
  } catch {
    return null
  }
}

export function saveLicense(license: StoredLicense): void {
  const at = licenseFile()
  mkdirSync(dirname(at), { recursive: true })
  writeFileSync(at, `${JSON.stringify(license, null, 2)}\n`, 'utf8')
}

/** 인증을 물어봐야 하는 판인가 — 설치판만 물어본다. 웹 체험판은 그냥 열린다 */
export function licenseRequired(): boolean {
  return process.env.PIANOEVENT_REQUIRE_LICENSE === '1'
}

export interface LicenseStatus extends LicenseCheck {
  required: boolean
  /** 키가 들어 있고 아직 살아 있는가 */
  active: boolean
  academyName?: string
  activatedAt?: string
}

export function licenseStatus(now = new Date()): LicenseStatus {
  const required = licenseRequired()
  const stored = readLicense()
  if (!stored) return { required, active: false, ok: false }
  const check = checkKey(stored.key, now)
  return {
    ...check,
    required,
    active: check.ok,
    academyName: stored.academyName,
    activatedAt: stored.activatedAt,
  }
}

/** 키를 넣는다. 맞으면 적어 두고, 틀리면 왜 틀렸는지 그대로 돌려준다 */
export function activate(key: string, academyName: string | undefined, now = new Date()): LicenseStatus {
  const check = checkKey(key, now)
  if (!check.ok) return { ...check, required: licenseRequired(), active: false }
  saveLicense({
    key: normalizeKey(key),
    activatedAt: now.toISOString(),
    academyName: academyName?.trim() || undefined,
  })
  return { ...check, required: licenseRequired(), active: true, academyName: academyName?.trim() || undefined }
}
