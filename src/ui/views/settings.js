// 설정 탭 — 브랜딩 / 학습항목(custom) / 과목·강사 / 알림 템플릿 / 라이선스 / 백업·복원 / 개발자 도구

import { h, clear, toast, modal, field, confirmDialog, copyText } from '../dom.js'
import { branding, saveBranding, resizeImage, logoDataUrl, updateManifest } from '../branding.js'
import { FIELD_TYPES, PRESETS, validateField } from '../../core/customfields.js'
import { DEFAULT_TEMPLATES, TEMPLATE_VARS, unknownVars } from '../../core/templates.js'
import { formatKey, PRODUCTS } from '../../core/license.js'
import { entitlement, activateWithKey, deviceCode } from '../activation.js'
import { buildBackup, parseBackup, BACKUP_TABLES } from '../../core/backup.js'
import { ROLES } from '../../core/perm.js'
import { db } from '../../data/db.js'
import { restoreFromBackup } from '../../data/restore.js'
import { downloadCsv } from '../../core/csv.js'
import { toYmd, toMonth, addMonths, daysBetween } from '../../core/date.js'

export async function render(root, ctx) {
  const { repo, user } = ctx
  const isOwner = (user?.role || 'owner') === 'owner'

  const sections = [
    section('브랜딩 (학원명 · 로고 · 색상)', brandingSection(repo), true),
    section('학습 항목 (계열별 custom 필드)', customFieldSection(repo)),
    section('과목 · 반 · 강사', peopleSection(repo, isOwner)),
    section('알림 문구 템플릿', templateSection(repo)),
    section('수납 정책 (납부일 · 형제 할인)', billingSection(repo)),
    section('인증키 · 플랜', licenseSection(repo)),
    section('백업 · 복원 · 내보내기', backupSection(repo)),
    repo.getPlan() === 'pro' ? section('Pro 동기화 (Supabase)', proSection(repo)) : null,
    section('개발자 · 데모 도구', devSection(repo))
  ].filter(Boolean)
  root.append(...sections)
  return () => {}
}

function section(title, body, open = false) {
  return h('details', { class: 'card', open, style: { marginBottom: '12px' } },
    h('summary', { style: { cursor: 'pointer', fontWeight: '700' } }, title),
    h('div', { style: { marginTop: '12px' } }, body))
}

// ── 브랜딩 ──────────────────────────────────────────────────
function brandingSection(repo) {
  const b = branding()
  const name = h('input', { type: 'text', value: b.name })
  const phone = h('input', { type: 'tel', value: b.phone || '' })
  const color = h('input', { type: 'color', value: b.brand_color, style: { height: '42px', padding: '2px' } })
  const preview = h('img', { src: logoDataUrl(192), style: { width: '72px', height: '72px', borderRadius: '18px', objectFit: 'cover' }, alt: '로고' })
  const file = h('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp' })

  file.addEventListener('change', async () => {
    const f = file.files?.[0]
    if (!f) return
    try {
      const dataUrl = await resizeImage(f, 256)
      await saveBranding({ logo: dataUrl })
      preview.src = dataUrl
      toast('로고를 저장했습니다', 'ok')
    } catch (err) {
      toast(err.message, 'error')
    }
  })

  return h('div', {},
    h('div', { class: 'row', style: { marginBottom: '12px' } }, preview,
      h('div', { class: 'grow' }, file,
        h('div', { class: 'small muted' }, '미업로드 시 학원명 이니셜 아바타가 사용됩니다'),
        b.logo ? h('button', {
          class: 'btn sm', style: { marginTop: '6px' }, onClick: async () => {
            await saveBranding({ logo: null })
            preview.src = logoDataUrl(192)
            toast('로고를 삭제했습니다')
          }
        }, '로고 삭제') : null)),
    h('div', { class: 'inline-fields' }, field('학원명', name), field('대표 연락처', phone), field('브랜드 컬러', color)),
    h('div', { class: 'row' },
      h('button', {
        class: 'btn primary', onClick: async () => {
          await saveBranding({ name: name.value.trim() || '학원 관리노트', phone: phone.value.trim(), brand_color: color.value })
          toast('브랜딩을 적용했습니다', 'ok')
        }
      }, '적용'),
      h('button', {
        class: 'btn', onClick: () => {
          const ok = updateManifest()
          toast(ok ? '설치 아이콘(manifest)을 갱신했습니다' : '이 브라우저는 동적 아이콘을 지원하지 않아 기본 아이콘을 사용합니다')
        }
      }, '설치 아이콘 갱신')
    ),
    h('p', { class: 'small muted' }, '학원명·로고·컬러는 앱 헤더, 리포트카드, 로그인 화면, 홈 화면 설치 아이콘에 함께 반영됩니다.')
  )
}

