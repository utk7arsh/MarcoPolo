import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { createApiTransport } from './lib/transport'
import { DashboardStore } from './lib/store'
import { createDemoTransport } from './data/demo'
import './styles.css'

const demo =
  import.meta.env.VITE_DATA_SOURCE !== 'api' ? createDemoTransport() : undefined
const transport =
  demo || createApiTransport(import.meta.env.VITE_API_BASE_URL || '/api')
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App store={new DashboardStore(transport)} demo={demo} />
  </StrictMode>,
)
