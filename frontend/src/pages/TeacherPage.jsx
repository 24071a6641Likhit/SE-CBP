import React, {useState, useEffect} from 'react'

export default function TeacherPage({token}){
  const [date,setDate] = useState(new Date().toISOString().slice(0,10))
  const [period,setPeriod] = useState(3)
  const [rows,setRows] = useState([])
  const [msg,setMsg] = useState(null)
  const [currentInfo,setCurrentInfo] = useState(null)
  const [nowTime,setNowTime] = useState(new Date())

  useEffect(()=>{
    // update clock
    const t = setInterval(()=> setNowTime(new Date()), 1000);
    // fetch current period info
    (async ()=>{
      try{
        const res = await fetch('/api/current_period', {headers:{'Authorization': `Bearer ${token}`}})
        if(!res.ok) return
        const j = await res.json()
        setCurrentInfo(j)
        if(j && j.period) setPeriod(j.period)
      }catch(e){/* ignore */}
    })()
    return ()=> clearInterval(t)
  }, [token])

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
    try{
      const res = await fetch('/api/attendance', {method:'POST', headers:{'Authorization': `Bearer ${token}`, 'Content-Type':'application/json'}, body: JSON.stringify({updates})})
      let j = null
      try{ j = await res.json() }catch(err){ j = null }
      if(!res.ok){
        // handle version conflict specially
        if(res.status === 409){
          setMsg('Version conflict detected — reloading latest attendance...')
          await load()
          return
        }
        const detail = j && (j.detail || j.message) ? (j.detail || j.message) : (j || 'Unknown error')
        throw new Error(typeof detail === 'object' ? JSON.stringify(detail) : String(detail))
      }
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
    }catch(e){setMsg('Error: '+e)}
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

      {msg && <div className="note">{msg}</div>}

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