// ── custom 필드 ─────────────────────────────────────────────
function customFieldSection(repo) {
  const listBox = h('div')
  const presetRow = h('div', { class: 'row wrap' })

  const paint = () => {
    const fields = repo.getSetting('customFields', [])
    clear(listBox)
    if (!fields.length) listBox.append(h('p', { class: 'muted small' }, '아직 항목이 없습니다. 아래 프리셋으로 시작해 보세요.'))
    fields.forEach((f, i) => {
      listBox.append(h('div', { class: 'row', style: { padding: '8px 0', borderBottom: '1px solid var(--line)' } },
        h('div', { class: 'grow' },
          h('b', {}, f.label), h('span', { class: 'muted small' }, ` (${f.key} · ${FIELD_TYPES.find((t) => t.type === f.type)?.label || f.type})`),
          f.options?.length ? h('div', { class: 'small muted' }, f.options.join(' / ')) : null),
        h('label', { class: 'row small', style: { gap: '4px' } }, h('input', {
          type: 'checkbox', checked: !!f.onCard, style: { width: 'auto' },
          onChange: async (e) => { fields[i].onCard = e.target.checked; await repo.setSetting('customFields', fields) }
        }), '카드'),
        h('label', { class: 'row small', style: { gap: '4px' } }, h('input', {
          type: 'checkbox', checked: !!f.onReport, style: { width: 'auto' },
          onChange: async (e) => { fields[i].onReport = e.target.checked; await repo.setSetting('customFields', fields) }
        }), '리포트'),
        h('button', {
          class: 'btn sm danger', onClick: async () => {
            if (!await confirmDialog(`'${f.label}' 항목을 삭제할까요? 이미 입력된 값은 원생 데이터에 남습니다.`, { danger: true, okLabel: '삭제' })) return
            await repo.setSetting('customFields', fields.filter((x) => x.key !== f.key))
            paint()
          }
        }, '삭제')
      ))
    })
    clear(presetRow)
    for (const [key, preset] of Object.entries(PRESETS)) {
      presetRow.append(h('button', {
        class: 'chip', onClick: async () => {
          const cur = repo.getSetting('customFields', [])
          const merged = [...cur]
          for (const f of preset) if (!merged.some((x) => x.key === f.key)) merged.push({ ...f })
          await repo.setSetting('customFields', merged)
          paint()
          toast(`${key} 프리셋을 추가했습니다`, 'ok')
        }
      }, `${key} 프리셋`))
    }
  }
  paint()

  const addBtn = h('button', {
    class: 'btn primary', onClick: () => {
      const label = h('input', { type: 'text', placeholder: '예) 띠 급수' })
      const key = h('input', { type: 'text', placeholder: '예) belt' })
      const type = h('select', {}, ...FIELD_TYPES.map((t) => h('option', { value: t.type }, t.label)))
      const options = h('input', { type: 'text', placeholder: '선택 목록일 때만: 흰띠, 노란띠, 파란띠' })
      modal({
        title: '학습 항목 추가',
        body: h('div', {},
          field('항목 이름', label), field('저장 키(영문)', key, '한 번 정하면 바꾸지 마세요. 데이터가 이 키로 저장됩니다'),
          field('종류', type), field('선택지', options, '쉼표로 구분')),
        actions: [{
          label: '추가', kind: 'primary', keepOpen: true, onClick: async (close) => {
            const fields = repo.getSetting('customFields', [])
            const f = {
              key: key.value.trim(), label: label.value.trim(), type: type.value,
              options: options.value.split(',').map((s) => s.trim()).filter(Boolean),
              onCard: true, onReport: true
            }
            const errors = validateField(f, fields)
            if (errors.length) { toast(errors[0], 'error'); return false }
            await repo.setSetting('customFields', [...fields, f])
            paint()
            close()
          }
        }]
      })
    }
  }, '+ 항목 추가')

  return h('div', {}, listBox,
    h('div', { class: 'row wrap', style: { marginTop: '12px' } }, addBtn, presetRow),
    h('p', { class: 'small muted' }, '여기서 만든 항목이 원생 카드와 학부모 리포트에 자동으로 나타납니다. 계열이 달라도 이 항목만 바꾸면 그대로 운영할 수 있습니다.'))
}

