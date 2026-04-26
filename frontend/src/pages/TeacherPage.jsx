import React, {useState, useEffect} from 'react'

const SAVE_QUEUE_KEY = 'teacher_attendance_queue_v1'

function readQueue() {
  try {
    const raw = localStorage.getItem(SAVE_QUEUE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch (_err) {
    return []
  }
}

function writeQueue(items) {
  localStorage.setItem(SAVE_QUEUE_KEY, JSON.stringify(items))
}

export default function TeacherPage({token}){
  const [date,setDate] = useState(new Date().toISOString().slice(0,10))
  const [period,setPeriod] = useState(3)
  const [rows,setRows] = useState([])
  const [msg,setMsg] = useState(null)
  const [currentInfo,setCurrentInfo] = useState(null)
  const [nowTime,setNowTime] = useState(new Date())
  const [syncStatus,setSyncStatus] = useState('Synced')
  const [notifications,setNotifications] = useState([])
  const [activeTab,setActiveTab] = useState('attendance')
  const [selectedLetter,setSelectedLetter] = useState(null)
  const [letterBuckets,setLetterBuckets] = useState({})
  const [letterList,setLetterList] = useState([])
  const [sectionFilter,setSectionFilter] = useState('')
  const [rollFilter,setRollFilter] = useState('')
  const [letterStatusFilter,setLetterStatusFilter] = useState('Approved')

  const isCurrentPeriodSelected = !currentInfo || Number(period) === Number(currentInfo.period)

  function formatDateTime(value){
    if(!value) return 'N/A'
    const dt = new Date(value)
    if(Number.isNaN(dt.getTime())) return value
    return dt.toLocaleString()
  }

  async function loadCurrentInfo(){
    try{
      const res = await fetch('/api/current_period', {headers:{'Authorization': `Bearer ${token}`}})
      if(!res.ok) return null
      const j = await res.json()
      setCurrentInfo(j)
      if(j && j.period) setPeriod(j.period)
      return j
    }catch(_e){
      // ignore
      return null
    }
  }

  async function loadLetterBuckets(){
    try{
      const q = new URLSearchParams()
      q.set('date', date)
      q.set('period', String(period))
      if(sectionFilter.trim()) q.set('section', sectionFilter.trim())
      if(rollFilter.trim()) q.set('roll', rollFilter.trim())
      if(letterStatusFilter) q.set('status', letterStatusFilter)
      const res = await fetch(`/api/teacher/letters?${q.toString()}`, {headers:{'Authorization': `Bearer ${token}`}})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      setLetterBuckets(j.buckets || {})
      setLetterList(j.letters || [])
    }catch(e){
      setMsg(String(e))
    }
  }

  async function runSave(payload){
    const res = await fetch('/api/attendance', {
      method:'POST',
      headers:{'Authorization': `Bearer ${token}`, 'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    })
    let j = null
    try{ j = await res.json() }catch(_err){ j = null }
    if(!res.ok){
      const detail = j && (j.detail || j.message) ? (j.detail || j.message) : (j || 'Unknown error')
      const message = typeof detail === 'object' ? JSON.stringify(detail) : String(detail)
      const err = new Error(message)
      err.status = res.status
      throw err
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
    setSyncStatus(`Syncing ${queued.length} queued save(s)...`)
    const remaining = []
    for(const item of queued){
      try{
        await runSave(item)
      }catch(_err){
        remaining.push(item)
      }
    }
    writeQueue(remaining)
    setSyncStatus(remaining.length ? `${remaining.length} queued save(s) pending` : 'Synced')
    await load()
  }

  useEffect(()=>{
    // update clock
    const t = setInterval(()=> setNowTime(new Date()), 1000);

    loadCurrentInfo()
    load()
    loadLetterBuckets()
    flushQueue().catch(()=>{})

    const onOnline = ()=>{ flushQueue().catch(()=>{}) }
    window.addEventListener('online', onOnline)

    const poll = setInterval(()=>{
      loadCurrentInfo()
      load({clearMessage:false})
    }, 20000)

    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${wsProto}://${window.location.host}/ws?token=${encodeURIComponent(token)}`)
    ws.onmessage = (evt) => {
      try{
        const data = JSON.parse(evt.data)
        if(data?.requires_ack && data?.id){
          ws.send(JSON.stringify({type:'ack', id:data.id}))
        }
        if(data?.type === 'letter.approved'){
          setNotifications(prev => [
            {id: data.id || String(Date.now()), text: `Approval received for ${data?.payload?.student_roll || 'student'}`},
            ...prev,
          ].slice(0, 8))
          const affected = Array.isArray(data?.payload?.affected_periods) ? data.payload.affected_periods : []
          const shouldReload = affected.some(a => a?.date === date && Number(a?.period_index) === Number(period))
          if(shouldReload){
            load({clearMessage:false})
            loadLetterBuckets()
          }
        }
        if(data?.type === 'attendance.updated'){
          load({clearMessage:false})
        }
      }catch(_err){
        // ignore malformed ws message
      }
    }

    return ()=>{
      clearInterval(t)
      clearInterval(poll)
      window.removeEventListener('online', onOnline)
      ws.close()
    }
  }, [token])

  useEffect(()=>{
    load({clearMessage:false})
    loadLetterBuckets()
  }, [date, period])

  useEffect(()=>{
    loadLetterBuckets()
  }, [sectionFilter, rollFilter, letterStatusFilter])

  async function load({clearMessage = true} = {}){
    if (clearMessage) setMsg(null)
    try{
      const res = await fetch(`/api/attendance?date=${date}&period=${period}`, {headers:{'Authorization': `Bearer ${token}`}})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      // ensure rows have version (backend provides it)
      setRows(j.map(r => ({...r, version: r.version || null})))
    }catch(e){setMsg(String(e))}
  }

  async function save(){
    const latestCurrentInfo = await loadCurrentInfo()
    const effectivePeriod = latestCurrentInfo ? Number(latestCurrentInfo.period) : Number(currentInfo?.period)
    if(effectivePeriod && Number(period) !== effectivePeriod){
      setMsg('Cannot edit: not current period')
      return
    }
    const updates = rows.map(r=>({student_roll: r.student_roll, date, period_index: period, mark: r.mark, version: r.version || 1}))
    const payload = {updates}
    try{
      if(!navigator.onLine){
        const queued = readQueue()
        queued.push(payload)
        writeQueue(queued)
        setSyncStatus(`${queued.length} queued save(s) pending`)
        setMsg('Offline: attendance changes queued and will sync automatically')
        return
      }

      const j = await runSave(payload)
      await load({clearMessage: false})
      const updated = j && typeof j.updated === 'number' ? j.updated : updates.length
      const warningCount = j && Array.isArray(j.warnings) ? j.warnings.length : 0
      if (warningCount === updated && updated > 0) {
        setMsg(`Updated ${updated} existing attendance record${updated === 1 ? '' : 's'}`)
      } else if (warningCount > 0) {
        setMsg(`Saved ${updated} attendance record${updated === 1 ? '' : 's'} (${warningCount} updated)`)
      } else {
        setMsg(`Saved ${updated} attendance record${updated === 1 ? '' : 's'}`)
      }
    }catch(e){
      if(e?.status === 409){
        setMsg('Version conflict detected - reloading latest attendance...')
        await load()
        return
      }
      setMsg('Error: '+e)
    }
  }

  async function markFromLetters(letter, mark){
    const latestCurrentInfo = await loadCurrentInfo()
    const effectivePeriod = latestCurrentInfo ? Number(latestCurrentInfo.period) : Number(currentInfo?.period)
    if(effectivePeriod && Number(period) !== effectivePeriod){
      setMsg('Cannot edit: not current period')
      return
    }

    const existing = rows.find(r => r.student_roll === letter.student_roll)
    const payload = {
      updates: [{
        student_roll: letter.student_roll,
        date,
        period_index: period,
        mark,
        version: existing?.version || 1,
      }],
    }

    try{
      if(!navigator.onLine){
        const queued = readQueue()
        queued.push(payload)
        writeQueue(queued)
        setSyncStatus(`${queued.length} queued save(s) pending`)
        setMsg(`Offline: queued ${letter.student_roll} as ${mark}`)
        return
      }

      await runSave(payload)
      await load({clearMessage:false})
      setMsg(`Marked ${letter.student_roll} as ${mark} for P${period} on ${date}`)
    }catch(e){
      if(e?.status === 409){
        setMsg('Version conflict detected - reloading latest attendance...')
        await load()
        return
      }
      setMsg('Error: '+e)
    }
  }

  function toggle(i){
    // prevent toggling if not current period
    if(currentInfo && Number(period) !== Number(currentInfo.period)){
      setMsg('Cannot edit: not current period')
      return
    }
    const copy = rows.slice();
    copy[i].mark = copy[i].mark === 'Present' ? 'Absent' : 'Present'
    setRows(copy)
  }

  return (
    <div>
      <h2 className="card-title">Teacher Dashboard</h2>
      <div className="card" style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div>
          <div style={{fontSize:14,color:'#555'}}>Time</div>
          <div style={{fontWeight:700,fontSize:18}}>{nowTime.toLocaleTimeString()}</div>
        </div>
        <div>
          <div style={{fontSize:14,color:'#555'}}>Current Period</div>
          <div style={{fontWeight:700,fontSize:18}}>{currentInfo ? currentInfo.period : '—'}</div>
        </div>
        <div>
          <div style={{fontSize:14,color:'#555'}}>Subject</div>
          <div style={{fontWeight:700,fontSize:18}}>{currentInfo && currentInfo.subject ? (currentInfo.subject.name || currentInfo.subject.code) : '—'}</div>
        </div>
        <div>
          <button className="btn small" onClick={load}>Load</button>
        </div>
      </div>

      <div className="card">
        <div className="form-inline">
          <label>Date
            <input type="date" value={date} onChange={e=>setDate(e.target.value)} />
          </label>
          <label>Period
            <select value={period} onChange={e=>setPeriod(Number(e.target.value))}>
              <option value={1}>P1</option>
              <option value={2}>P2</option>
              <option value={3}>P3</option>
              <option value={4}>P4</option>
              <option value={5}>P5</option>
              <option value={6}>P6</option>
            </select>
          </label>
          <div className="note">Sync status: {syncStatus}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-body">
          <div className="form-inline">
            <button className={"btn small "+(activeTab === 'attendance' ? '' : 'outline')} onClick={()=>setActiveTab('attendance')}>Attendance</button>
            <button className={"btn small "+(activeTab === 'letters' ? '' : 'outline')} onClick={()=>setActiveTab('letters')}>Permission Letters (Section Buckets)</button>
          </div>
        </div>
      </div>

      {msg && <div className="note">{msg}</div>}

      {!!notifications.length && (
        <div className="card">
          <div className="card-title">Notifications</div>
          <div className="card-body">
            {notifications.map(n => <div key={n.id} className="note">{n.text}</div>)}
          </div>
        </div>
      )}

      {activeTab === 'attendance' && (
        <div className="card">
          <div className="card-title">Attendance</div>
          <div className="card-body">
            <div className="table-wrapper">
              <table className="table">
                <thead><tr><th>Roll</th><th>Name</th><th>Section</th><th>Letter</th><th>Present</th></tr></thead>
                <tbody>
                  {rows.map((r,i)=>(
                    <tr key={r.student_roll}>
                      <td>{r.student_roll}</td>
                      <td>{r.student_name}</td>
                      <td>{r.section || 'N/A'}</td>
                      <td>
                        {r.has_permission_letter ? (
                          <button className="btn small" onClick={()=>setSelectedLetter(r.permission_letter)} title="View permission letter">Has permission letter</button>
                        ) : (
                          <span style={{color:'#888'}}>No letter</span>
                        )}
                      </td>
                      <td>
                        <button onClick={()=>toggle(i)} className="btn" disabled={!isCurrentPeriodSelected}>{r.mark}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{marginTop:12}}>
              <button onClick={save} className="btn" disabled={!isCurrentPeriodSelected}>Save Changes</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'letters' && (
        <div className="card">
          <div className="card-title">Permission Letters by Section</div>
          <div className="card-body">
            <div className="form-inline" style={{marginBottom:12}}>
              <label>Section
                <input value={sectionFilter} onChange={e=>setSectionFilter(e.target.value)} placeholder="A66 / CSE-A" />
              </label>
              <label>Roll
                <input value={rollFilter} onChange={e=>setRollFilter(e.target.value)} placeholder="24071A66xx" />
              </label>
              <label>Status
                <select value={letterStatusFilter} onChange={e=>setLetterStatusFilter(e.target.value)}>
                  <option value="Approved">Approved</option>
                  <option value="">All</option>
                  <option value="Submitted">Submitted</option>
                  <option value="Rejected">Rejected</option>
                </select>
              </label>
              <button className="btn small" onClick={loadLetterBuckets}>Apply</button>
            </div>

            {!letterList.length && <div className="note">No permission letters for selected filters.</div>}

            {Object.keys(letterBuckets).sort().map(section => (
              <div key={section} style={{marginBottom:16}}>
                <h4 style={{margin:'0 0 8px 0'}}>Section {section}</h4>
                <div className="table-wrapper">
                  <table className="table">
                    <thead><tr><th>Roll</th><th>Name</th><th>Event</th><th>Window</th><th>Status</th><th>Preview</th><th>Mark</th></tr></thead>
                    <tbody>
                      {letterBuckets[section].map(l => (
                        <tr key={l.id}>
                          <td>{l.student_roll}</td>
                          <td>{l.student_name}</td>
                          <td>{l.event_name}</td>
                          <td>{l.event_summary || 'N/A'}</td>
                          <td>{l.status}</td>
                          <td><button className="btn small" onClick={()=>setSelectedLetter(l)}>View</button></td>
                          <td>
                            <button className="btn small" onClick={()=>markFromLetters(l, 'Present')} disabled={!isCurrentPeriodSelected}>Present</button>{' '}
                            <button className="btn small outline" onClick={()=>markFromLetters(l, 'Absent')} disabled={!isCurrentPeriodSelected}>Absent</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedLetter && (
        <div className="card">
          <div className="card-title">Permission Letter Preview</div>
          <div className="card-body">
            <div className="form-inline" style={{marginBottom:12}}>
              <div><strong>Event:</strong> {selectedLetter.event_name}</div>
              <div><strong>Type:</strong> {selectedLetter.event_type || 'N/A'}</div>
              <div><strong>Window:</strong> {selectedLetter.event_summary || 'N/A'}</div>
              <div><strong>Coordinator verified at:</strong> {formatDateTime(selectedLetter.approved_at)}</div>
            </div>
            <div className="preview-html" dangerouslySetInnerHTML={{__html: selectedLetter.content || '<p>No letter content provided.</p>'}} />
            <div style={{marginTop:12}}>
              <button className="btn small" onClick={()=>setSelectedLetter(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
