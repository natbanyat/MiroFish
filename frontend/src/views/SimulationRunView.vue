<template>
  <WorkflowShell
    v-model="viewMode"
    :current-step="3"
    step-name="Run Simulation"
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
        :currentPhase="3"
        :isSimulating="isSimulating"
        @refresh="refreshGraph"
        @toggle-maximize="toggleMaximize('graph')"
      />
    </template>

    <template #right>
      <Step3Simulation
        :simulationId="currentSimulationId"
        :maxRounds="maxRounds"
        :minutesPerRound="minutesPerRound"
        :projectData="projectData"
        :graphData="graphData"
        :systemLogs="systemLogs"
        @go-back="handleGoBack"
        @next-step="handleNextStep"
        @add-log="addLog"
        @update-status="updateStatus"
      />
    </template>
  </WorkflowShell>
</template>

<script setup>
import { ref, computed, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkflowShell from '../components/WorkflowShell.vue'
import GraphPanel from '../components/GraphPanel.vue'
import Step3Simulation from '../components/Step3Simulation.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, getSimulationConfig, stopSimulation, closeSimulationEnv, getEnvStatus } from '../api/simulation'
import { generateReport } from '../api/report'
import { buildHistoryQuery, getRouteWorkflowIds } from '../workflow/history'

const route = useRoute()
const router = useRouter()

// Props
const props = defineProps({
  simulationId: String
})

// Layout State
const viewMode = ref('split')

// Data State
const currentSimulationId = ref(route.params.simulationId)
// 直接在初始化时从 query 参数获取 maxRounds，确保子组件能立即获取到值
const maxRounds = ref(route.query.maxRounds ? parseInt(route.query.maxRounds) : null)
const existingReportId = ref(null)
const minutesPerRound = ref(30) // 默认每轮30分钟
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const simulationStatus = ref({
  status: 'processing',
  runnerStatus: 'idle',
  progressPercent: 0,
  currentRound: 0,
  totalRounds: 0
})

const workflowIds = computed(() => getRouteWorkflowIds(route))
const histQuery = computed(() => buildHistoryQuery({
  projectId: projectData.value?.project_id || workflowIds.value.projectId,
  simulationId: currentSimulationId.value || workflowIds.value.simulationId,
  reportId: existingReportId.value || workflowIds.value.reportId,
}))

// --- Status Computed ---
const normalizedStatus = computed(() => {
  return simulationStatus.value.status || 'processing'
})

const normalizedProgressPercent = computed(() => {
  const value = Number(simulationStatus.value.progressPercent || 0)
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0
})

const normalizedRoundSummary = computed(() => {
  const currentRound = Number(simulationStatus.value.currentRound || 0)
  const totalRounds = Number(simulationStatus.value.totalRounds || maxRounds.value || 0)
  if (!currentRound || !totalRounds) return ''
  return ' · R' + currentRound + '/' + totalRounds
})

const statusClass = computed(() => normalizedStatus.value)

const statusText = computed(() => {
  if (normalizedStatus.value === 'error') return 'Error'
  if (normalizedStatus.value === 'completed') return 'Completed'
  const progressLabel = normalizedProgressPercent.value > 0 ? ' · ' + normalizedProgressPercent.value.toFixed(1) + '%' : ''
  return 'Running' + progressLabel + normalizedRoundSummary.value
})

const isSimulating = computed(() => normalizedStatus.value === 'processing')

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 200) {
    systemLogs.value.shift()
  }
}

const updateStatus = (statusUpdate) => {
  if (typeof statusUpdate === 'string') {
    simulationStatus.value = {
      ...simulationStatus.value,
      status: statusUpdate
    }
    return
  }

  simulationStatus.value = {
    ...simulationStatus.value,
    ...(statusUpdate || {})
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleGoBack = async () => {
  // 在返回 Step 2 之前，先关闭正在运行的模拟
  addLog('Returning to Step 2. Closing the simulation...')
  
  // 停止轮询
  stopGraphRefresh()
  
  try {
    // 先尝试优雅关闭模拟环境
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })
    
    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog('Closing simulation environment...')
      try {
        await closeSimulationEnv({ 
          simulation_id: currentSimulationId.value,
          timeout: 10
        })
        addLog('✓ Simulation environment closed')
      } catch (closeErr) {
        addLog('Failed to close environment. Trying force-stop...')
        try {
          await stopSimulation({ simulation_id: currentSimulationId.value })
          addLog('✓ Simulation force-stopped')
        } catch (stopErr) {
          addLog(`Force-stop failed: ${stopErr.message}`)
        }
      }
    } else {
      // 环境未运行，检查是否需要停止进程
      if (isSimulating.value) {
        addLog('Stopping simulation process...')
        try {
          await stopSimulation({ simulation_id: currentSimulationId.value })
          addLog('✓ Simulation stopped')
        } catch (err) {
          addLog(`Stop failed: ${err.message}`)
        }
      }
    }
  } catch (err) {
    addLog(`Failed to check simulation status: ${err.message}`)
  }
  
  // 返回到 Step 2 (环境搭建)
  router.push({
    name: 'Simulation',
    params: { simulationId: currentSimulationId.value },
    query: histQuery.value,
  })
}