// ── 과목/강사 ───────────────────────────────────────────────
function peopleSection(repo, isOwner) {
  const subjBox = h('div')
  const userBox = h('div')

  const paint = () => {
    clear(subjBox)
    for (const s of repo.cache.subjects) {
      subjBox.append(h('div', { class: 'row', style: { padding: '6px 0' } },
        h('span', { style: { width: '14px', height: '14px', borderRadius: '4px', background: s.color, display: 'inline-block' } }),
        h('span', { class: 'grow' }, s.name),
        isOwner ? h('button', { class: 'btn sm', onClick: () => editSubject(s) }, '수정') : null))
    }
    if (!repo.cache.subjects.length) subjBox.append(h('p', { class: 'muted small' }, '과목이 없습니다'))

    clear(userBox)
    for (const u of repo.cache.users) {
      userBox.append(h('div', { class: 'row', style: { padding: '6px 0' } },
        h('span', { class: 'grow' }, u.name, h('span', { class: 'badge', style: { marginLeft: '6px' } }, ROLES[u.role]?.label || u.role)),
        h('span', { class: 'muted small' }, `PIN ${String(u.pin || '').replace(/./g, '•')}`),
        isOwner ? h('button', { class: 'btn sm', onClick: () => editUser(u) }, '수정') : null))
    }
  }

  function editSubject(subject = null) {
    const name = h('input', { type: 'text', value: subject?.name || '' })
    const color = h('input', { type: 'color', value: subject?.color || '#2563eb', style: { height: '42px' } })
    modal({
      title: subject ? '과목 수정' : '과목 추가',
      body: h('div', { class: 'inline-fields' }, field('과목명', name), field('색상', color, '출결 보드와 시간표에 이 색이 쓰입니다')),
      actions: [
        subject ? {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (!await confirmDialog('이 과목을 삭제할까요?', { danger: true, okLabel: '삭제' })) return false
            await repo.remove('subjects', subject.id); paint(); close()
          }
        } : null,
        {
          label: '저장', kind: 'primary', onClick: async () => {
            if (!name.value.trim()) return toast('과목명을 입력해 주세요', 'error')
            await repo.put('subjects', { ...(subject || {}), name: name.value.trim(), color: color.value })
            paint()
          }
        }
      ].filter(Boolean)
    })
  }

  function editUser(u = null) {
    const name = h('input', { type: 'text', value: u?.name || '' })
    const role = h('select', {}, ...Object.entries(ROLES).map(([k, v]) => h('option', { value: k, selected: u?.role === k }, `${v.label} — ${v.desc}`)))
    const pin = h('input', { type: 'text', value: u?.pin || '', maxLength: 4, inputMode: 'numeric' })
    modal({
      title: u ? '계정 수정' : '계정 추가',
      body: h('div', { class: 'inline-fields' }, field('이름', name), field('권한', role), field('PIN 4자리', pin)),
      actions: [
        u ? {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (repo.cache.users.length <= 1) { toast('마지막 계정은 삭제할 수 없습니다', 'error'); return false }
            if (!await confirmDialog('이 계정을 삭제할까요?', { danger: true, okLabel: '삭제' })) return false
            await repo.remove('users', u.id); paint(); close()
          }
        } : null,
        {
          label: '저장', kind: 'primary', keepOpen: true, onClick: async (close) => {
            if (!/^\d{4}$/.test(pin.value)) { toast('PIN 은 숫자 4자리입니다', 'error'); return false }
            const dup = repo.cache.users.find((x) => x.pin === pin.value && x.id !== u?.id)
            if (dup) { toast('이미 쓰는 PIN 입니다', 'error'); return false }
            await repo.put('users', { ...(u || {}), name: name.value.trim() || '강사', role: role.value, pin: pin.value })
            paint(); close()
          }
        }
      ].filter(Boolean)
    })
  }

  paint()
  return h('div', {},
    h('div', { class: 'card-title' }, '과목'), subjBox,
    isOwner ? h('button', { class: 'btn sm', onClick: () => editSubject() }, '+ 과목 추가') : null,
    h('div', { class: 'card-title', style: { marginTop: '16px' } }, '계정 (PIN 로그인)'), userBox,
    isOwner ? h('button', { class: 'btn sm', onClick: () => editUser() }, '+ 계정 추가') : null,
    h('p', { class: 'small muted' }, '반 관리는 시간표 탭에서 합니다.'))
}

