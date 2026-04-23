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
  const [eventName,setEventName] = useState('')
  const [start,setStart] = useState('')
  const [end,setEnd] = useState('')
  const [content,setContent] = useState(TEMPLATES[0].body)
  const [letters,setLetters] = useState([])
  const [syncStatus,setSyncStatus] = useState('Synced')
  const [msg,setMsg] = useState(null)

  const queueLength = useMemo(() => readQueue().length, [syncStatus])

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

  async function submit(e){
    e.preventDefault()
    setMsg(null)
    if(!profile?.student_roll || !profile?.student_name){
      setMsg('Error: your account is not linked to a student roster entry')
      return
    }

    const payload = {
      student_roll: profile.student_roll,
      student_name: profile.student_name,
      event_name: eventName,
      body: content,
      start_datetime: start,
      end_datetime: end,
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
      setStart('')
      setEnd('')
      setContent(TEMPLATES.find(t=>t.id === template)?.body || '')
      await loadLetters()
    }catch(e){
      setMsg('Error: '+String(e))
    }
  }

  return (
    <div>
      <h2 className="card-title">Student Dashboard</h2>
      <div className="card">
        <div className="card-body">
          <div className="form-inline" style={{marginBottom:12}}>
            <div><strong>Roll:</strong> {profile?.student_roll || '—'}</div>
            <div><strong>Name:</strong> {profile?.student_name || '—'}</div>
            <div><strong>Sync:</strong> {syncStatus}</div>
            <div><strong>Queue:</strong> {queueLength}</div>
          </div>

          <form onSubmit={submit} className="form">
            <div>
              <label style={{display:'block',fontWeight:600}}>Template</label>
              <select value={template} onChange={e=>setTemplate(e.target.value)}>
                {TEMPLATES.map(t=><option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{display:'block',fontWeight:600}}>Event name</label>
              <input value={eventName} onChange={e=>setEventName(e.target.value)} required />
            </div>
            <div className="form-inline">
              <label>Start (local)<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)} required/></label>
              <label>End (local)<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)} required/></label>
            </div>
            <div>
              <label style={{display:'block',fontWeight:600,marginBottom:8}}>Letter content</label>
              <div className="editor-canvas">
                <ReactQuill theme="snow" value={content} onChange={setContent} modules={{toolbar: [['bold','italic','underline'], [{ 'list': 'ordered'}, { 'list': 'bullet'}], [{ 'align': [] }]]}} />
              </div>
            </div>
            <div>
              <button type="submit" className="btn">Submit</button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Previous Letters</div>
        <div className="card-body">
          <div className="table-wrapper">
            <table className="table">
              <thead><tr><th>Event</th><th>Start</th><th>End</th><th>Status</th><th>Submitted</th></tr></thead>
              <tbody>
                {letters.map(l => (
                  <tr key={l.id}>
                    <td>{l.event_name}</td>
                    <td>{l.start_datetime}</td>
                    <td>{l.end_datetime}</td>
                    <td>{l.status}</td>
                    <td>{l.submitted_at}</td>
                  </tr>
                ))}
                {!letters.length && <tr><td colSpan={5}>No letters yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {msg && <div className="note">{msg}</div>}
    </div>
  )
}
