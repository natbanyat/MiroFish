<template>
  <WorkflowShell
    v-model="viewMode"
    :current-step="5"
    step-name="Interaction"
    :status-class="statusClass"
    :status-text="statusText"
  >
    <template #left>
      <GraphPanel 
        :graphData="graphData"
        :loading="graphLoading"
        :currentPhase="5"
        :isSimulating="false"
        @refresh="refreshGraph"
        @toggle-maximize="toggleMaximize('graph')"
      />
    </template>

    <template #right>
      <div v-if="simulationId && !envAlive && !envChecking" class="env-banner">
        <span class="env-banner-text">Environment closed — all simulation data is saved.</span>
        <button
          class="env-reopen-btn"
          :disabled="envReopening"
          @click="reopenEnvironment"
        >
          {{ envReopening ? 'Reopening...' : 'Reopen for Interactions' }}
        </button>
      </div>
      <Step5Interaction
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
import Step5Interaction from '../components/Step5Interaction.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, getEnvStatus, reopenEnv } from '../api/simulation'
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
const currentStatus = ref('ready') // ready | processing | completed | error

// Environment status
const envAlive = ref(true) // optimistic until first check
const envChecking = ref(false)
const envReopening = ref(false)

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Completed'
  if (currentStatus.value === 'processing') return 'Processing'
  return 'Ready'
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

// Load simulation and project data given a simulation_id (used when no reportId)
const loadFromSimulation = async (simId) => {
  try {
    const simRes = await getSimulation(simId)
    if (simRes.success && simRes.data) {
      const simData = simRes.data
      if (simData.project_id) {
        const projRes = await getProject(simData.project_id)
        if (projRes.success && projRes.data) {
          projectData.value = projRes.data
          addLog(`Project loaded: ${projRes.data.project_id}`)
          if (projRes.data.graph_id) {
            await loadGraph(projRes.data.graph_id)
          }
        }
      }
    }
  } catch (err) {
    addLog(`Load from simulation error: ${err.message}`)
  }
}

// --- Data Logic ---
const loadReportData = async () => {
  // If no reportId, fall back to loading from simulation_id directly
  if (!currentReportId.value) {
    if (simulationId.value) {
      addLog(`No reportId, loading from simulation_id: ${simulationId.value}`)
      await loadFromSimulation(simulationId.value)
      injectHistParams()
      checkEnvStatus()
    }
    return
  }

  try {
    addLog(`Loading report data: ${currentReportId.value}`)

    // 获取 report 信息以获取 simulation_id
    const reportRes = await getReport(currentReportId.value)
    if (reportRes.success && reportRes.data) {
      const reportData = reportRes.data
      simulationId.value = reportData.simulation_id

      if (simulationId.value) {
        // 获取 simulation 信息
        const simRes = await getSimulation(simulationId.value)
        if (simRes.success && simRes.data) {
          const simData = simRes.data

          // 获取 project 信息
          if (simData.project_id) {
            const projRes = await getProject(simData.project_id)
            if (projRes.success && projRes.data) {
              projectData.value = projRes.data
              addLog(`Project loaded: ${projRes.data.project_id}`)

              // 获取 graph 数据
              if (projRes.data.graph_id) {
                await loadGraph(projRes.data.graph_id)
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
    addLog(`Load error: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded')
    }
  } catch (err) {
    addLog(`Graph load failed: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

// Check environment alive status
const checkEnvStatus = async () => {
  if (!simulationId.value) return
  envChecking.value = true
  try {
    const res = await getEnvStatus({ simulation_id: simulationId.value })
    envAlive.value = res.data?.env_alive ?? false
  } catch {
    envAlive.value = false
  } finally {
    envChecking.value = false
  }
}

// Reopen environment and poll until alive
const reopenEnvironment = async () => {
  if (!simulationId.value || envReopening.value) return
  envReopening.value = true
  addLog('Reopening simulation environment...')
  try {
    await reopenEnv({ simulation_id: simulationId.value })
    // Poll env-status until alive (up to 60s)
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 2000))
      try {
        const res = await getEnvStatus({ simulation_id: simulationId.value })
        if (res.data?.env_alive) {
          envAlive.value = true
          addLog('Environment is ready for interactions')
          break
        }
      } catch { /* keep polling */ }
    }
    if (!envAlive.value) {
      addLog('Environment startup timed out. Try again.')
    }
  } catch (e) {
    addLog(`Failed to reopen environment: ${e.message}`)
  } finally {
    envReopening.value = false
  }
}

// Watch route params
watch(() => route.params.reportId, (newId) => {
  if (newId && newId !== currentReportId.value) {
    currentReportId.value = newId
    loadReportData()
  }
}, { immediate: true })

// Also accept simulation_id directly from query params (e.g. from History Resume)
watch(simulationId, (id) => {
  if (id) checkEnvStatus()
})

onMounted(() => {
  addLog('InteractionView initialized')
  // Support direct simulation_id from query (History Resume flow)
  if (route.query.simulation_id && !simulationId.value) {
    simulationId.value = route.query.simulation_id
  }
  loadReportData()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  position: relative;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #E0E0E0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.ready .dot { background: #4CAF50; }
.status-indicator.processing .dot { background: #FF9800; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}

.env-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 20px;
  background: #FFF7ED;
  border-bottom: 1px solid #FED7AA;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
}

.env-banner-text {
  color: #92400E;
}

.env-reopen-btn {
  padding: 5px 14px;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  color: #FFFFFF;
  background: #92400E;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease;
}

.env-reopen-btn:hover:not(:disabled) {
  background: #78350F;
}

.env-reopen-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