// ── 알림 템플릿 ─────────────────────────────────────────────
function templateSection(repo) {
  const box = h('div')
  const paint = () => {
    const templates = repo.getSetting('templates', DEFAULT_TEMPLATES)
    clear(box)
    templates.forEach((t, i) => {
      const body = h('textarea', { value: t.body })
      box.append(h('div', { style: { marginBottom: '14px' } },
        h('div', { class: 'row' }, h('b', { class: 'grow' }, t.name),
          h('button', {
            class: 'btn sm', onClick: async () => {
              const bad = unknownVars(body.value)
              if (bad.length) return toast(`정의되지 않은 변수: ${bad.join(' ')}`, 'error')
              const next = templates.slice()
              next[i] = { ...t, body: body.value }
              await repo.setSetting('templates', next)
              toast('저장했습니다', 'ok')
            }
          }, '저장')),
        body))
    })
  }
  paint()
  return h('div', {}, box,
    h('div', { class: 'row wrap small muted' }, '사용 가능한 변수: ',
      ...TEMPLATE_VARS.map((v) => h('span', { class: 'chip', onClick: () => copyText(v.key).then(() => toast(`${v.key} 복사`)) }, `${v.key} ${v.desc}`))),
    h('div', { class: 'row', style: { marginTop: '10px' } },
      h('button', {
        class: 'btn sm', onClick: async () => { await repo.setSetting('templates', DEFAULT_TEMPLATES); paint(); toast('기본 문구로 되돌렸습니다') }
      }, '기본값 복원')))
}

// ── 인증키(시디키) ──────────────────────────────────────────
function licenseSection(repo) {
  const box = h('div')

  const paint = () => {
    const ent = entitlement()
    const lic = repo.getSetting('license')
    const input = h('input', { type: 'text', placeholder: 'AAAA-AAAA-AAAA', value: lic?.key || '' })
    input.addEventListener('input', () => { input.value = formatKey(input.value).slice(0, 14) })
    const nameInput = h('input', {
      type: 'text', placeholder: '피아노 관리노트에서 학원명으로 받은 키일 때만',
      value: lic?.academy_name || ''
    })

    clear(box)
    box.append(
      ent.mode === 'licensed'
        ? h('div', {},
          h('span', { class: 'badge ok' }, `${lic.plan === 'pro' ? 'Pro' : 'Lite'} 인증됨`),
          h('div', { class: 'small muted', style: { marginTop: '6px' } },
            `키 ${lic.key} · ${lic.scheme === 'piano' ? '피아노 관리노트 발급분' : (PRODUCTS[lic.product]?.label || '통합')} · 인증일 ${(lic.activated_at || '').slice(0, 10)} · 기기번호 ${lic.device || deviceCode()}`))
        : h('span', { class: 'badge warn' },
          ent.mode === 'trial' ? `체험 ${ent.daysLeft}일 남음 — 인증키를 넣으면 계속 사용합니다` : '미인증'),

      h('div', { class: 'row', style: { marginTop: '10px' } },
        h('div', { class: 'grow' }, input),
        h('button', {
          class: 'btn primary', onClick: async () => {
            const res = await activateWithKey(input.value, { academyName: nameInput.value })
            if (!res.ok) return toast(res.reason, 'error')
            toast(`${res.plan === 'pro' ? 'Pro' : 'Lite'} 인증 완료. 앱을 새로고침합니다`, 'ok')
            setTimeout(() => location.reload(), 800)
          }
        }, lic ? '키 교체' : '인증')),

      h('div', { style: { marginTop: '8px' } }, nameInput),
      h('p', { class: 'small muted' },
        'Lite 키(두 번째 자리 L)는 기기 1대, Pro 키(P)는 여러 기기 동시 사용과 실시간 동기화를 지원합니다. ',
        '첫 자리가 A인 통합키와 ', h('b', {}, '피아노 관리노트에서 발급받은 키'), '는 두 제품에서 모두 열립니다. ',
        '피아노 쪽에서 학원명으로 받은 키라면 위 칸에 그 학원명을 넣어 주세요.'),

      h('div', { class: 'row small muted' },
        h('span', { class: 'grow' }, `이 기기 번호: ${deviceCode()} (재발급·문의 시 사용)`),
        h('button', { class: 'linkbtn', onClick: () => copyText(deviceCode()).then(() => toast('복사했습니다')) }, '복사')),

      lic
        ? h('div', { style: { marginTop: '10px' } },
          h('button', {
            class: 'btn sm danger', onClick: async () => {
              if (!await confirmDialog('이 기기에서 인증을 해제합니다. 자료는 지워지지 않습니다.', { title: '인증 해제', okLabel: '해제', danger: true })) return
              await repo.setSetting('license', null)
              toast('인증을 해제했습니다')
              setTimeout(() => location.reload(), 600)
            }
          }, '이 기기 인증 해제'))
        : null
    )
  }
  paint()
  return box
}

