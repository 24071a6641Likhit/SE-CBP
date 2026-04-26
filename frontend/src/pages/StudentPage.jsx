import React, {useEffect, useMemo, useState} from 'react'
import 'react-quill/dist/quill.snow.css'
import ReactQuill from 'react-quill'

const QUEUE_KEY = 'student_letter_queue_v1'

const TEMPLATES = [
  {
    id: 'cultural',
    label: 'Cultural Event',
    body: '<p>Respected Coordinator,</p><p>I request attendance consideration for participating in the college cultural event.</p><p>Thank you.</p>',
  },
  {
    id: 'sports',
    label: 'Sports Event',
    body: '<p>Respected Coordinator,</p><p>I request attendance consideration for participation in the inter-college sports event.</p><p>Thank you.</p>',
  },
  {
    id: 'technical',
    label: 'Technical Event',
    body: '<p>Respected Coordinator,</p><p>I request attendance consideration for participating in a technical competition/workshop.</p><p>Thank you.</p>',
  },
]

const PERIOD_WINDOWS = {
  1: {start: '10:00:00', end: '11:00:00'},
  2: {start: '11:00:00', end: '12:00:00'},
  3: {start: '12:00:00', end: '13:00:00'},
  4: {start: '13:40:00', end: '14:40:00'},
  5: {start: '14:40:00', end: '15:40:00'},
  6: {start: '15:40:00', end: '16:40:00'},
}

