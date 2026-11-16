// 설정 탭 — 브랜딩 / 학습항목(custom) / 과목·강사 / 알림 템플릿 / 라이선스 / 백업·복원 / 개발자 도구

import { h, clear, toast, modal, field, confirmDialog, copyText } from '../dom.js'
import { branding, saveBranding, resizeImage, logoDataUrl, updateManifest } from '../branding.js'
import { FIELD_TYPES, PRESETS, validateField } from '../../core/customfields.js'
import { DEFAULT_TEMPLATES, TEMPLATE_VARS, unknownVars, withDefaults } from '../../core/templates.js'
import { formatKey, normalizeKey, PRODUCTS } from '../../core/license.js'
import { entitlement, activateWithKey, deviceCode } from '../activation.js'
import { buildBackup, parseBackup, BACKUP_TABLES } from '../../core/backup.js'
import { ROLES } from '../../core/perm.js'
import { db } from '../../data/db.js'
import { restoreFromBackup } from '../../data/restore.js'
import { downloadCsv } from '../../core/csv.js'
import { toYmd, toMonth, addMonths, daysBetween } from '../../core/date.js'
import { showCoach } from '../coach.js'
import { openInstallGuide } from '../install.js'
import { icon } from '../icons.js'
import { buyUrl } from '../../core/store.js'

export async function render(root, ctx) {
  const { repo, user } = ctx
  const isOwner = (user?.role || 'owner') === 'owner'

  // 자주 찾는 순서대로 — 맨 위 셋은 처음 쓰는 원장님이 한 번은 들르는 곳이다
  const sections = [
    section('monitor', '화면', '글씨 크기 · 홈 화면에 설치', displaySection(repo), true),
    section('home', '학원 이름 · 로고 · 색', '화면 위쪽과 리포트·영수증에 들어갑니다', brandingSection(repo)),
    section('save', '백업 · 복원', '자료를 파일로 보관하고 되살립니다', backupSection(repo)),
    section('won', '수강료 규칙', '내는 날 · 형제 할인', billingSection(repo)),
    section('send', '문자 안내 문구', '결석 · 수강료 · 레슨 안내에 쓰는 글', templateSection(repo)),
    section('users', '과목 · 선생님 · 잠금 번호', '과목을 추가하고, 선생님 계정과 잠금 번호를 정합니다', peopleSection(repo, isOwner)),
    section('list', '학습 기록 항목', '원생 카드에 적어 둘 내용을 정합니다 (예: 급수, 콩쿨)', customFieldSection(repo)),
    section('key', '인증키 · 구매', '인증 상태 확인 · 인증키 넣기', licenseSection(repo)),
    repo.getPlan() === 'pro' ? section('repeat', 'Pro 동기화', '여러 기기에서 함께 쓰기', proSection(repo)) : null,
    section('settings', '고급', '샘플 자료 넣기 · 전체 초기화', devSection(repo))
  ].filter(Boolean)
  root.append(
    h('div', { class: 'page-head' },
      h('h1', {}, '설정'),
      h('p', {}, '바꾸고 싶은 항목을 누르면 펼쳐집니다.')),
    ...sections)
  return () => {}
}

function section(ico, title, desc, body, open = false) {
  return h('details', { class: 'card setsec', open },
    h('summary', {},
      h('span', { class: 'todo-ico' }, icon(ico, { size: 20 })),
      h('span', { class: 'grow' }, h('b', {}, title), h('span', { class: 'small muted' }, desc)),
      icon('chevronRight', { size: 18, class: 'chev' })),
    h('div', { class: 'setsec-body' }, body))
}

