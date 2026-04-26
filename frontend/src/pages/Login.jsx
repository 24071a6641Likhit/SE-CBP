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
    <section className="signup1-shell">
      <div className="signup1-center">
        <div className="signup1-card">
          <div className="signup1-head">
            <div className="signup1-logo-wrap" aria-hidden="true">
              <span className="signup1-logo-dot" />
              <span className="signup1-logo-text">College Event Attendance</span>
            </div>
            <h1>Sign in</h1>
            <p>Access your dashboard</p>
          </div>

          <form onSubmit={submit} className="signup1-form">
            <div className="signup1-field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                value={username}
                onChange={e=>setUsername(e.target.value)}
                placeholder="Enter your username"
                required
              />
            </div>
            <div className="signup1-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={e=>setPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>
            <button type="submit" className="signup1-primary-btn">Sign in</button>
            {err && <div className="error">{err}</div>}
          </form>

          <div className="signup1-footnote">
            Use maintainer/coordinator/teacher/student_test accounts (password: changeme)
          </div>
        </div>
      </div>
    </section>
  )
}
