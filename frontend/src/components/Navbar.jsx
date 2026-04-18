import React from 'react'

export default function Navbar(){
  const username = localStorage.getItem('token') ? (()=>{try{return JSON.parse(atob(localStorage.getItem('token').split('.')[1])).sub}catch(e){return ''}})() : ''
  return (
    <header className="site-header">
      <div className="container header-inner">
        <div className="brand">College Attendance</div>
        <nav className="nav">
          <button className="btn small" onClick={()=>{localStorage.removeItem('token'); window.location.reload()}}>Logout</button>
        </nav>
      </div>
    </header>
  )
}
