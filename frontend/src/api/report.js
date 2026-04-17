import axios from 'axios'
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

export const getDecisionPathways = (reportId) => {
  return service.get(`/api/report/${reportId}/decision-pathways`)
}

/**
 * Regenerate a single section of an existing report (async).
 * @param {string} reportId
 * @param {number} sectionIndex - 1-based section number
 */
export const regenerateSection = (reportId, sectionIndex) => {
  return service.post(`/api/report/${reportId}/regenerate-section`, { section_index: sectionIndex })
}

const getFilenameFromDisposition = (headerValue, fallback) => {
  if (!headerValue) return fallback
  const utf8Match = headerValue.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1])
  const plainMatch = headerValue.match(/filename="?([^";]+)"?/i)
  if (plainMatch?.[1]) return plainMatch[1]
  return fallback
}

/**
 * Download report as PDF (or printable HTML fallback)
 * @param {string} reportId
 */
export const downloadReportPdf = async (reportId) => {
  const url = `${service.defaults.baseURL || ''}/api/report/${reportId}/pdf`

  try {
    const response = await axios.get(url, {
      responseType: 'blob',
      timeout: service.defaults.timeout,
    })

    const contentType = response.headers?.['content-type'] || 'application/octet-stream'
    const isPdf = contentType.includes('application/pdf')
    const fallbackName = isPdf ? `${reportId}.pdf` : `${reportId}_printable.html`
    const filename = getFilenameFromDisposition(response.headers?.['content-disposition'], fallbackName)
    const blob = new Blob([response.data], { type: contentType })
    const blobUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = blobUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(blobUrl)

    return {
      ok: true,
      filename,
      contentType,
      isPdf,
    }
  } catch (error) {
    const maybeBlob = error?.response?.data
    if (maybeBlob instanceof Blob) {
      const text = await maybeBlob.text()
      let parsed = null
      try {
        parsed = JSON.parse(text)
      } catch {
        parsed = null
      }
      throw new Error(parsed?.error || text || 'PDF download failed')
    }
    throw error
  }
}