// ── 수납 정책 ───────────────────────────────────────────────
// 매달 계산기로 두드리던 형제 할인·절사 규칙을 한 번만 정해 두면 청구 생성이 알아서 계산한다.
function billingSection(repo) {
  const p = repo.policy()
  const dueDay = h('input', { type: 'number', min: '1', max: '28', value: p.dueDay })
  const roundUnit = h('select', {}, ...[1, 100, 1000].map((u) =>
    h('option', { value: String(u), selected: p.roundUnit === u }, u === 1 ? '절사 없음' : `${u.toLocaleString('ko-KR')}원 단위 절사`)))
  const sibOn = h('input', { type: 'checkbox', checked: p.sibling.enabled, style: { width: 'auto' } })
  const sibValue = h('input', { type: 'number', min: '0', value: p.sibling.value })
  const sibType = h('select', {},
    h('option', { value: 'percent', selected: p.sibling.type === 'percent' }, '%'),
    h('option', { value: 'amount', selected: p.sibling.type === 'amount' }, '원'))
  const sibApply = h('select', {},
    h('option', { value: 'all', selected: p.sibling.applyTo === 'all' }, '형제 전원'),
    h('option', { value: 'others', selected: p.sibling.applyTo === 'others' }, '첫째 제외(둘째부터)'))

  return h('div', {},
    h('div', { class: 'inline-fields' },
      field('납부 기준일', dueDay, '이 날이 지나면 오늘 할 일에 미납 독촉이 뜹니다'),
      field('청구액 절사', roundUnit)),
    h('div', { class: 'card', style: { marginTop: '10px' } },
      h('label', { class: 'row', style: { gap: '8px' } }, sibOn, h('b', {}, '형제·자매 할인 자동 적용')),
      h('div', { class: 'inline-fields', style: { marginTop: '8px' } },
        field('할인', h('div', { class: 'row' }, h('div', { class: 'grow' }, sibValue), sibType)),
        field('적용 대상', sibApply)),
      h('p', { class: 'small muted' }, '학부모 연락처가 같으면 형제로 자동 인식됩니다(원생 탭 기준).')),
    h('div', { class: 'row', style: { marginTop: '10px' } },
      h('button', {
        class: 'btn primary', onClick: async () => {
          await repo.setSetting('billing', {
            dueDay: Math.min(28, Math.max(1, Number(dueDay.value) || 10)),
            roundUnit: Number(roundUnit.value) || 1,
            sibling: {
              enabled: sibOn.checked,
              type: sibType.value,
              value: Number(sibValue.value) || 0,
              applyTo: sibApply.value
            }
          })
          toast('수납 정책을 저장했습니다', 'ok')
        }
      }, '저장')))
}

