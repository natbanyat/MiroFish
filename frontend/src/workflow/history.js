export function getRouteWorkflowIds(route) {
  const query = route?.query || {}
  const params = route?.params || {}

  return {
    projectId: query.hist_project_id || params.projectId || null,
    simulationId: query.hist_simulation_id || query.simulation_id || params.simulationId || null,
    reportId: query.hist_report_id || params.reportId || null,
  }
}

export function buildHistoryQuery(ids = {}) {
  return {
    hist_project_id: ids.projectId || undefined,
    hist_simulation_id: ids.simulationId || undefined,
    hist_report_id: ids.reportId || undefined,
  }
}