function readQueue() {
  try {
    const raw = localStorage.getItem(QUEUE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch (_err) {
    return []
  }
}

function writeQueue(items) {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(items))
}

export default function StudentPage({token}){
  const [profile,setProfile] = useState(null)
  const [template,setTemplate] = useState(TEMPLATES[0].id)
  const [eventType,setEventType] = useState('half_day_or_less')
  const [eventName,setEventName] = useState('')
  const [eventDate,setEventDate] = useState(new Date().toISOString().slice(0,10))
  const [startPeriod,setStartPeriod] = useState(1)
  const [durationHours,setDurationHours] = useState(1)
  const [oneDayDate,setOneDayDate] = useState(new Date().toISOString().slice(0,10))
  const [multiStartDate,setMultiStartDate] = useState(new Date().toISOString().slice(0,10))
  const [multiEndDate,setMultiEndDate] = useState(new Date().toISOString().slice(0,10))
  const [content,setContent] = useState(TEMPLATES[0].body)
  const [letters,setLetters] = useState([])
  const [syncStatus,setSyncStatus] = useState('Synced')
  const [msg,setMsg] = useState(null)

  const queueLength = useMemo(() => readQueue().length, [syncStatus])

  function formatDateTime(value){
    if(!value) return 'N/A'
    const dt = new Date(value)
    if(Number.isNaN(dt.getTime())) return value
    return dt.toLocaleString()
  }

  function computeWindow(){
    if(eventType === 'half_day_or_less'){
      const startP = Number(startPeriod)
      const dur = Number(durationHours)
      const endP = startP + dur - 1
      if(endP > 6){
        throw new Error('Selected window exceeds available 6 periods in a day')
      }
      const startStr = PERIOD_WINDOWS[startP]?.start
      const endStr = PERIOD_WINDOWS[endP]?.end
      if(!startStr || !endStr){
        throw new Error('Invalid period selection')
      }
      return {
        start_datetime: `${eventDate}T${startStr}`,
        end_datetime: `${eventDate}T${endStr}`,
      }
    }

    if(eventType === 'one_day'){
      return {
        start_datetime: `${oneDayDate}T${PERIOD_WINDOWS[1].start}`,
        end_datetime: `${oneDayDate}T${PERIOD_WINDOWS[6].end}`,
      }
    }

    if(multiEndDate < multiStartDate){
      throw new Error('For multi-day events, end date must be same as or after start date')
    }
    return {
      start_datetime: `${multiStartDate}T${PERIOD_WINDOWS[1].start}`,
      end_datetime: `${multiEndDate}T${PERIOD_WINDOWS[6].end}`,
    }
  }

  const maxDurationFromStart = Math.max(1, 7 - Number(startPeriod))

  function statusClassName(status){
    const normalized = String(status || '').toLowerCase()
    if(normalized.includes('approved')) return 'student-status approved'
    if(normalized.includes('rejected')) return 'student-status rejected'
    return 'student-status pending'
  }

  async function loadProfile(){
    const res = await fetch('/api/me', {headers:{'Authorization': `Bearer ${token}`}})
    const j = await res.json()
    if(!res.ok) throw new Error(j.detail || j.message || 'Failed to load profile')
    setProfile(j)
  }

  async function loadLetters(){
    const res = await fetch('/api/letters', {headers:{'Authorization': `Bearer ${token}`}})
    const j = await res.json()
    if(!res.ok) throw new Error(j.detail || j.message || 'Failed to load letters')
    setLetters(j)
  }

  async function postLetter(payload){
    const res = await fetch('/api/letters', {
      method:'POST',
      headers:{'Content-Type':'application/json', 'Authorization': `Bearer ${token}`},
      body: JSON.stringify(payload),
    })
    const j = await res.json()
    if(!res.ok){
      const detail = j.detail || j.message || j
      const text = typeof detail === 'object' ? (detail.message || JSON.stringify(detail)) : String(detail)
      throw new Error(text)
    }
    return j
  }

  async function flushQueue(){
    if(!navigator.onLine) return
    const queued = readQueue()
    if(!queued.length){
      setSyncStatus('Synced')
      return
    }
    setSyncStatus(`Syncing ${queued.length} queued submission(s)...`)
    const remaining = []
    for(const item of queued){
      try{
        await postLetter(item)
      }catch(_err){
        remaining.push(item)
      }
    }
    writeQueue(remaining)
    setSyncStatus(remaining.length ? `${remaining.length} queued submission(s) pending` : 'Synced')
    await loadLetters()
  }

  useEffect(()=>{
    loadProfile().catch(e=>setMsg('Error: '+String(e)))
    loadLetters().catch(e=>setMsg('Error: '+String(e)))
    flushQueue()

    const onOnline = ()=>{ flushQueue().catch(()=>{}) }
    window.addEventListener('online', onOnline)
    const interval = setInterval(()=>{ flushQueue().catch(()=>{}) }, 20000)

    return ()=>{
      window.removeEventListener('online', onOnline)
      clearInterval(interval)
    }
  }, [])

  useEffect(()=>{
    const selected = TEMPLATES.find(t=>t.id === template)
    if(selected) setContent(selected.body)
  }, [template])

  useEffect(()=>{
    if(durationHours > maxDurationFromStart){
      setDurationHours(maxDurationFromStart)
    }
  }, [maxDurationFromStart, durationHours])

  async function submit(e){
    e.preventDefault()
    setMsg(null)
    if(!profile?.student_roll || !profile?.student_name){
      setMsg('Error: your account is not linked to a student roster entry')
      return
    }

    let windowData
    try{
      windowData = computeWindow()
    }catch(e){
      setMsg('Error: '+String(e))
      return
    }

    const payload = {
      student_roll: profile.student_roll,
      student_name: profile.student_name,
      event_name: eventName,
      body: content,
      start_datetime: windowData.start_datetime,
      end_datetime: windowData.end_datetime,
    }

    try{
      if(!navigator.onLine){
        const queued = readQueue()
        queued.push(payload)
        writeQueue(queued)
        setSyncStatus(`${queued.length} queued submission(s) pending`)
        setMsg('Offline: letter queued and will sync automatically')
      }else{
        const j = await postLetter(payload)
        setMsg('Submitted - id: '+j.id)
      }

      setEventName('')
      setContent(TEMPLATES.find(t=>t.id === template)?.body || '')
      await loadLetters()
    }catch(e){
      setMsg('Error: '+String(e))
    }
  }

  return (
    <div className="student-dashboard">
      <section className="student-hero">
        <div>
          <h2>Student Dashboard</h2>
          <p>Create attendance letters and track approval updates in one place.</p>
        </div>
        <div className="student-hero-badges">
          <span className="student-chip"><strong>Roll</strong>{profile?.student_roll || 'N/A'}</span>
          <span className="student-chip"><strong>Name</strong>{profile?.student_name || 'N/A'}</span>
          <span className="student-chip"><strong>Sync</strong>{syncStatus}</span>
          <span className="student-chip"><strong>Queue</strong>{queueLength}</span>
        </div>
      </section>

      <div className="student-grid">
        <section className="student-panel">
          <div className="student-panel-head">
            <h3>Create Letter</h3>
            <p>Use a template, set event timing, and submit instantly.</p>
          </div>

          <form onSubmit={submit} className="student-form">
            <div className="student-field">
              <label>Template</label>
              <select value={template} onChange={e=>setTemplate(e.target.value)}>
                {TEMPLATES.map(t=><option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </div>

            <div className="student-field">
              <label>Event name</label>
              <input value={eventName} onChange={e=>setEventName(e.target.value)} required />
            </div>

            <div className="student-field">
              <label>Event type</label>
              <select value={eventType} onChange={e=>setEventType(e.target.value)}>
                <option value="half_day_or_less">Less than or equal to half day</option>
                <option value="one_day">One day</option>
                <option value="multi_day">More than one day</option>
              </select>
            </div>

            {eventType === 'half_day_or_less' && (
              <div className="student-field-row">
                <div className="student-field">
                  <label>Date</label>
                  <input type="date" value={eventDate} onChange={e=>setEventDate(e.target.value)} required/>
                </div>
                <div className="student-field">
                  <label>Start period</label>
                  <select value={startPeriod} onChange={e=>setStartPeriod(Number(e.target.value))}>
                    <option value={1}>P1 (10:00-11:00)</option>
                    <option value={2}>P2 (11:00-12:00)</option>
                    <option value={3}>P3 (12:00-13:00)</option>
                    <option value={4}>P4 (13:40-14:40)</option>
                    <option value={5}>P5 (14:40-15:40)</option>
                    <option value={6}>P6 (15:40-16:40)</option>
                  </select>
                </div>
                <div className="student-field">
                  <label>Window width (hours)</label>
                  <select value={durationHours} onChange={e=>setDurationHours(Number(e.target.value))}>
                    {Array.from({length: maxDurationFromStart}, (_, i)=>i+1).map(h => (
                      <option key={h} value={h}>{h} hour(s)</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {eventType === 'one_day' && (
              <div className="student-field">
                <label>Select day</label>
                <input type="date" value={oneDayDate} onChange={e=>setOneDayDate(e.target.value)} required/>
              </div>
            )}

            {eventType === 'multi_day' && (
              <div className="student-field-row">
                <div className="student-field">
                  <label>Start day</label>
                  <input type="date" value={multiStartDate} onChange={e=>setMultiStartDate(e.target.value)} required/>
                </div>
                <div className="student-field">
                  <label>End day</label>
                  <input type="date" value={multiEndDate} onChange={e=>setMultiEndDate(e.target.value)} required/>
                </div>
              </div>
            )}

            <div className="student-field">
              <label>Letter content</label>
              <div className="student-editor-wrap">
                <ReactQuill theme="snow" value={content} onChange={setContent} modules={{toolbar: [['bold','italic','underline'], [{ 'list': 'ordered'}, { 'list': 'bullet'}], [{ 'align': [] }]]}} />
              </div>
            </div>

            <button type="submit" className="student-submit-btn">Submit Letter</button>
          </form>
        </section>

        <section className="student-panel">
          <div className="student-panel-head">
            <h3>Previous Letters</h3>
            <p>Latest submissions and their review status.</p>
          </div>

          <div className="student-letters-list">
            {letters.map(l => (
              <article key={l.id} className="student-letter-item">
                <div className="student-letter-top">
                  <h4>{l.event_name}</h4>
                  <span className={statusClassName(l.status)}>{l.status}</span>
                </div>
                <div className="student-letter-meta">
                  <span>Type: {l.event_type || 'N/A'} | Window: {l.event_summary || 'N/A'}</span>
                  <span>Start: {formatDateTime(l.start_datetime)}</span>
                  <span>End: {formatDateTime(l.end_datetime)}</span>
                  <span>Submitted: {formatDateTime(l.submitted_at)}</span>
                </div>
              </article>
            ))}
            {!letters.length && <div className="student-empty">No letters yet. Your submissions will appear here.</div>}
          </div>
        </section>
      </div>

      {msg && <div className="student-message">{msg}</div>}
    </div>
  )
}
