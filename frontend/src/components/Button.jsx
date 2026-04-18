import React from 'react'

export default function Button({children, onClick, className, disabled}){
  return <button className={"btn "+(className||"")} onClick={onClick} disabled={disabled}>{children}</button>
}
