import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { installClientIdentityGlobal } from './shared/client-identity'
import './index.css'

installClientIdentityGlobal()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
