import React, {useState, useEffect} from 'react'

export default function CoordinatorPage({token}){
  const [letters,setLetters] = useState([])
  const [err,setErr] = useState(null)

  async function load(){
    setErr(null)
    try{
      const res = await fetch('/api/letters?status=Submitted', {headers:{'Authorization': `Bearer ${token}`}})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      setLetters(j)
    }catch(e){
      setErr(String(e))
    }
  }

  useEffect(()=>{load()}, [])

  async function approve(id){
    try{
      const res = await fetch(`/api/letters/${id}/approve`, {method:'POST', headers:{'Authorization': `Bearer ${token}`}})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      load()
      alert('Approved')
    }catch(e){alert('Error: '+e)}
  }

  async function reject(id){
    const comment = prompt('Rejection comment (optional)')
    try{
      const res = await fetch(`/api/letters/${id}/reject`, {method:'POST', headers:{'Authorization': `Bearer ${token}`, 'Content-Type':'application/json'}, body: JSON.stringify({comment})})
      const j = await res.json()
      if(!res.ok) throw new Error(JSON.stringify(j))
      load()
      alert('Rejected')
    }catch(e){alert('Error: '+e)}
  }

  return (
    <div>
      <h2>Coordinator — Inbox</h2>
      <button onClick={load}>Refresh</button>
      {err && <div className="error">{err}</div>}
      <table className="table">
        <thead><tr><th>Roll</th><th>Name</th><th>Event</th><th>Start</th><th>End</th><th>Actions</th></tr></thead>
        <tbody>
          {letters.map(l => (
            <tr key={l.id}><td>{l.student_roll}</td><td>{l.student_name}</td><td>{l.event_name}</td><td>{l.start_datetime}</td><td>{l.end_datetime}</td><td><button onClick={()=>approve(l.id)}>Approve</button> <button onClick={()=>reject(l.id)}>Reject</button></td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
