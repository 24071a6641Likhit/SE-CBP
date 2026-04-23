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

  async function loadCurrentInfo(){
    try{
      const res = await fetch('/api/current_period', {headers:{'Authorization': `Bearer ${token}`}})
      if(!res.ok) return
      const j = await res.json()
      setCurrentInfo(j)
      if(j && j.period) setPeriod(j.period)
    }catch(_e){
      // ignore
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
    flushQueue().catch(()=>{})

    const onOnline = ()=>{ flushQueue().catch(()=>{}) }
    window.addEventListener('online', onOnline)

    const poll = setInterval(()=>{ load({clearMessage:false}) }, 20000)

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
          if(shouldReload) load({clearMessage:false})
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
  }, [date, period])

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

  function toggle(i){
    // prevent toggling if not current period
    if(currentInfo && period !== currentInfo.period){
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

      {msg && <div className="note">{msg}</div>}

      {!!notifications.length && (
        <div className="card">
          <div className="card-title">Notifications</div>
          <div className="card-body">
            {notifications.map(n => <div key={n.id} className="note">{n.text}</div>)}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">Attendance</div>
        <div className="card-body">
          <div className="table-wrapper">
            <table className="table">
              <thead><tr><th>Roll</th><th>Name</th><th>Present</th></tr></thead>
              <tbody>
                {rows.map((r,i)=>(
                  <tr key={r.student_roll}>
                    <td>{r.student_roll}</td>
                    <td>{r.student_name}</td>
                    <td>
                      <button onClick={()=>toggle(i)} className="btn" disabled={currentInfo && period !== currentInfo.period}>{r.mark}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{marginTop:12}}>
            <button onClick={save} className="btn" disabled={currentInfo && period !== currentInfo.period}>Save Changes</button>
          </div>
        </div>
      </div>
    </div>
  )
}
