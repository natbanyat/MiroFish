<template>
  <WorkflowShell
    v-model="viewMode"
    :current-step="2"
    step-name="Environment Setup"
    :status-class="statusClass"
    :status-text="statusText"
    right-panel-class="simulation-view-right"
  >
    <template #left>
      <GraphPanel 
        :graphData="graphData"
        :loading="graphLoading"
        :currentPhase="2"
        @refresh="refreshGraph"
        @toggle-maximize="toggleMaximize('graph')"
      />
    </template>

    <template #right>
      <div v-if="existingReportId" class="resume-banner">
        <div class="resume-banner-left">
          <span class="resume-icon">◆</span>
          <div>
            <div class="resume-title">Report Already Generated</div>
            <div class="resume-sub">A completed report exists for this simulation.</div>
          </div>
        </div>
        <button class="resume-view-btn" @click="openExistingReport">
          View Report →
        </button>
      </div>
      <Step2EnvSetup
        :simulationId="currentSimulationId"
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkflowShell from '../components/WorkflowShell.vue'
import GraphPanel from '../components/GraphPanel.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, stopSimulation, getEnvStatus, closeSimulationEnv } from '../api/simulation'
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
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error
const existingReportId = ref(null) // set if a completed report already exists

const workflowIds = computed(() => getRouteWorkflowIds(route))
const histQuery = computed(() => buildHistoryQuery({
  projectId: projectData.value?.project_id || workflowIds.value.projectId,
  simulationId: currentSimulationId.value || workflowIds.value.simulationId,
  reportId: existingReportId.value || workflowIds.value.reportId,
}))

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

const openExistingReport = () => {
  if (!existingReportId.value) return
  router.push({
    name: 'Report',
    params: { reportId: existingReportId.value },
    query: histQuery.value,
  })
}

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Ready'
  return 'Preparing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleGoBack = () => {
  // 返回到 process 页面
  if (projectData.value?.project_id) {
    router.push({
      name: 'Process',
      params: { projectId: projectData.value.project_id },
      query: histQuery.value,
    })
  } else {
    router.push('/')
  }
}

const handleNextStep = (params = {}) => {
  addLog('Entering Step 3: Run Simulation')
  
  // 记录模拟轮数配置
  if (params.maxRounds) {
    addLog(`Custom simulation rounds: ${params.maxRounds}`)
  } else {
    addLog('Using auto-configured simulation rounds')
  }
  
  // 构建路由参数
  const routeParams = {
    name: 'SimulationRun',
    params: { simulationId: currentSimulationId.value },
    query: { ...histQuery.value }
  }
  
  // 如果有自定义轮数，通过 query 参数传递
  if (params.maxRounds) {
    routeParams.query.maxRounds = params.maxRounds
  }
  
  // 跳转到 Step 3 页面
  router.push(routeParams)
}

// --- Data Logic ---

/**
 * 检查并关闭正在运行的模拟
 * 当用户从 Step 3 返回到 Step 2 时，默认用户要退出模拟
 */
const checkAndStopRunningSimulation = async () => {
  if (!currentSimulationId.value) return
  
  try {
    // 先检查模拟环境是否存活
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })
    
    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog('Detected a running simulation environment. Closing it...')
      
      // 尝试优雅关闭模拟环境
      try {
        const closeRes = await closeSimulationEnv({ 
          simulation_id: currentSimulationId.value,
          timeout: 10  // 10秒超时
        })
        
        if (closeRes.success) {
          addLog('✓ Simulation environment closed')
        } else {
          addLog(`Failed to close simulation environment: ${closeRes.error || 'Unknown error'}`)
          // 如果优雅关闭失败，尝试强制停止
          await forceStopSimulation()
        }
      } catch (closeErr) {
        addLog(`Simulation environment close error: ${closeErr.message}`)
        // 如果优雅关闭异常，尝试强制停止
        await forceStopSimulation()
      }
    } else {
      // 环境未运行，但可能进程还在，检查模拟状态
      const simRes = await getSimulation(currentSimulationId.value)
      if (simRes.success && simRes.data?.status === 'running') {
        addLog('Simulation still marked running. Stopping it...')
        await forceStopSimulation()
      }
    }
  } catch (err) {
    // 检查环境状态失败不影响后续流程
    console.warn('Failed to check simulation status:', err)
  }
}

/**
 * 强制停止模拟
 */
const forceStopSimulation = async () => {
  try {
    const stopRes = await stopSimulation({ simulation_id: currentSimulationId.value })
    if (stopRes.success) {
      addLog('✓ Simulation force-stopped')
    } else {
      addLog(`Failed to force-stop simulation: ${stopRes.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Force-stop simulation error: ${err.message}`)
  }
}

const loadSimulationData = async () => {
  try {
    addLog(`Loading simulation data: ${currentSimulationId.value}`)
    
    // 获取 simulation 信息
    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data

      // Check if a completed report already exists for this simulation
      try {
        const reportCheck = await generateReport({ simulation_id: currentSimulationId.value, force_regenerate: false })
        if (reportCheck.success && reportCheck.data?.already_generated && reportCheck.data?.report_id) {
          existingReportId.value = reportCheck.data.report_id
          addLog(`Existing report found: ${reportCheck.data.report_id}`)
        }
      } catch (e) {
        // Non-blocking — ignore if report check fails
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

onMounted(async () => {
  addLog('SimulationView initialized')
  
  // 检查并关闭正在运行的模拟（用户从 Step 3 返回时）
  await checkAndStopRunningSimulation()
  
  // 加载模拟数据
  loadSimulationData()
})
</script>

<style scoped>
.simulation-view-right {
  display: flex;
  flex-direction: column;
}

/* Resume banner */
.resume-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #F0FFF4;
  border-bottom: 1px solid #C6F6D5;
  flex-shrink: 0;
}

.resume-banner-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.resume-icon {
  font-size: 18px;
  color: #22C55E;
}

.resume-title {
  font-weight: 700;
  font-size: 13px;
  color: #166534;
}

.resume-sub {
  font-size: 11px;
  color: #4ADE80;
  color: #15803D;
  margin-top: 1px;
}

.resume-view-btn {
  background: #16A34A;
  color: #FFF;
  border: none;
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.3px;
  transition: background 0.15s;
  white-space: nowrap;
}

.resume-view-btn:hover {
  background: #15803D;
}
</style>
