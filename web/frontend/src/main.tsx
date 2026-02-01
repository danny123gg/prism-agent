import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

console.log('[DEBUG] main.tsx loaded')
console.log('[DEBUG] root element:', document.getElementById('root'))

try {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
  console.log('[DEBUG] React render completed')
} catch (error) {
  console.error('[DEBUG] React render error:', error)
}
