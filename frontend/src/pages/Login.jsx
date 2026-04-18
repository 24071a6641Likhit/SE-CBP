import React, {useState} from 'react'

export default function Login({onLogin}){
  const [username,setUsername] = useState('')
  const [password,setPassword] = useState('')
  const [err,setErr] = useState(null)

  async function submit(e){
    e.preventDefault()
    setErr(null)
    try{
      const res = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username,password})})
      if(!res.ok) throw new Error(await res.text())
      const j = await res.json()
      onLogin(j.access_token)
    }catch(e){
      setErr(String(e))
    }
  }

  return (
    <div className="login">
      <h2>Sign in</h2>
      <form onSubmit={submit}>
        <div>
          <label>Username</label>
          <input value={username} onChange={e=>setUsername(e.target.value)} />
        </div>
        <div>
          <label>Password</label>
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} />
        </div>
        <div>
          <button type="submit">Sign in</button>
        </div>
        {err && <div className="error">{err}</div>}
      </form>
      <div className="note">Use maintainer/coordinator/teacher/student_test accounts (password: changeme)</div>
    </div>
  )
}
