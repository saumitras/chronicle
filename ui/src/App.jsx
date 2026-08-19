import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { InvestigationList } from './pages/Investigations/List'
import { InvestigationDetail } from './pages/Investigations/Detail'
import { AlertList } from './pages/Alerts'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/investigations" element={<InvestigationList />} />
          <Route path="/investigations/:id" element={<InvestigationDetail />} />
          <Route path="/alerts" element={<AlertList />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
