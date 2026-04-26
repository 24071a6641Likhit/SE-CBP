import React, {useState, useEffect} from 'react'

const ACTION_QUEUE_KEY = 'coordinator_action_queue_v1'

function readQueue() {
  try {
    const raw = localStorage.getItem(ACTION_QUEUE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch (_err) {
    return []
  }
}

function writeQueue(items) {
  localStorage.setItem(ACTION_QUEUE_KEY, JSON.stringify(items))
}

export default function CoordinatorPage({token}){
  const [letters,setLetters] = useState([])
  const [err,setErr] = useState(null)
  const [statusFilter,setStatusFilter] = useState('Submitted')
  const [rollFilter,setRollFilter] = useState('')
  const [fromDate,setFromDate] = useState('')
  const [toDate,setToDate] = useState('')
  const [syncStatus,setSyncStatus] = useState('Synced')
  const [previewLetter,setPreviewLetter] = useState(null)

  function formatDateTime(value){
    if(!value) return 'N/A'
    const dt = new Date(value)
    if(Number.isNaN(dt.getTime())) return value
    return dt.toLocaleString()
  }

  function buildQuery(){
    const q = new URLSearchParams()
    if(statusFilter) q.set('status', statusFilter)
    if(rollFilter.trim()) q.set('roll', rollFilter.trim())
    if(fromDate) q.set('date_from', fromDate)
    if(toDate) q.set('date_to', toDate)
    return q.toString()
  }

  async function load(){
    setErr(null)
    try{
      const res = await fetch(`/api/letters?${buildQuery()}`, {headers:{'Authorization': `Bearer ${token}`}})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      setLetters(j)
    }catch(e){
      setErr(String(e))
    }
  }

  async function runAction(action){
    if(action.type === 'approve'){
      const res = await fetch(`/api/letters/${action.letterId}/approve`, {method:'POST', headers:{'Authorization': `Bearer ${token}`}})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      return
    }
    if(action.type === 'reject'){
      const res = await fetch(`/api/letters/${action.letterId}/reject`, {
        method:'POST',
        headers:{'Authorization': `Bearer ${token}`, 'Content-Type':'application/json'},
        body: JSON.stringify({comment: action.comment || null}),
      })
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
    }
  }

  async function flushQueue(){
    if(!navigator.onLine) return
    const queued = readQueue()
    if(!queued.length){
      setSyncStatus('Synced')
      return
    }
    setSyncStatus(`Syncing ${queued.length} queued action(s)...`)
    const remaining = []
    for(const action of queued){
      try{
        await runAction(action)
      }catch(_err){
        remaining.push(action)
      }
    }
    writeQueue(remaining)
    setSyncStatus(remaining.length ? `${remaining.length} queued action(s) pending` : 'Synced')
    await load()
  }

  useEffect(()=>{
    load()
    flushQueue().catch(()=>{})

    const onOnline = ()=>{ flushQueue().catch(()=>{}) }
    window.addEventListener('online', onOnline)
    const poll = setInterval(()=>{ load() }, 20000)

    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${wsProto}://${window.location.host}/ws?token=${encodeURIComponent(token)}`)
    ws.onmessage = (evt) => {
      try{
        const msg = JSON.parse(evt.data)
        if(msg?.requires_ack && msg?.id){
          ws.send(JSON.stringify({type:'ack', id: msg.id}))
        }
        if(msg?.type === 'letter.created' || msg?.type === 'letter.approved' || msg?.type === 'letter.rejected'){
          load()
        }
      }catch(_err){
        // ignore malformed ws messages
      }
    }

    return ()=>{
      window.removeEventListener('online', onOnline)
      clearInterval(poll)
      ws.close()
    }
  }, [token])

  useEffect(()=>{ load() }, [statusFilter, rollFilter, fromDate, toDate])

  async function approve(id){
    try{
      if(!navigator.onLine){
        const queued = readQueue()
        queued.push({type:'approve', letterId: id})
        writeQueue(queued)
        setSyncStatus(`${queued.length} queued action(s) pending`)
        alert('Offline: approval queued')
        return
      }
      await runAction({type:'approve', letterId: id})
      load()
      alert('Approved')
    }catch(e){alert('Error: '+e)}
  }

  async function reject(id){
    const comment = prompt('Rejection comment (optional)')
    try{
      if(!navigator.onLine){
        const queued = readQueue()
        queued.push({type:'reject', letterId: id, comment})
        writeQueue(queued)
        setSyncStatus(`${queued.length} queued action(s) pending`)
        alert('Offline: rejection queued')
        return
      }
      await runAction({type:'reject', letterId: id, comment})
      load()
      alert('Rejected')
    }catch(e){alert('Error: '+e)}
  }

  return (
    <div className="coordinator-page">
      <h2 className="card-title">Coordinator Inbox</h2>
      <div className="card">
        <div className="card-body">
          <div className="form-inline" style={{marginBottom:12}}>
            <label>Status
              <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
                <option value="">All</option>
                <option value="Submitted">Submitted</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
              </select>
            </label>
            <label>Roll
              <input value={rollFilter} onChange={e=>setRollFilter(e.target.value)} placeholder="24071A66xx" />
            </label>
            <label>From
              <input type="date" value={fromDate} onChange={e=>setFromDate(e.target.value)} />
            </label>
            <label>To
              <input type="date" value={toDate} onChange={e=>setToDate(e.target.value)} />
            </label>
            <button className="btn small" onClick={load}>Refresh</button>
          </div>
          <div className="note">Sync status: {syncStatus}</div>
          {err && <div className="error">{err}</div>}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Letters</div>
        <div className="card-body">
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Roll</th>
                  <th>Name</th>
                  <th>Event</th>
                  <th>Type</th>
                  <th>Window</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {letters.map(l => (
                  <tr key={l.id}>
                    <td>{l.student_roll}</td>
                    <td>{l.student_name}</td>
                    <td>{l.event_name}</td>
                    <td>{l.event_type || 'N/A'}</td>
                    <td>{l.event_summary || 'N/A'}</td>
                    <td>{formatDateTime(l.start_datetime)}</td>
                    <td>{formatDateTime(l.end_datetime)}</td>
                    <td>
                      <button className="btn small" onClick={()=>setPreviewLetter(l)}>Preview</button>{' '}
                      <button className="btn small" onClick={()=>approve(l.id)} disabled={l.status !== 'Submitted'}>Approve</button>{' '}
                      <button className="btn small" onClick={()=>reject(l.id)} disabled={l.status !== 'Submitted'}>Reject</button>
                    </td>
                  </tr>
                ))}
                {!letters.length && (
                  <tr><td colSpan={8}>No letters found for current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {previewLetter && (
        <div className="card">
          <div className="card-title">Letter Preview - {previewLetter.student_roll}</div>
          <div className="card-body">
            <div className="form-inline" style={{marginBottom:12}}>
              <div><strong>Event:</strong> {previewLetter.event_name}</div>
              <div><strong>Type:</strong> {previewLetter.event_type || 'N/A'}</div>
              <div><strong>Window:</strong> {previewLetter.event_summary || 'N/A'}</div>
              <div><strong>Start:</strong> {formatDateTime(previewLetter.start_datetime)}</div>
              <div><strong>End:</strong> {formatDateTime(previewLetter.end_datetime)}</div>
            </div>
            <div className="preview-html" dangerouslySetInnerHTML={{__html: previewLetter.content || '<p>No letter content provided.</p>'}} />
            <div style={{marginTop:12}}>
              <button className="btn small" onClick={()=>setPreviewLetter(null)}>Close Preview</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
