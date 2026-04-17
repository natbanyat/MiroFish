<template>
  <WorkflowShell
    v-model="viewMode"
    :current-step="5"
    step-name="Interaction"
    :status-class="statusClass"
    :status-text="statusText"
    :show-refresh="true"
    :refresh-disabled="graphLoading || envChecking || envReopening"
    @refresh="handleRefresh"
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
        <div class="env-banner-actions">
          <button
            class="env-reopen-btn"
            :disabled="envReopening"
            @click="reopenEnvironment"
          >
            {{ envReopening ? 'Reopening...' : 'Reopen for Interactions' }}
          </button>
          <button class="env-home-btn" @click="router.push('/')">
            New Simulation
          </button>
        </div>
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
  // If no reportId, fall back to loading from simulation_id directly.
  // Env status (single probe or poll-until-alive) is handled by watch(simulationId);
  // calling checkEnvStatus() here would race against pollEnvUntilAlive when reopen=1.
  if (!currentReportId.value) {
    if (simulationId.value) {
      addLog(`No reportId, loading from simulation_id: ${simulationId.value}`)
      await loadFromSimulation(simulationId.value)
      injectHistParams()
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

const handleRefresh = async () => {
  addLog('Manual view refresh triggered')
  if (currentReportId.value) {
    await loadReportData()
  } else if (simulationId.value) {
    await loadFromSimulation(simulationId.value)
  }
  await checkEnvStatus()
  refreshGraph()
}

// Check environment alive status (single probe)
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

// Poll env status until alive — used when a reopen was just triggered by the caller
// (e.g. StageNav or HistoryDatabase passed reopen=1 after calling reopenEnv).
// Keeps envChecking=true so the banner stays hidden while we wait.
// The first probe is immediate so that an already-alive env is confirmed without delay.
const pollEnvUntilAlive = async (simId) => {
  if (!simId) return
  envChecking.value = true
  addLog('Waiting for environment to come online...')
  try {
    for (let i = 0; i < 30; i++) {
      try {
        const res = await getEnvStatus({ simulation_id: simId })
        if (res.data?.env_alive) {
          envAlive.value = true
          addLog('Environment is ready for interactions')
          return
        }
      } catch { /* keep polling */ }
      await new Promise(r => setTimeout(r, 2000))
    }
    // Timed out — fall through and show banner
    addLog('Environment startup timed out.')
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

// Watch both the route param and simulation_id query so the view re-syncs when the
// component is reused for a different report/simulation via in-app navigation.
// On initial mount (old === undefined) the guard is skipped so the load always runs.
watch(
  () => [route.params.reportId, route.query.simulation_id],
  ([newReportId, newSimId], old) => {
    if (old !== undefined) {
      const [oldReportId, oldSimId] = old
      if (newReportId === oldReportId && newSimId === oldSimId) return
    }

    // Sync route context and reset stale state for the new session
    currentReportId.value = newReportId || null
    currentStatus.value = 'ready'
    systemLogs.value = []
    envAlive.value = true
    envChecking.value = false
    envReopening.value = false
    simulationId.value = null
    projectData.value = null
    graphData.value = null

    // Seed simulationId early so watch(simulationId) fires for env check/poll
    // before the full loadReportData() async chain completes.
    // Sources: simulation_id query param (also carries reopen=1), then hist_simulation_id.
    const earlySimId = newSimId || getRouteWorkflowIds(route).simulationId
    if (earlySimId) {
      simulationId.value = earlySimId
    }
    loadReportData()
  },
  { immediate: true }
)

// When simulationId is resolved (either from early seed or loadReportData chain),
// check env status. When reopen=1 the caller already triggered reopenEnv server-side;
// poll until alive rather than probing once to avoid a false "env closed" banner.
watch(simulationId, (id) => {
  if (id) {
    if (route.query.reopen === '1') {
      pollEnvUntilAlive(id)
    } else {
      checkEnvStatus()
    }
  }
})

onMounted(() => {
  addLog('InteractionView initialized')
})
</script>

<style scoped>
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

.env-banner-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.env-home-btn {
  padding: 5px 14px;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  color: #92400E;
  background: transparent;
  border: 1px solid #92400E;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.env-home-btn:hover {
  background: #92400E;
  color: #FFFFFF;
}
</style>
