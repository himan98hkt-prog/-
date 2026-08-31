// PianoEvent AI · Gemini 프록시 Edge Function
//
// 목적: 모바일 앱(Expo/React Native) 등 클라이언트가 GEMINI_API_KEY 없이 AI 를 쓰게 한다.
// [Client] --(Supabase 사용자 JWT)--> [이 함수] --(GEMINI_API_KEY)--> [Google Gemini API]
//
// 배포:
//   supabase secrets set GEMINI_API_KEY=...
//   supabase functions deploy gemini-proxy
//
// 웹(Next.js)에서는 이 함수가 필요 없다. app/api/* 라우트가 이미 서버에서 키를 들고 있다.

import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { GoogleGenAI } from 'https://esm.sh/@google/genai@2'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': Deno.env.get('ALLOWED_ORIGIN') ?? '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } })

const apiKey = Deno.env.get('GEMINI_API_KEY')
const supabaseUrl = Deno.env.get('SUPABASE_URL')
const anonKey = Deno.env.get('SUPABASE_ANON_KEY')

const ALLOWED_MODELS = new Set(['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'])

serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })
  if (req.method !== 'POST') return json({ error: 'POST 만 허용됩니다.' }, 405)
  if (!apiKey) return json({ error: '서버에 GEMINI_API_KEY 가 설정되지 않았습니다.' }, 500)

  // 1) 사용자 인증 — 로그인한 사용자만 AI 를 쓸 수 있게 한다 (키 도용·비용 폭주 방지)
  const authHeader = req.headers.get('Authorization')
  if (!authHeader) return json({ error: 'Unauthorized' }, 401)

  if (supabaseUrl && anonKey) {
    const supabase = createClient(supabaseUrl, anonKey, {
      global: { headers: { Authorization: authHeader } },
    })
    const { data, error } = await supabase.auth.getUser()
    if (error || !data.user) return json({ error: 'Unauthorized' }, 401)
  }

  // 2) 입력 검증
  let body: { prompt?: string; contents?: unknown; model?: string }
  try {
    body = await req.json()
  } catch {
    return json({ error: '잘못된 JSON 입니다.' }, 400)
  }

  const model = body.model && ALLOWED_MODELS.has(body.model) ? body.model : 'gemini-2.5-flash'
  const contents = typeof body.contents === 'string' ? body.contents : JSON.stringify(body.contents ?? {})
  if (contents.length > 100_000) return json({ error: '입력이 너무 깁니다.' }, 413)

  // 3) Gemini 호출
  try {
    const ai = new GoogleGenAI({ apiKey })
    const response = await ai.models.generateContent({
      model,
      contents,
      config: {
        systemInstruction: body.prompt ?? '',
        responseMimeType: 'application/json',
      },
    })
    return new Response(response.text ?? '{}', { headers: { ...CORS, 'Content-Type': 'application/json' } })
  } catch (error) {
    console.error('[gemini-proxy]', error)
    return json({ error: 'AI 호출에 실패했습니다.' }, 502)
  }
})
