import React, { useEffect, useMemo, useState } from 'react'

const styles: Record<string, React.CSSProperties> = {
  page: { margin: 0, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial', background: '#0f172a', color: '#e5e7eb', minHeight: '100vh' },
  container: { maxWidth: 980, margin: '0 auto', padding: '24px 16px 48px' },
  card: { background: '#111827', border: '1px solid #1f2937', borderRadius: 12, padding: 16, marginBottom: 16 },
  label: { display: 'block', margin: '8px 0 4px', color: '#cbd5e1' },
  input: { width: '100%', padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0b1020', color: '#e5e7eb' },
  button: { background: '#22d3ee', color: '#0b1020', border: 'none', borderRadius: 10, padding: '10px 14px', fontWeight: 700, cursor: 'pointer' },
  row: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 12 },
  col12: { gridColumn: 'span 12' },
  col6: { gridColumn: 'span 12' },
  small: { color: '#94a3b8', fontSize: 12 },
}

function useApiBase() {
  // If running via Vite (5173), target backend on 8001 at same host
  const href = typeof window !== 'undefined' ? window.location.href : ''
  try {
    const url = new URL(href)
    if (url.port === '5173') {
      url.port = '8001'
      return url.origin
    }
  } catch {}
  return window.location.origin
}

type Voice = { id: string; gender?: string; language_code?: string; engines?: string[] }

export function App() {
  const API_BASE = useApiBase()
  const [voices, setVoices] = useState<Voice[]>([])
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [voice, setVoice] = useState('')
  const [gender, setGender] = useState('')
  const [srcLang, setSrcLang] = useState('en-IN')
  const [dstLang, setDstLang] = useState('en-IN')
  const [accent, setAccent] = useState('en-IN')
  const [engine, setEngine] = useState('')
  const [format, setFormat] = useState<'mp3' | 'wav' | 'ogg_vorbis' | 'pcm'>('mp3')
  const [sampleRate, setSampleRate] = useState('16000')
  const [loading, setLoading] = useState(false)

  useEffect(() => { void fetchVoices(accent) }, [])

  async function fetchVoices(lang?: string) {
    try {
      const res = await fetch(`${API_BASE}/voices?language_code=${encodeURIComponent(lang || '')}`)
      const data = await res.json()
      setVoices(data)
    } catch (e) {
      console.error(e)
    }
  }

  async function synthesize() {
    setLoading(true)
    try {
      const fd = new FormData()
      if (text) fd.append('text', text)
      if (file) fd.append('file', file)
      if (voice) fd.append('voice', voice)
      if (gender) fd.append('gender', gender)
      if (srcLang) fd.append('src_lang', srcLang)
      if (dstLang) fd.append('dst_lang', dstLang)
      if (accent) fd.append('accent', accent)
      if (engine) fd.append('engine', engine)
      if (sampleRate) fd.append('sample_rate', sampleRate)
      fd.append('format', format)

      let res: Response
      try {
        res = await fetch(`${API_BASE}/synthesize`, { method: 'POST', body: fd })
      } catch (fetchErr) {
        throw new Error('Network error calling /synthesize')
      }
      if (!res.ok) {
        let errMsg = `HTTP ${res.status}`
        try {
          const err = await res.json()
          if (err && (err as any).error) errMsg = (err as any).error as string
        } catch {}
        throw new Error(errMsg)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `polly_output.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      console.error(e)
      alert(e?.message ?? 'Unexpected error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <h1>Polly TTS – Web UI</h1>
        <div style={styles.card}>
          <label style={styles.label}>Text</label>
          <textarea rows={6} value={text} onChange={e => setText(e.target.value)} placeholder="Type text here..." style={styles.input as any} />
          <label style={styles.label}>Or upload file (.txt or .pdf)</label>
          <input type="file" accept=".txt,.pdf" onChange={e => setFile(e.target.files?.[0] ?? null)} style={styles.input} />
        </div>
        <div style={styles.row}>
          <div style={{ ...styles.card, ...styles.col6 }}>
            <label style={styles.label}>Source language</label>
            <select value={srcLang} onChange={e => setSrcLang(e.target.value)} style={styles.input as any}>
              <option value="en-IN">English (India) - en-IN</option>
              <option value="pt-PT">Portuguese (Portugal) - pt-PT</option>
              <option value="es-US">Spanish (US) - es-US</option>
            </select>
            <label style={{ ...styles.label, marginTop: 8 }}>Destination language</label>
            <select value={dstLang} onChange={e => { const code = e.target.value; setDstLang(code); setAccent(code); void fetchVoices(code) }} style={styles.input as any}>
              <option value="en-IN">English (India) - en-IN</option>
              <option value="pt-PT">Portuguese (Portugal) - pt-PT</option>
              <option value="es-US">Spanish (US) - es-US</option>
            </select>
            <label style={styles.label}>Voice</label>
            <select value={voice} onChange={e => setVoice(e.target.value)} style={styles.input as any}>
              <option value="">Auto (by gender/accent)</option>
              {voices.map(v => (
                <option key={v.id} value={v.id}>{v.id} ({v.gender}) {v.language_code} [{(v.engines || []).join('/')}]</option>
              ))}
            </select>
            <label style={styles.label}>Gender</label>
            <select value={gender} onChange={e => setGender(e.target.value)} style={styles.input as any}>
              <option value="">Any</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div style={{ ...styles.card, ...styles.col6 }}>
            <label style={styles.label}>Engine</label>
            <select value={engine} onChange={e => setEngine(e.target.value)} style={styles.input as any}>
              <option value="">Auto</option>
              <option value="standard">standard</option>
              <option value="neural">neural</option>
            </select>
            <label style={styles.label}>Format</label>
            <select value={format} onChange={e => setFormat(e.target.value as any)} style={styles.input as any}>
              <option value="mp3">mp3</option>
              <option value="wav">wav</option>
              <option value="ogg_vorbis">ogg_vorbis</option>
              <option value="pcm">pcm</option>
            </select>
            <label style={styles.label}>Sample rate</label>
            <input value={sampleRate} onChange={e => setSampleRate(e.target.value)} style={styles.input} />
          </div>
        </div>
        <div style={styles.card}>
          <button onClick={synthesize} disabled={loading} style={styles.button}>{loading ? 'Converting…' : 'Convert'}</button>
        </div>
        <div style={styles.small}>API: {API_BASE}</div>
      </div>
    </div>
  )
}


