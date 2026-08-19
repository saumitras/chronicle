import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE })

export const getDashboardStats = () => api.get('/dashboard/stats').then(r => r.data)
export const getAlerts = (limit = 20) => api.get(`/alerts?limit=${limit}`).then(r => r.data)
export const getInvestigations = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return api.get(`/investigations${q ? '?' + q : ''}`).then(r => r.data)
}
export const getInvestigation = id => api.get(`/investigations/${id}`).then(r => r.data)
export const getInvestigationEvents = id => api.get(`/investigations/${id}/events`).then(r => r.data)
export const getPendingStatus = id => api.get(`/investigations/${id}/pending`).then(r => r.data)
export const submitDecision = (id, body) => api.post(`/investigations/${id}/approve`, body).then(r => r.data)
export const submitClarify = (id, body) => api.post(`/investigations/${id}/clarify`, body).then(r => r.data)
export const triggerReplay = () => api.post('/admin/replay').then(r => r.data)
export const generateAlert = (risk_profile = 'random') =>
  axios.post(`${import.meta.env.VITE_ALERT_URL || '/alert-api'}/alerts/generate?risk_profile=${risk_profile}`).then(r => r.data)