// ── 백업/복원 ───────────────────────────────────────────────
function backupSection(repo) {
  const fileInput = h('input', { type: 'file', accept: 'application/json' })

  fileInput.addEventListener('change', async () => {
    const f = fileInput.files?.[0]
    if (!f) return
    try {
      const backup = parseBackup(await f.text())
      const counts = Object.entries(backup.counts || {}).filter(([, v]) => v).map(([k, v]) => `${k} ${v}`).join(', ')
      if (!await confirmDialog(`현재 데이터를 모두 지우고 복원합니다.\n\n${counts}`, { title: '백업 복원', okLabel: '복원', danger: true })) return
      await restoreFromBackup(backup)
      toast('복원했습니다. 앱을 새로고침합니다', 'ok')
      setTimeout(() => location.reload(), 800)
    } catch (err) {
      toast(err.message, 'error')
    }
  })

  const lastLine = h('div', { class: 'small muted' }, lastBackupText(repo))

  return h('div', {},
    lastLine,
    h('div', { class: 'row wrap', style: { marginTop: '8px' } },
      h('button', {
        class: 'btn primary', onClick: async () => {
          const tables = {}
          for (const t of BACKUP_TABLES) tables[t] = db[t] ? await db[t].toArray() : []
          const backup = buildBackup(tables, { plan: repo.getPlan(), academy: branding().name })
          const blob = new Blob([JSON.stringify(backup)], { type: 'application/json' })
          const a = h('a', { href: URL.createObjectURL(blob), download: `${branding().name}_백업_${new Date().toISOString().slice(0, 10)}.json` })
          a.click()
          setTimeout(() => URL.revokeObjectURL(a.href), 4000)
          await repo.setSetting('lastBackupAt', new Date().toISOString())
          lastLine.textContent = lastBackupText(repo)
          toast('백업 파일을 저장했습니다', 'ok')
        }
      }, '백업 파일 내려받기'),
      h('div', { class: 'grow' }, fileInput)),
    h('p', { class: 'small muted' }, '이 백업 파일은 Pro 전환 시 그대로 업로드해 마이그레이션할 수 있습니다.'),
    h('div', { class: 'card-title', style: { marginTop: '12px' } }, '엑셀(CSV) 내보내기'),
    h('div', { class: 'row wrap' },
      h('button', { class: 'btn sm', onClick: () => exportStudentsCsv(repo) }, '원생 명단'),
      h('button', { class: 'btn sm', onClick: () => exportPaymentsCsv(repo) }, '수납 내역(12개월)'),
      h('button', { class: 'btn sm', onClick: () => exportAttendanceCsv(repo) }, '출결 기록(3개월)')),
    h('p', { class: 'small muted' }, '세무·회계 정리나 다른 프로그램으로 옮길 때 사용하세요. 엑셀에서 바로 열립니다.'))
}

function lastBackupText(repo) {
  const at = repo.getSetting('lastBackupAt')
  if (!at) return '아직 백업한 적이 없습니다. 자료는 이 기기에만 있습니다.'
  const days = daysBetween(String(at).slice(0, 10), toYmd())
  return `마지막 백업 ${String(at).slice(0, 10)} (${days === 0 ? '오늘' : `${days}일 전`})`
}

async function exportStudentsCsv(repo) {
  const rows = repo.cache.students.map((s) => [
    s.name, s.status, s.school || '', s.grade || '',
    repo.studentClasses(s.id).map((c) => c.name).join(' '),
    s.phone || '', s.parent_phone || '', s.joined_at || '', s.memo || ''
  ])
  downloadCsv(`원생명단_${toYmd()}.csv`, ['이름', '상태', '학교', '학년', '반', '학생연락처', '학부모연락처', '등록일', '메모'], rows)
  toast(`원생 ${rows.length}명을 저장했습니다`, 'ok')
}

async function exportPaymentsCsv(repo) {
  const months = Array.from({ length: 12 }, (_, i) => addMonths(toMonth(toYmd()), -i))
  const rows = []
  for (const m of months) {
    for (const p of await repo.paymentsOfMonth(m)) {
      const st = repo.cache.studentById.get(p.student_id)
      rows.push([m, st?.name || '(삭제)', p.base_amount ?? p.amount, p.discount || 0, p.amount, p.paid, p.remaining, p.status, p.method || '', p.paid_at || ''])
    }
  }
  downloadCsv(`수납내역_${toYmd()}.csv`, ['월', '원생', '기본', '할인', '청구', '납부', '잔액', '상태', '방법', '납부일'], rows)
  toast(`${rows.length}건을 저장했습니다`, 'ok')
}