// ── 화면·사용 편의 ──────────────────────────────────────────
// 선생님 연령대가 넓다. 글씨 크기와 안내는 언제든 다시 조절할 수 있어야 한다.
function displaySection(repo) {
  const cur = repo.getSetting('textSize') || 'normal'
  const box = h('div', { class: 'row wrap' })
  const SIZES = [['normal', '보통'], ['large', '크게'], ['xlarge', '아주 크게']]
  const paint = () => {
    clear(box)
    for (const [key, label] of SIZES) {
      box.append(h('button', {
        class: `chip ${(repo.getSetting('textSize') || 'normal') === key ? 'active' : ''}`,
        onClick: async () => {
          await repo.setSetting('textSize', key)
          document.documentElement.dataset.textsize = key
          paint()
          toast(`글씨를 ${label} 로 바꿨습니다`, 'ok')
        }
      }, label))
    }
  }
  paint()

  return h('div', {},
    field('글씨 크기', box, '화면 전체 글씨가 함께 커집니다. 언제든 되돌릴 수 있습니다.'),
    h('div', { class: 'row wrap', style: { marginTop: '6px' } },
      h('button', { class: 'btn', onClick: () => showCoach() }, '처음 안내 다시 보기'),
      h('button', { class: 'btn', onClick: () => openInstallGuide() }, '홈 화면에 설치하기')),
    h('div', { class: 'callout tip' },
      h('p', {}, h('b', {}, '막히면 "도움말"을 누르세요.'), ' 하고 싶은 일을 고르면 순서대로 알려 드립니다. (휴대폰은 오른쪽 아래 물음표)')))
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
        h('div', { class: 'small muted' }, '로고가 없으면 학원 이름 첫 글자를 대신 씁니다'),
        b.logo ? h('button', {
          class: 'btn sm', style: { marginTop: '6px' }, onClick: async () => {
            await saveBranding({ logo: null })
            preview.src = logoDataUrl(192)
            toast('로고를 삭제했습니다')
          }
        }, '로고 삭제') : null)),
    h('div', { class: 'inline-fields' }, field('학원 이름', name), field('학원 전화번호', phone), field('학원 색', color)),
    h('div', { class: 'row' },
      h('button', {
        class: 'btn primary', onClick: async () => {
          await saveBranding({ name: name.value.trim() || '학원 관리노트', phone: phone.value.trim(), brand_color: color.value })
          toast('바꿨습니다', 'ok')
        }
      }, '저장'),
      h('button', {
        class: 'btn', onClick: () => {
          const ok = updateManifest()
          toast(ok ? '홈 화면 아이콘을 새로 만들었습니다' : '이 기기는 아이콘을 바꿀 수 없어 기본 아이콘을 씁니다')
        }
      }, '홈 화면 아이콘 새로 만들기')
    ),
    h('p', { class: 'small muted' }, '여기서 정한 이름·로고·색이 화면 위쪽, 학부모 리포트, 영수증, 홈 화면 아이콘에 함께 들어갑니다.')
  )
}

