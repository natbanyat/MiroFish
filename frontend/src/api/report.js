import service, { requestWithRetry } from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/generate', data), 3, 1000)
}

/**
 * 获取报告生成状态
 * Backend supports report_id, simulation_id, or task_id.
 * @param {Object} params - { report_id?, simulation_id?, task_id? }
 */
export const getReportStatus = (params = {}) => {
  return service.get(`/api/report/generate/status`, { params })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/chat', data), 3, 1000)
}

/**
 * Download report as PDF (or printable HTML fallback)
 * @param {string} reportId
 */
export const downloadReportPdf = async (reportId) => {
  const response = await service.get(`/api/report/${reportId}/pdf`, { responseType: 'blob' })
  const contentDisposition = response.headers?.['content-disposition'] || ''
  const contentType = response.headers?.['content-type'] || 'application/octet-stream'
  const isPdf = contentType.includes('pdf')
  const filename = isPdf ? `${reportId}.pdf` : `${reportId}_printable.html`
  const url = URL.createObjectURL(new Blob([response.data], { type: contentType }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
