import React from 'react'
import ReactDOM from 'react-dom/client'

// Reset first, then App.css so the theme tokens win on equal specificity.
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