async function exportAttendanceCsv(repo) {
  const to = toYmd()
  const from = `${addMonths(toMonth(to), -2)}-01`
  const records = await repo.attendanceOfRange(from, to)
  const rows = records.map((r) => [
    r.date,
    repo.cache.studentById.get(r.student_id)?.name || '(삭제)',
    repo.cache.classById.get(r.class_id)?.name || '',
    r.status, r.reason_tag || ''
  ]).sort((a, b) => String(a[0]).localeCompare(String(b[0])))
  downloadCsv(`출결기록_${from}_${to}.csv`, ['날짜', '원생', '반', '상태', '사유'], rows)
  toast(`${rows.length}건을 저장했습니다`, 'ok')
}

// ── 개발자/데모 도구 ────────────────────────────────────────
function devSection(repo) {
  const out = h('div', { class: 'small muted' })
  const bar = h('div', { class: 'progressbar', style: { margin: '8px 0' } }, h('div'))
  const scenarioSel = h('select', {})

  import('../../data/seed.js').then(({ DEMO_SCENARIOS }) => {
    for (const [key, sc] of Object.entries(DEMO_SCENARIOS)) scenarioSel.append(h('option', { value: key }, sc.label))
  })

  return h('div', {},
    h('div', { class: 'row wrap' },
      scenarioSel,
      h('button', {
        class: 'btn', onClick: async () => {
          if (!await confirmDialog('현재 데이터를 지우고 데모 데이터를 넣습니다. 계속할까요?', { danger: true, okLabel: '데모 넣기' })) return
          const { seedDemo } = await import('../../data/seed.js')
          const r = await seedDemo(scenarioSel.value)
          out.textContent = `데모 생성 완료: 원생 ${r.students} / 반 ${r.classes} / 출결 ${r.attendance}`
          setTimeout(() => location.reload(), 900)
        }
      }, '데모 데이터 넣기'),
      h('button', {
        class: 'btn', onClick: async () => {
          if (!await confirmDialog('원생 1,000명 · 출결 20만 건을 생성합니다. 기기에 따라 1~3분 걸릴 수 있습니다.', { danger: true, okLabel: '생성' })) return
          const { seedBulk } = await import('../../data/seed.js')
          const t0 = performance.now()
          const r = await seedBulk({}, (done, total) => {
            bar.firstChild.style.width = `${Math.round((done / total) * 100)}%`
            out.textContent = `출결 ${done.toLocaleString('ko-KR')} / ${total.toLocaleString('ko-KR')} 생성 중…`
          })
          out.textContent = `성능 테스트 데이터 생성 완료 (${Math.round(performance.now() - t0)}ms): 원생 ${r.students} / 반 ${r.classes} / 출결 ${r.attendance.toLocaleString('ko-KR')}`
          setTimeout(() => location.reload(), 1200)
        }
      }, '성능 테스트 데이터 (1,000명/20만건)'),
      h('button', {
        class: 'btn', onClick: async () => {
          const { measure } = await import('../../data/perf.js')
          out.textContent = '측정 중…'
          const rows = await measure()
          out.innerHTML = rows.map((r) => `${r.name}: <b>${r.ms}ms</b> ${r.ms < 1000 ? '✅' : '❌'}`).join('<br>')
        }
      }, '렌더 성능 측정'),
      h('button', {
        class: 'btn danger', onClick: async () => {
          if (!await confirmDialog('모든 데이터를 삭제합니다. 되돌릴 수 없습니다.', { danger: true, okLabel: '전체 삭제' })) return
          const { clearAll } = await import('../../data/seed.js')
          await clearAll()
          location.reload()
        }
      }, '전체 데이터 삭제')),
    bar, out,
    h('p', { class: 'small muted' }, '시작 마법사를 다시 보려면 아래 버튼을 누르세요.'),
    h('button', {
      class: 'btn sm', onClick: async () => { await repo.setSetting('wizardDone', false); location.reload() }
    }, '시작 마법사 다시 실행'))
}