// ── custom 필드 ─────────────────────────────────────────────
function customFieldSection(repo) {
  const listBox = h('div')
  const presetRow = h('div', { class: 'row wrap' })

  const paint = () => {
    const fields = repo.getSetting('customFields', [])
    clear(listBox)
    if (!fields.length) listBox.append(h('p', { class: 'muted small' }, '아직 항목이 없습니다. 아래에서 학원 종류를 누르면 기본 항목이 들어옵니다.'))
    fields.forEach((f, i) => {
      listBox.append(h('div', { class: 'row', style: { padding: '8px 0', borderBottom: '1px solid var(--line)' } },
        h('div', { class: 'grow' },
          h('b', {}, f.label), h('span', { class: 'muted small' }, ` (${f.key} · ${FIELD_TYPES.find((t) => t.type === f.type)?.label || f.type})`),
          f.options?.length ? h('div', { class: 'small muted' }, f.options.join(' / ')) : null),
        h('label', { class: 'row small', style: { gap: '4px' } }, h('input', {
          type: 'checkbox', checked: !!f.onCard, style: { width: 'auto' },
          onChange: async (e) => { fields[i].onCard = e.target.checked; await repo.setSetting('customFields', fields) }
        }), '원생 카드에 표시'),
        h('label', { class: 'row small', style: { gap: '4px' } }, h('input', {
          type: 'checkbox', checked: !!f.onReport, style: { width: 'auto' },
          onChange: async (e) => { fields[i].onReport = e.target.checked; await repo.setSetting('customFields', fields) }
        }), '리포트에 표시'),
        h('button', {
          class: 'btn sm danger', onClick: async () => {
            if (!await confirmDialog(`'${f.label}' 항목을 지울까요? 이미 적어 둔 내용은 남아 있습니다.`, { danger: true, okLabel: '삭제' })) return
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
          toast(`${key} 기본 항목을 넣었습니다`, 'ok')
        }
      }, `${key} 기본 항목`))
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
        title: '학습 기록 항목 추가',
        body: h('div', {},
          field('항목 이름', label), field('구분 이름 (영어)', key, '프로그램이 이 항목을 알아보는 이름입니다. 영어로 짧게 적고, 한 번 정하면 바꾸지 마세요'),
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
    h('p', { class: 'small muted' }, '여기서 만든 항목이 원생 카드와 학부모 리포트에 나타납니다. 교재와 진도는 원생 카드의 "교재·진도" 칸에서 따로 적습니다.'))
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
        h('span', { class: 'muted small' }, `잠금 번호 ${String(u.pin || '').replace(/./g, '•')}`),
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
      title: u ? '계정 고치기' : '계정 추가',
      body: h('div', { class: 'inline-fields' }, field('이름', name), field('하는 일', role), field('잠금 번호 (숫자 4자리)', pin, '앱을 열 때 누르는 번호입니다')),
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
            if (!/^\d{4}$/.test(pin.value)) { toast('잠금 번호는 숫자 4자리입니다', 'error'); return false }
            const dup = repo.cache.users.find((x) => x.pin === pin.value && x.id !== u?.id)
            if (dup) { toast('다른 계정이 이미 쓰는 번호입니다', 'error'); return false }
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
    h('div', { class: 'card-title', style: { marginTop: '16px' } }, '선생님 계정 · 잠금 번호'), userBox,
    isOwner ? h('button', { class: 'btn sm', onClick: () => editUser() }, '+ 계정 추가') : null,
    h('div', { class: 'callout tip' },
      h('p', {}, h('b', {}, '혼자 쓰신다면 그대로 두세요.'), ' 잠금 번호가 처음 그대로(0000)이고 계정이 하나면 앱을 열 때 번호를 묻지 않습니다.'),
      h('p', {}, '번호를 다른 숫자로 바꾸거나 선생님 계정을 추가하면 그때부터 번호를 묻습니다. 반은 "시간표" 메뉴에서 만듭니다.')))
}

// ── 알림 템플릿 ─────────────────────────────────────────────
function templateSection(repo) {
  const box = h('div')
  const paint = () => {
    const templates = withDefaults(repo.getSetting('templates'))
    clear(box)
    templates.forEach((t, i) => {
      const body = h('textarea', { value: t.body })
      box.append(h('div', { style: { marginBottom: '14px' } },
        h('div', { class: 'row' }, h('b', { class: 'grow' }, t.name),
          h('button', {
            class: 'btn sm', onClick: async () => {
              const bad = unknownVars(body.value)
              if (bad.length) return toast(`쓸 수 없는 낱말이 있습니다: ${bad.join(' ')}`, 'error')
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
    h('div', { class: 'row wrap small muted' }, '문구 안에 넣을 수 있는 낱말 (누르면 복사됩니다): ',
      ...TEMPLATE_VARS.map((v) => h('span', { class: 'chip', onClick: () => copyText(v.key).then(() => toast(`${v.key} 복사`)) }, `${v.key} ${v.desc}`))),
    h('div', { class: 'row', style: { marginTop: '10px' } },
      h('button', {
        class: 'btn sm', onClick: async () => { await repo.setSetting('templates', DEFAULT_TEMPLATES); paint(); toast('기본 문구로 되돌렸습니다') }
      }, '처음 문구로 되돌리기')))
}

// ── 인증키(시디키) ──────────────────────────────────────────
function licenseSection(repo) {
  const box = h('div')

  const paint = () => {
    const ent = entitlement()
    const lic = repo.getSetting('license')
    const input = h('input', { type: 'text', placeholder: 'XXXX-XXXX-XXXX', value: lic?.key || '', 'aria-label': '인증키' })
    input.addEventListener('input', () => { if (normalizeKey(input.value).length <= 12) input.value = formatKey(input.value).slice(0, 14) })
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
        : h('div', {},
          h('span', { class: 'badge warn' },
            ent.mode === 'trial' ? `무료 체험 ${ent.daysLeft}일 남음` : '아직 인증 전입니다'),
          h('p', { class: 'small muted', style: { margin: '8px 0 0' } },
            '구매하시면 인증키가 메일로 바로 옵니다. 메일의 버튼을 누르거나 아래 칸에 키를 넣으면 지금까지 넣은 자료 그대로 계속 쓰실 수 있습니다.'),
          h('a', { class: 'btn primary', style: { marginTop: '10px' }, href: buyUrl('settings'), target: '_blank', rel: 'noopener' },
            icon('cart', { size: 17 }), '구매하러 가기')),

      h('div', { class: 'row', style: { marginTop: '10px' } },
        h('div', { class: 'grow' }, input),
        h('button', {
          class: 'btn primary', onClick: async () => {
            const res = await activateWithKey(input.value, { academyName: nameInput.value })
            if (!res.ok) return toast(res.reason, 'error')
            toast(`${res.plan === 'pro' ? 'Pro' : 'Lite'} 인증 완료. 앱을 새로고침합니다`, 'ok')
            setTimeout(() => location.reload(), 800)
          }
        }, lic ? '다른 키로 바꾸기' : '인증하기')),

      h('div', { style: { marginTop: '8px' } }, nameInput),
      h('p', { class: 'small muted' },
        '받은 메일을 통째로 붙여 넣어도 됩니다. ', h('b', {}, '피아노 관리노트에서 받은 인증키'), '도 그대로 쓸 수 있습니다 ',
        '(학원명으로 받은 키라면 위 칸에 그 학원명을 함께 넣어 주세요).'),

      h('div', { class: 'row small muted' },
        h('span', { class: 'grow' }, `기기번호 ${deviceCode()} — 문의하실 때 알려 주세요`),
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
    h('option', { value: String(u), selected: p.roundUnit === u }, u === 1 ? '버리지 않음' : `${u.toLocaleString('ko-KR')}원 아래는 버림`)))
  const sibOn = h('input', { type: 'checkbox', checked: p.sibling.enabled, style: { width: 'auto' } })
  const sibValue = h('input', { type: 'number', min: '0', value: p.sibling.value })
  const sibType = h('select', {},
    h('option', { value: 'percent', selected: p.sibling.type === 'percent' }, '%'),
    h('option', { value: 'amount', selected: p.sibling.type === 'amount' }, '원'))
  const sibApply = h('select', {},
    h('option', { value: 'all', selected: p.sibling.applyTo === 'all' }, '형제 전원'),
    h('option', { value: 'others', selected: p.sibling.applyTo === 'others' }, '둘째부터'))

  return h('div', {},
    h('div', { class: 'inline-fields' },
      field('수강료 내는 날 (매달)', dueDay, '이 날이 지나도 안 낸 원생이 있으면 "오늘" 화면에서 알려 드립니다'),
      field('끝자리 버림', roundUnit, '할인으로 생긴 자투리 금액을 정리합니다')),
    h('div', { class: 'card', style: { marginTop: '10px' } },
      h('label', { class: 'row', style: { gap: '8px' } }, sibOn, h('b', {}, '형제·자매가 함께 다니면 자동으로 할인')),
      h('div', { class: 'inline-fields', style: { marginTop: '8px' } },
        field('할인', h('div', { class: 'row' }, h('div', { class: 'grow' }, sibValue), sibType)),
        field('누구에게', sibApply)),
      h('p', { class: 'small muted' }, '학부모 연락처가 같은 원생을 형제로 봅니다.')),
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
          toast('수강료 규칙을 저장했습니다', 'ok')
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
      if (!await confirmDialog(`지금 자료를 모두 지우고 백업 파일의 자료로 바꿉니다.\n\n${counts}`, { title: '백업 파일로 되살리기', okLabel: '되살리기', danger: true })) return
      await restoreFromBackup(backup)
      toast('되살렸습니다. 화면을 다시 엽니다', 'ok')
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
      }, icon('download', { size: 17 }), '백업 파일 받기')),
    h('div', { class: 'callout tip' },
      h('p', {}, h('b', {}, '받은 파일은 다른 곳에도 보관하세요.'), ' 카카오톡 "나에게 보내기"나 USB에 넣어 두면, 기기가 고장 나거나 바뀌어도 이 파일 하나로 되살릴 수 있습니다.')),
    field('백업 파일로 되살리기', fileInput, '예전에 받아 둔 백업 파일을 고르면 그때 자료로 돌아갑니다. 지금 자료는 지워집니다.'),
        h('div', { class: 'card-title', style: { marginTop: '18px' } }, '엑셀 파일로 내려받기'),
    h('div', { class: 'row wrap' },
      h('button', { class: 'btn sm', onClick: () => exportStudentsCsv(repo) }, '원생 명단'),
      h('button', { class: 'btn sm', onClick: () => exportPaymentsCsv(repo) }, '수납 내역(12개월)'),
      h('button', { class: 'btn sm', onClick: () => exportAttendanceCsv(repo) }, '출결 기록(3개월)')),
    h('p', { class: 'small muted' }, '세무사에게 보내거나 따로 정리할 때 쓰세요. 엑셀에서 바로 열립니다.'))
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
          if (!await confirmDialog('지금 자료를 모두 지우고 샘플 자료를 넣습니다. 계속할까요?', { danger: true, okLabel: '샘플 넣기' })) return
          const { seedDemo } = await import('../../data/seed.js')
          const r = await seedDemo(scenarioSel.value)
          out.textContent = `데모 생성 완료: 원생 ${r.students} / 반 ${r.classes} / 출결 ${r.attendance}`
          setTimeout(() => location.reload(), 900)
        }
      }, '샘플 자료 넣기'),
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
      }, '속도 시험용 자료 (1,000명 · 20만 건)'),
      h('button', {
        class: 'btn', onClick: async () => {
          const { measure } = await import('../../data/perf.js')
          out.textContent = '측정 중…'
          const rows = await measure()
          out.innerHTML = rows.map((r) => `${r.name}: <b>${r.ms}ms</b> ${r.ms < 1000 ? '✅' : '❌'}`).join('<br>')
        }
      }, '화면 속도 재기'),
      h('button', {
        class: 'btn danger', onClick: async () => {
          if (!await confirmDialog('원생·출결·수강료 자료를 모두 지웁니다. 되돌릴 수 없으니 먼저 백업 파일을 받아 두세요.', { danger: true, okLabel: '모두 지우기' })) return
          const { clearAll } = await import('../../data/seed.js')
          await clearAll()
          location.reload()
        }
      }, '자료 모두 지우기')),
    bar, out,
    h('p', { class: 'small muted' }, '평소에는 쓸 일이 없는 기능입니다. 처음 설정 화면을 다시 보려면 아래 버튼을 누르세요.'),
    h('button', {
      class: 'btn sm', onClick: async () => { await repo.setSetting('wizardDone', false); location.reload() }
    }, '처음 설정 다시 하기'))
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
