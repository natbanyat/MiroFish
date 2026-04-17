<template>
  <WorkflowShell
    v-model="viewMode"
    :current-step="4"
    step-name="Report Generation"
    :status-class="statusClass"
    :status-text="statusText"
    :show-refresh="true"
    :refresh-disabled="graphLoading"
    @refresh="handleRefresh"
  >
    <template #left>
      <GraphPanel 
        :graphData="graphData"
        :loading="graphLoading"
        :currentPhase="4"
        :isSimulating="false"
        @refresh="refreshGraph"
        @toggle-maximize="toggleMaximize('graph')"
      />
    </template>

    <template #right>
      <Step4Report
        :reportId="currentReportId"
        :simulationId="simulationId"
        :systemLogs="systemLogs"
        @add-log="addLog"
        @update-status="updateStatus"
      />
    </template>
  </WorkflowShell>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkflowShell from '../components/WorkflowShell.vue'
import GraphPanel from '../components/GraphPanel.vue'
import Step4Report from '../components/Step4Report.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation } from '../api/simulation'
import { getReport } from '../api/report'
import { buildHistoryQuery, getRouteWorkflowIds } from '../workflow/history'

const route = useRoute()
const router = useRouter()

// Props
const props = defineProps({
  reportId: String
})

// Layout State - 默认切换到工作台视角
const viewMode = ref('workbench')

// Data State
const currentReportId = ref(route.params.reportId)
const simulationId = ref(null)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error
let activeReportLoadToken = 0

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Completed'
  return 'Generating'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 200) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// Silently enrich URL with hist_* params so StageNav has full context
// when this view is reached directly (e.g. from OperationsDashboard).
const injectHistParams = () => {
  const existing = getRouteWorkflowIds(route)
  const projectId = projectData.value?.project_id || existing.projectId
  const simId = simulationId.value || existing.simulationId
  const repId = currentReportId.value || existing.reportId

  if (
    projectId === existing.projectId &&
    simId === existing.simulationId &&
    repId === existing.reportId
  ) return

  const newQuery = { ...route.query }
  if (projectId) newQuery.hist_project_id = projectId
  if (simId) newQuery.hist_simulation_id = simId
  if (repId) newQuery.hist_report_id = repId
  router.replace({ name: route.name, params: route.params, query: newQuery })
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

// --- Data Logic ---
const isActiveReportLoad = (requestToken, reportId) => {
  return requestToken === activeReportLoadToken && currentReportId.value === reportId
}

const loadReportData = async (requestToken = activeReportLoadToken) => {
  const reportId = currentReportId.value
  if (!reportId) return

  try {
    addLog(`Loading report data: ${reportId}`)
    
    // 获取 report 信息以获取 simulation_id
    const reportRes = await getReport(reportId)
    if (!isActiveReportLoad(requestToken, reportId)) return

    if (reportRes.success && reportRes.data) {
      const reportData = reportRes.data
      simulationId.value = reportData.simulation_id
      
      if (simulationId.value) {
        // 获取 simulation 信息
        const simRes = await getSimulation(simulationId.value)
        if (!isActiveReportLoad(requestToken, reportId)) return

        if (simRes.success && simRes.data) {
          const simData = simRes.data
          
          // 获取 project 信息
          if (simData.project_id) {
            const projRes = await getProject(simData.project_id)
            if (!isActiveReportLoad(requestToken, reportId)) return

            if (projRes.success && projRes.data) {
              projectData.value = projRes.data
              addLog(`Project loaded: ${projRes.data.project_id}`)
              
              // 获取 graph 数据
              if (projRes.data.graph_id) {
                await loadGraph(projRes.data.graph_id, requestToken, reportId)
                if (!isActiveReportLoad(requestToken, reportId)) return
              }
            }
          }
        }
      }
      injectHistParams()
    } else {
      addLog(`Failed to load report info: ${reportRes.error || 'Unknown error'}`)
    }
  } catch (err) {
    if (isActiveReportLoad(requestToken, reportId)) {
      addLog(`Load error: ${err.message}`)
    }
  }
}

const loadGraph = async (graphId, requestToken = activeReportLoadToken, reportId = currentReportId.value) => {
  graphLoading.value = true

  try {
    const res = await getGraphData(graphId)
    if (!isActiveReportLoad(requestToken, reportId)) return

    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded')
    }
  } catch (err) {
    if (isActiveReportLoad(requestToken, reportId)) {
      addLog(`Graph load failed: ${err.message}`)
    }
  } finally {
    if (isActiveReportLoad(requestToken, reportId)) {
      graphLoading.value = false
    }
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

const handleRefresh = async () => {
  addLog('Manual view refresh triggered')
  activeReportLoadToken += 1
  await loadReportData(activeReportLoadToken)
}

// Watch route params — handles initial load (old === undefined) and component reuse (different
// reportId). Resets all stale state before loading so navigating between reports never flashes
// old status, graph, or simulationId from a previous visit.
watch(() => route.params.reportId, (newId, oldId) => {
  if (oldId !== undefined && newId === oldId) return

  activeReportLoadToken += 1
  const requestToken = activeReportLoadToken

  currentReportId.value = newId || null
  simulationId.value = null
  currentStatus.value = 'processing'
  projectData.value = null
  graphData.value = null
  graphLoading.value = false
  systemLogs.value = []
  loadReportData(requestToken)
}, { immediate: true })

onMounted(() => {
  addLog('ReportView initialized')
})
</script>

<style scoped>
</style>