const handleNextStep = () => {
  // Step3Simulation 组件会直接处理报告生成和路由跳转
  // 这个方法仅作为备用
  addLog('Entering Step 4: Report Generation')
}

// Silently enrich URL with hist_* params so StageNav has full context
// when this view is reached directly (e.g. from OperationsDashboard).
const injectHistParams = () => {
  const existing = getRouteWorkflowIds(route)
  const projectId = projectData.value?.project_id || existing.projectId
  const simId = currentSimulationId.value || existing.simulationId
  const repId = existingReportId.value || existing.reportId

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

// --- Data Logic ---
const loadSimulationData = async () => {
  try {
    addLog(`Loading simulation data: ${currentSimulationId.value}`)
    
    // 获取 simulation 信息
    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data

      updateStatus({
        status: simData.status === 'failed' ? 'error' : (simData.status === 'completed' ? 'completed' : (simData.runner_status === 'failed' ? 'error' : (['completed', 'stopped'].includes(simData.runner_status) ? 'completed' : 'processing'))),
        runnerStatus: simData.runner_status || simData.status || 'idle',
        progressPercent: simData.progress_percent || 0,
        currentRound: simData.current_round || 0,
        totalRounds: simData.total_rounds || maxRounds.value || 0
      })

      // If simulation is already completed, probe for an existing report so that
      // hist_report_id is injected into the URL and StageNav Step 4 becomes enabled.
      if (simData.status === 'completed' || ['completed', 'stopped'].includes(simData.runner_status)) {
        try {
          const reportCheck = await generateReport({ simulation_id: currentSimulationId.value, force_regenerate: false })
          if (reportCheck.success && reportCheck.data?.already_generated && reportCheck.data?.report_id) {
            existingReportId.value = reportCheck.data.report_id
            addLog(`Existing report found: ${reportCheck.data.report_id}`)
          }
        } catch (e) {
          // Non-blocking — ignore if report check fails
        }
      }

      // 获取 simulation config 以获取 minutes_per_round
      try {
        const configRes = await getSimulationConfig(currentSimulationId.value)
        if (configRes.success && configRes.data?.time_config?.minutes_per_round) {
          minutesPerRound.value = configRes.data.time_config.minutes_per_round
          addLog(`Timing config: ${minutesPerRound.value} minutes per round`)
        }
      } catch (configErr) {
        addLog(`Failed to load timing config. Using default: ${minutesPerRound.value} min/round`)
      }
      
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

      injectHistParams()
    } else {
      addLog(`Failed to load simulation data: ${simRes.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Load error: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  // 当正在模拟时，自动刷新不显示全屏 loading，以免闪烁
  // 手动刷新或初始加载时显示 loading
  if (!isSimulating.value) {
    graphLoading.value = true
  }
  
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      if (!isSimulating.value) {
        addLog('Graph data loaded')
      }
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
  await loadSimulationData()
  refreshGraph()
}

// --- Auto Refresh Logic ---
let graphRefreshTimer = null

const startGraphRefresh = () => {
  if (graphRefreshTimer) return
  addLog('Started live graph refresh (30s)')
  // 立即刷新一次，然后每30秒刷新
  graphRefreshTimer = setInterval(refreshGraph, 30000)
}

const stopGraphRefresh = () => {
  if (graphRefreshTimer) {
    clearInterval(graphRefreshTimer)
    graphRefreshTimer = null
    addLog('Stopped live graph refresh')
  }
}

watch(isSimulating, (newValue) => {
  if (newValue) {
    startGraphRefresh()
  } else {
    stopGraphRefresh()
  }
}, { immediate: true })

// Keep maxRounds in sync when only the query changes (same simulationId, different round
// count). The simulationId watch handles initial mount and simulationId changes; this covers
// the Step2 -> Step3 reuse case where the user adjusts maxRounds on the same simulation.
watch(() => route.query.maxRounds, (newVal) => {
  maxRounds.value = newVal ? parseInt(newVal) : null
})

// Reset stale state when the component is reused with a different simulationId
watch(() => route.params.simulationId, (newId, oldId) => {
  if (oldId !== undefined && newId === oldId) return

  // Stop any running timers from the previous simulation
  stopGraphRefresh()

  // Reset all state
  currentSimulationId.value = newId || null
  maxRounds.value = route.query.maxRounds ? parseInt(route.query.maxRounds) : null
  existingReportId.value = null
  minutesPerRound.value = 30
  projectData.value = null
  graphData.value = null
  graphLoading.value = false
  systemLogs.value = []
  simulationStatus.value = {
    status: 'processing',
    runnerStatus: 'idle',
    progressPercent: 0,
    currentRound: 0,
    totalRounds: 0
  }

  addLog('SimulationRunView initialized')
  if (maxRounds.value) {
    addLog(`Custom simulation rounds: ${maxRounds.value}`)
  }
  loadSimulationData()
}, { immediate: true })

onUnmounted(() => {
  stopGraphRefresh()
})
</script>

<style scoped>
</style>