// ── Pro 동기화 ──────────────────────────────────────────────
function proSection(repo) {
  const cfg = repo.getSetting('supabase') || {}
  const academy = repo.getSetting('academy') || null
  const url = h('input', { type: 'text', value: cfg.url || '', placeholder: 'https://xxxx.supabase.co' })
  const key = h('input', { type: 'text', value: cfg.anonKey || '', placeholder: 'anon public key' })
  const invite = h('input', { type: 'text', placeholder: '초대 코드 6자리', style: { maxWidth: '180px' } })
  const memberName = h('input', { type: 'text', placeholder: '내 이름', style: { maxWidth: '160px' } })
  const memberPin = h('input', { type: 'text', placeholder: 'PIN 4자리', maxLength: 4, style: { maxWidth: '120px' } })
  const info = h('div', { class: 'small' })
  const migrateFile = h('input', { type: 'file', accept: 'application/json' })

  const paint = () => {
    const a = repo.getSetting('academy')
    clear(info)
    info.append(a
      ? h('div', {}, h('span', { class: 'badge ok' }, `연결됨: ${a.name}`), h('div', { class: 'small muted' }, `초대 코드 ${a.invite_code} — 강사 기기에서 이 코드로 합류합니다`))
      : h('span', { class: 'badge warn' }, '아직 학원이 연결되지 않았습니다'))
  }
  paint()

  migrateFile.addEventListener('change', async () => {
    const f = migrateFile.files?.[0]
    if (!f) return
    try {
      const backup = parseBackup(await f.text())
      const sync = await import('../../data/sync.js')
      const summary = await sync.migrateFromBackup(backup)
      toast(`마이그레이션 완료: ${Object.entries(summary).map(([k, v]) => `${k} ${v}`).join(', ')}`, 'ok')
    } catch (err) {
      toast(err.message, 'error')
    }
  })

  return h('div', {},
    info,
    h('div', { class: 'inline-fields', style: { marginTop: '12px' } }, field('Supabase URL', url), field('anon key', key)),
    h('div', { class: 'row wrap' },
      h('button', {
        class: 'btn', onClick: async () => {
          await repo.setSetting('supabase', { url: url.value.trim(), anonKey: key.value.trim() })
          toast('접속 정보를 저장했습니다. 새로고침 후 동기화가 시작됩니다', 'ok')
        }
      }, '접속 정보 저장'),
      h('button', {
        class: 'btn primary', onClick: async () => {
          try {
            const sync = await import('../../data/sync.js')
            const lic = repo.getSetting('license')
            const a = await sync.createAcademy({
              name: branding().name, licenseHash: lic?.key_hash || '', brandColor: branding().brand_color
            })
            paint()
            toast(`학원을 만들었습니다. 초대 코드: ${a.invite_code}`, 'ok')
          } catch (err) { toast(err.message, 'error') }
        }
      }, '이 기기에서 학원 만들기'),
      h('button', {
        class: 'btn', onClick: async () => {
          try {
            const sync = await import('../../data/sync.js')
            await sync.joinAcademy(invite.value, { name: memberName.value.trim() || '강사', role: 'teacher', pin: memberPin.value })
            paint()
            toast('학원에 합류했습니다', 'ok')
            setTimeout(() => location.reload(), 800)
          } catch (err) { toast(err.message, 'error') }
        }
      }, '초대 코드로 합류')),
    h('div', { class: 'row wrap', style: { marginTop: '8px' } }, invite, memberName, memberPin),
    h('div', { class: 'row wrap', style: { marginTop: '12px' } },
      h('button', {
        class: 'btn sm', onClick: async () => {
          const sync = await import('../../data/sync.js')
          await sync.syncNow()
          const st = sync.status()
          toast(st.error ? `동기화 실패: ${st.error}` : `동기화 완료 (대기 ${st.pending}건)`, st.error ? 'error' : 'ok')
        }
      }, '지금 동기화'),
      h('div', { class: 'grow' }, h('div', { class: 'small muted' }, 'Lite 백업 파일을 올려 Pro 로 옮기기'), migrateFile)),
    h('p', { class: 'small muted' }, 'supabase/schema.sql 을 Supabase SQL 편집기에서 한 번 실행하면 테이블과 RLS 정책이 만들어집니다.'))
}
