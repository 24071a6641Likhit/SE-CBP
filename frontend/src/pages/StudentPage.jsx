import React, {useState} from 'react'
import 'react-quill/dist/quill.snow.css'
import ReactQuill from 'react-quill'

export default function StudentPage({token}){
  const [eventName,setEventName] = useState('')
  const [start,setStart] = useState('')
  const [end,setEnd] = useState('')
  const [content,setContent] = useState('')
  const [msg,setMsg] = useState(null)

  async function submit(e){
    e.preventDefault()
    setMsg(null)
    try{
      // send the raw datetime-local string (local naive, no timezone) to match API contract
      const s = start
      const en = end
      const body = {student_roll: '24071A6601', student_name: 'Test Student', event_name: eventName, body: content, start_datetime: s, end_datetime: en}
      const res = await fetch('/api/letters', {method:'POST', headers:{'Content-Type':'application/json', 'Authorization': `Bearer ${token}`}, body: JSON.stringify(body)})
      // parse JSON safely and show friendly message
      let j = null
      try{
        j = await res.json()
      }catch(err){
        throw new Error('Server returned non-JSON response')
      }
      if(!res.ok){
        const detail = j.detail || j.message || j
        const msg = typeof detail === 'object' ? (detail.message || JSON.stringify(detail)) : String(detail)
        throw new Error(msg)
      }
      setMsg('Submitted — id: '+j.id)
      setEventName('')
      setStart('')
      setEnd('')
      setContent('')
    }catch(e){
      setMsg('Error: '+String(e))
    }
  }

  return (
    <div>
      <h2 className="card-title">Student Dashboard</h2>
      <div className="card">
        <div className="card-body">
          <form onSubmit={submit} className="form">
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
        <div className="card-body">(Not implemented in UI) — use API /api/letters to fetch past submissions.</div>
      </div>

      {msg && <div className="note">{msg}</div>}
    </div>
  )
}
