import React, {useState, useEffect} from 'react'
import Login from './pages/Login'
import StudentPage from './pages/StudentPage'
import CoordinatorPage from './pages/CoordinatorPage'
import TeacherPage from './pages/TeacherPage'
import Layout from './components/Layout'

const decodeToken = (token) => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload
  } catch (e) {
    return null
  }
}

export default function App(){
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [user, setUser] = useState(token ? decodeToken(token) : null)

  useEffect(()=>{
    if(token){
      localStorage.setItem('token', token)
      setUser(decodeToken(token))
    }else{
      localStorage.removeItem('token')
      setUser(null)
    }
  },[token])

  if(!token) return <Login onLogin={setToken} />
  const role = user?.role || 'student'

  return (
    <Layout>
      <main>
        {role === 'student' && <StudentPage token={token} />}
        {role === 'coordinator' && <CoordinatorPage token={token} />}
        {role === 'teacher' && <TeacherPage token={token} />}
        {(role !== 'student' && role !== 'coordinator' && role !== 'teacher') && <div>Role: {role} — no UI implemented.</div>}
      </main>
    </Layout>
  )
}
