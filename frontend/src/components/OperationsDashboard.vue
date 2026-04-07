<template>
  <section class="ops-dashboard">
    <div class="ops-header">
      <div>
        <div class="ops-kicker">Artifact / History / Admin</div>
        <h2 class="ops-title">Operations Snapshot</h2>
      </div>
      <button class="refresh-btn" @click="loadDashboard" :disabled="loading || actionLoading">
        {{ loading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <div v-if="error" class="ops-error">{{ error }}</div>

    <div class="ops-grid">
      <article class="ops-card">
        <div class="card-label">History</div>
        <div class="headline-row">
          <div>
            <div class="headline-value">{{ summary.total }}</div>
            <div class="headline-caption">recent simulations tracked</div>
          </div>
          <div class="pill-row">
            <span class="pill complete">{{ summary.completed }} complete</span>
            <span class="pill running">{{ summary.running }} active</span>
            <span class="pill draft">{{ summary.draft }} draft</span>
          </div>
        </div>

        <div class="metric-list">
          <div class="metric-item">
            <span>Reports generated</span>
            <strong>{{ summary.withReports }}</strong>
          </div>
          <div class="metric-item">
            <span>Avg files / run</span>
            <strong>{{ summary.avgFiles }}</strong>
          </div>
          <div class="metric-item">
            <span>Latest artifact</span>
            <strong>{{ latestArtifactLabel }}</strong>
          </div>
        </div>
      </article>

      <article class="ops-card">
        <div class="card-label">Live Environment</div>
        <template v-if="selectedSimulation">
          <div class="sim-meta-row">
            <div>
              <div class="sim-id">{{ shortSimId(selectedSimulation.simulation_id) }}</div>
              <div class="sim-text">{{ truncate(selectedSimulation.simulation_requirement || 'Untitled simulation', 76) }}</div>
            </div>
            <span class="status-chip" :class="statusTone">{{ liveStatusLabel }}</span>
          </div>

          <div class="metric-list run-list">
            <div class="metric-item">
              <span>Runner</span>
              <strong>{{ runStatus.runner_status || selectedSimulation.runner_status || selectedSimulation.status || 'idle' }}</strong>
            </div>
            <div class="metric-item">
              <span>Rounds</span>
              <strong>{{ roundLabel }}</strong>
            </div>
            <div class="metric-item">
              <span>Environment</span>
              <strong>{{ envLabel }}</strong>
            </div>
            <div class="metric-item">
              <span>Platforms</span>
              <strong>{{ platformLabel }}</strong>
            </div>
          </div>
        </template>
        <div v-else class="empty-copy">No simulations yet.</div>
      </article>

      <article class="ops-card admin-card">
        <div class="card-label">Admin Controls</div>
        <div class="admin-topline">
          <div>
            <div class="headline-value tier">{{ costTier.current_tier || 'unknown' }}</div>
            <div class="headline-caption">cost tier · est {{ costTier.est_cost || 'n/a' }}</div>
          </div>
          <div class="provider-dots">
            <span v-for="provider in providerSummary" :key="provider.name" class="provider-dot" :class="{ online: provider.connected }">
              {{ provider.name }}
            </span>
          </div>
        </div>

        <div class="metric-list">
          <div class="metric-item">
            <span>Configured providers</span>
            <strong>{{ configuredProviders }}/{{ providerSummary.length }}</strong>
          </div>
          <div class="metric-item">
            <span>Task overrides</span>
            <strong>{{ overrideCount }}</strong>
          </div>
          <div class="metric-item">
            <span>Routing default</span>
            <strong>{{ primaryRouting }}</strong>
          </div>
        </div>

        <div class="routing-list" v-if="topTaskRoutes.length">
          <div v-for="task in topTaskRoutes" :key="task.name" class="route-item">
            <span>{{ task.label }}</span>
            <code>{{ task.provider }}/{{ task.model }}</code>
          </div>
        </div>
      </article>
    </div>

    <div v-if="recentArtifacts.length" class="artifact-detail-shell">
      <div class="artifact-header-row">
        <div>
          <div class="ops-kicker detail-kicker">Recent Artifacts</div>
          <h3 class="artifact-title">Recent drill-down</h3>
        </div>
        <div class="artifact-subtle">Select a recent simulation to inspect and jump into the saved workflow.</div>
      </div>

      <div class="artifact-layout">
        <aside class="artifact-rail">
          <button
            v-for="sim in recentArtifacts"
            :key="sim.simulation_id"
            class="artifact-row"
            :class="{ active: sim.simulation_id === selectedSimulation?.simulation_id }"
            @click="selectSimulation(sim)"
          >
            <div class="artifact-row-top">
              <span class="artifact-row-id">{{ shortSimId(sim.simulation_id) }}</span>
              <span class="artifact-row-status" :class="statusClass(sim)">{{ artifactStageLabel(sim) }}</span>
            </div>
            <div class="artifact-row-text">{{ truncate(sim.simulation_requirement || 'Untitled simulation', 72) }}</div>
            <div class="artifact-row-meta">
              <span>{{ formatDateTime(sim.created_at) }}</span>
              <span>{{ fileCountLabel(sim) }}</span>
            </div>
          </button>
        </aside>

        <article class="artifact-detail-card" v-if="selectedSimulation">
          <div class="artifact-detail-top">
            <div>
              <div class="sim-id">{{ shortSimId(selectedSimulation.simulation_id) }}</div>
              <h4 class="artifact-detail-title">{{ selectedTitle }}</h4>
            </div>
            <div class="artifact-status-stack">
              <span class="status-chip" :class="statusTone">{{ liveStatusLabel }}</span>
              <span class="artifact-timestamp">{{ formatDateTime(selectedSimulation.created_at) }}</span>
            </div>
          </div>

          <p class="artifact-detail-copy">{{ selectedSimulation.simulation_requirement || 'No simulation requirement saved.' }}</p>

          <div class="artifact-progress-card">
            <div class="artifact-progress-header">
              <div>
                <div class="ops-kicker detail-kicker">Workflow checkpoint</div>
                <div class="artifact-progress-title">{{ workflowProgressLabel }}</div>
              </div>
              <strong>{{ selectedProgressPercent }}%</strong>
            </div>
            <div class="artifact-progress-bar" aria-hidden="true">
              <span class="artifact-progress-fill" :style="{ width: `${selectedProgressPercent}%` }"></span>
            </div>
            <div class="artifact-progress-meta">
              <span>{{ workflowProgressCopy }}</span>
              <span>{{ formatDateTime(selectedSimulation.updated_at || selectedSimulation.created_at) }}</span>
            </div>
          </div>

          <div v-if="workflowChecklist.length" class="workflow-checklist">
            <div
              v-for="step in workflowChecklist"
              :key="step.key"
              class="workflow-step"
              :class="step.state"
            >
              <div class="workflow-step-top">
                <span class="workflow-step-label">{{ step.label }}</span>
                <span class="workflow-step-state">{{ step.badge }}</span>
              </div>
              <div class="workflow-step-hint">{{ step.hint }}</div>
            </div>
          </div>

          <div class="artifact-stats-grid">
            <div class="detail-stat">
              <span>Artifact stage</span>
              <strong>{{ artifactStageLabel(selectedSimulation) }}</strong>
            </div>
            <div class="detail-stat">
              <span>Runner</span>
              <strong>{{ runStatus.runner_status || selectedSimulation.runner_status || selectedSimulation.status || 'idle' }}</strong>
            </div>
            <div class="detail-stat">
              <span>Rounds</span>
              <strong>{{ roundLabel }}</strong>
            </div>
            <div class="detail-stat">
              <span>Files</span>
              <strong>{{ fileCountLabel(selectedSimulation) }}</strong>
            </div>
            <div class="detail-stat">
              <span>Environment</span>
              <strong>{{ envLabel }}</strong>
            </div>
            <div class="detail-stat">
              <span>Platforms</span>
              <strong>{{ platformLabel }}</strong>
            </div>
          </div>

          <div v-if="selectedManifest.length" class="artifact-manifest-grid">
            <div v-for="item in selectedManifest" :key="item.label" class="manifest-item">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>

          <div class="artifact-files-block">
            <div class="artifact-files-header">
              <span>Attached files</span>
              <span class="artifact-files-count">{{ selectedFiles.length }}</span>
            </div>
            <div v-if="selectedFiles.length" class="artifact-files-list">
              <div v-for="file in selectedFiles.slice(0, 6)" :key="file.filename" class="artifact-file-chip">
                <span class="artifact-file-ext">{{ getFileTypeLabel(file.filename) }}</span>
                <span class="artifact-file-name">{{ truncate(file.filename, 34) }}</span>
              </div>
            </div>
            <div v-else class="empty-copy">No attached files.</div>
          </div>

          <div class="artifact-actions">
            <button class="artifact-action" :disabled="!selectedSimulation.project_id" @click="openGraphBuild">
              <span class="artifact-action-step">Step 1</span>
              <span>Graph Build</span>
            </button>
            <button class="artifact-action" @click="openEnvironmentSetup">
              <span class="artifact-action-step">Step 2</span>
              <span>Environment Setup</span>
            </button>
            <button class="artifact-action" :disabled="!selectedSimulation.project_id" @click="openSimulationRun">
              <span class="artifact-action-step">Step 3</span>
              <span>Run Simulation</span>
            </button>
            <button class="artifact-action" :disabled="!selectedSimulation.report_id" @click="openReport">
              <span class="artifact-action-step">Step 4</span>
              <span>Report</span>
            </button>
            <button class="artifact-action primary" :disabled="actionLoading || !selectedSimulation.simulation_id" @click="resumeInteraction">
              <span class="artifact-action-step">Step 5</span>
              <span>{{ actionLoading ? 'Opening…' : 'Resume' }}</span>
            </button>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getCostTier, getModelRouting } from '../api/settings'
import { getEnvStatus, getRunStatus, getSimulationHistory, reopenEnv } from '../api/simulation'
import { buildHistoryQuery } from '../workflow/history'

const router = useRouter()

const loading = ref(false)
const actionLoading = ref(false)
const error = ref('')
const history = ref([])
const selectedSimulation = ref(null)
const runStatus = ref({})
const envStatus = ref({})
const costTier = ref({})
const modelRouting = ref({ tasks: {}, providers: {} })

const normalizeLifecycle = (simulation = {}) => {
  return simulation.report_id
    ? 'completed'
    : (simulation.runner_status || simulation.status || 'idle')
}

const summary = computed(() => {
  const sims = history.value
  const total = sims.length
  const completed = sims.filter(sim => sim.report_id || ['completed', 'stopped'].includes(normalizeLifecycle(sim))).length
  const running = sims.filter(sim => ['starting', 'running', 'pausing', 'paused', 'stopping'].includes(normalizeLifecycle(sim))).length
  const draft = Math.max(total - completed - running, 0)
  const withReports = sims.filter(sim => sim.report_id).length
  const avgFiles = total
    ? (sims.reduce((sum, sim) => sum + (sim.files?.length || 0), 0) / total).toFixed(1)
    : '0.0'

  return { total, completed, running, draft, withReports, avgFiles }
})

const recentArtifacts = computed(() => history.value.slice(0, 5))

const latestArtifactLabel = computed(() => {
  const sim = history.value[0]
  if (!sim) return 'none'
  if (sim.report_id) return 'report ready'
  if (sim.project_id) return 'graph + env'
  return 'seed only'
})

const liveStatusLabel = computed(() => {
  if (!selectedSimulation.value) return 'idle'
  if (envStatus.value.env_alive) return 'env live'
  if ((runStatus.value.runner_status || selectedSimulation.value.runner_status) === 'running') return 'sim running'
  if (selectedSimulation.value.report_id) return 'report ready'
  return 'standby'
})

const statusTone = computed(() => {
  if (envStatus.value.env_alive) return 'online'
  if ((runStatus.value.runner_status || selectedSimulation.value?.runner_status) === 'running') return 'running'
  if (selectedSimulation.value?.report_id) return 'complete'
  return 'idle'
})

const roundLabel = computed(() => {
  const current = runStatus.value.current_round ?? selectedSimulation.value?.current_round ?? 0
  const total = runStatus.value.total_rounds ?? selectedSimulation.value?.total_rounds ?? 0
  return total > 0 ? `${current}/${total}` : 'not started'
})

const envLabel = computed(() => {
  if (!selectedSimulation.value) return 'n/a'
  return envStatus.value.env_alive ? 'ready for interview' : 'offline'
})

const platformLabel = computed(() => {
  if (!selectedSimulation.value) return 'n/a'
  const flags = []
  if (envStatus.value.twitter_available || runStatus.value.twitter_running) flags.push('twitter')
  if (envStatus.value.reddit_available || runStatus.value.reddit_running) flags.push('reddit')
  return flags.length ? flags.join(' + ') : 'no live platform'
})

const providerSummary = computed(() => {
  return Object.entries(modelRouting.value.providers || {}).map(([name, meta]) => ({
    name,
    connected: Boolean(meta?.connected)
  }))
})

const configuredProviders = computed(() => providerSummary.value.filter(provider => provider.connected).length)
const overrideCount = computed(() => Object.values(modelRouting.value.tasks || {}).filter(task => task?.overridden).length)

const primaryRouting = computed(() => {
  const ontology = modelRouting.value.tasks?.ontology
  if (!ontology) return 'n/a'
  return `${ontology.provider}/${ontology.model}`
})

const topTaskRoutes = computed(() => {
  const preferred = ['ontology', 'profiles', 'report_section']
  return preferred
    .map(name => ({ name, label: name.replace('_', ' '), ...(modelRouting.value.tasks?.[name] || {}) }))
    .filter(task => task.provider && task.model)
})

const selectedTitle = computed(() => {
  const requirement = selectedSimulation.value?.simulation_requirement || ''
  if (!requirement) return 'Untitled simulation'
  return requirement.length > 84 ? `${requirement.slice(0, 84)}…` : requirement
})

const selectedFiles = computed(() => selectedSimulation.value?.files || [])

const selectedProgressPercent = computed(() => {
  const sim = selectedSimulation.value
  if (!sim) return 0

  const explicit = Number(runStatus.value.progress_percent ?? sim.progress_percent)
  if (Number.isFinite(explicit) && explicit > 0) {
    return Math.max(0, Math.min(100, Math.round(explicit)))
  }

  const current = Number(runStatus.value.current_round ?? sim.current_round ?? 0)
  const total = Number(runStatus.value.total_rounds ?? sim.total_rounds ?? 0)
  if (total > 0) {
    return Math.max(0, Math.min(100, Math.round((current / total) * 100)))
  }

  return sim.report_id ? 100 : 0
})

const workflowProgressLabel = computed(() => {
  const sim = selectedSimulation.value
  if (!sim) return 'No artifact selected'
  if (envStatus.value.env_alive) return 'Environment reopened and ready'
  if (sim.report_id) return 'Report-ready artifact chain'
  if ((runStatus.value.runner_status || sim.runner_status || sim.status) === 'running') return 'Simulation actively running'
  if (sim.project_id) return 'Graph and environment prepared'
  return 'Seed captured'
})

const workflowProgressCopy = computed(() => {
  const sim = selectedSimulation.value
  if (!sim) return 'Select a simulation to inspect its workflow state.'
  if (envStatus.value.env_alive) return `Live environment · ${platformLabel.value}`
  if (sim.report_id) return 'All downstream artifacts are available for reopen and review.'
  if ((runStatus.value.runner_status || sim.runner_status || sim.status) === 'running') return `Round progress ${roundLabel.value}`
  if (sim.project_id) return 'Ready to jump back into setup or continue the run.'
  return 'Only the initial seed exists so far.'
})

const workflowChecklist = computed(() => {
  const sim = selectedSimulation.value
  if (!sim) return []

  const runnerStatus = runStatus.value.runner_status || sim.runner_status || sim.status || 'idle'
  const currentRound = Number(runStatus.value.current_round ?? sim.current_round ?? 0)
  const hasRounds = currentRound > 0

  return [
    {
      key: 'seed',
      label: 'Seed',
      state: sim.simulation_id ? 'ready' : 'missing',
      badge: sim.simulation_id ? 'saved' : 'missing',
      hint: sim.simulation_id ? shortSimId(sim.simulation_id) : 'No simulation id yet'
    },
    {
      key: 'graph',
      label: 'Graph',
      state: sim.project_id ? 'ready' : 'missing',
      badge: sim.project_id ? 'linked' : 'missing',
      hint: sim.project_id ? truncate(sim.project_name || sim.project_id, 28) : 'Project not generated'
    },
    {
      key: 'env',
      label: 'Env',
      state: envStatus.value.env_alive ? 'live' : (sim.project_id ? 'ready' : 'missing'),
      badge: envStatus.value.env_alive ? 'live' : (sim.project_id ? 'standby' : 'missing'),
      hint: envStatus.value.env_alive ? 'Interview shell open now' : envLabel.value
    },
    {
      key: 'run',
      label: 'Run',
      state: runnerStatus === 'running' ? 'live' : (hasRounds || ['completed', 'stopped', 'paused'].includes(runnerStatus) ? 'ready' : 'missing'),
      badge: runnerStatus === 'running' ? 'live' : (hasRounds ? roundLabel.value : 'idle'),
      hint: hasRounds ? `${currentRound} round${currentRound === 1 ? '' : 's'} captured` : `Runner ${runnerStatus}`
    },
    {
      key: 'report',
      label: 'Report',
      state: sim.report_id ? 'ready' : 'missing',
      badge: sim.report_id ? 'ready' : 'missing',
      hint: sim.report_id ? truncate(sim.report_id, 18) : 'No report artifact yet'
    }
  ]
})

const selectedManifest = computed(() => {
  const sim = selectedSimulation.value
  if (!sim) return []

  const items = [
    { label: 'Project', value: sim.project_name || sim.project_id || 'unlinked' },
    { label: 'Project ID', value: sim.project_id || 'not generated' },
    { label: 'Report ID', value: sim.report_id || 'not generated' },
    { label: 'Entities', value: sim.entities_count ? `${sim.entities_count}` : 'n/a' },
    { label: 'Profiles', value: sim.profiles_count ? `${sim.profiles_count}` : 'n/a' },
    { label: 'Entity mix', value: summarizeEntityTypes(sim.entity_types) },
    { label: 'Sim span', value: sim.total_simulation_hours ? `${sim.total_simulation_hours}h planned` : 'n/a' },
    { label: 'Version', value: sim.version || 'n/a' }
  ]

  return items.filter(item => item.value)
})

const shortSimId = (id) => {
  if (!id) return 'SIM_UNKNOWN'
  return `SIM_${id.replace('sim_', '').slice(0, 6).toUpperCase()}`
}

const truncate = (text, limit = 64) => {
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return 'unknown time'
  try {
    const date = new Date(dateStr)
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    const hh = String(date.getHours()).padStart(2, '0')
    const mm = String(date.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${d} ${hh}:${mm}`
  } catch {
    return dateStr
  }
}

const getFileTypeLabel = (filename) => {
  if (!filename) return 'FILE'
  const ext = filename.split('.').pop()?.toUpperCase()
  return ext || 'FILE'
}

const summarizeEntityTypes = (types = []) => {
  if (!Array.isArray(types) || !types.length) return 'n/a'
  if (types.length <= 3) return types.join(' · ')
  return `${types.slice(0, 3).join(' · ')} +${types.length - 3}`
}

const artifactStageLabel = (simulation = {}) => {
  if (simulation.report_id) return 'report ready'
  const runnerStatus = simulation.runner_status || simulation.status || ''
  if (['starting', 'running', 'pausing', 'paused', 'stopping'].includes(runnerStatus)) return runnerStatus === 'running' ? 'running' : runnerStatus
  if (simulation.project_id) return 'graph + env'
  return 'seed only'
}

const fileCountLabel = (simulation = {}) => {
  const count = simulation.files?.length || 0
  return `${count} file${count === 1 ? '' : 's'}`
}

const statusClass = (simulation = {}) => {
  if (simulation.report_id) return 'complete'
  if (['starting', 'running', 'pausing', 'paused', 'stopping'].includes(normalizeLifecycle(simulation))) return 'running'
  return 'idle'
}

const buildHistQuery = (simulation = selectedSimulation.value) => buildHistoryQuery({
  projectId: simulation?.project_id,
  simulationId: simulation?.simulation_id,
  reportId: simulation?.report_id,
})

const loadSelectedRuntime = async (simulation) => {
  if (!simulation?.simulation_id) {
    runStatus.value = {}
    envStatus.value = {}
    return
  }

  const results = await Promise.allSettled([
    getRunStatus(simulation.simulation_id),
    getEnvStatus({ simulation_id: simulation.simulation_id })
  ])

  runStatus.value = results[0].status === 'fulfilled' ? (results[0].value.data || {}) : {}
  envStatus.value = results[1].status === 'fulfilled' ? (results[1].value.data || {}) : {}
}

const selectSimulation = async (simulation) => {
  selectedSimulation.value = simulation
  await loadSelectedRuntime(simulation)
}

const openGraphBuild = () => {
  if (!selectedSimulation.value?.project_id) return
  router.push({
    name: 'Process',
    params: { projectId: selectedSimulation.value.project_id },
    query: buildHistQuery()
  })
}

const openEnvironmentSetup = () => {
  if (!selectedSimulation.value?.simulation_id) return
  router.push({
    name: 'Simulation',
    params: { simulationId: selectedSimulation.value.simulation_id },
    query: buildHistQuery()
  })
}

const openSimulationRun = () => {
  if (!selectedSimulation.value?.simulation_id) return
  router.push({
    name: 'SimulationRun',
    params: { simulationId: selectedSimulation.value.simulation_id },
    query: buildHistQuery()
  })
}

const openReport = () => {
  if (!selectedSimulation.value?.report_id) return
  router.push({
    name: 'Report',
    params: { reportId: selectedSimulation.value.report_id },
    query: buildHistQuery()
  })
}

const resumeInteraction = async () => {
  if (!selectedSimulation.value?.simulation_id || actionLoading.value) return

  const simulationId = selectedSimulation.value.simulation_id
  const reportId = selectedSimulation.value.report_id
  const histQuery = buildHistQuery()

  actionLoading.value = true
  try {
    await reopenEnv({ simulation_id: simulationId })
  } catch (e) {
    console.error('Failed to reopen environment:', e)
  } finally {
    actionLoading.value = false
  }

  router.push({
    name: 'Interaction',
    params: reportId ? { reportId } : {},
    query: { ...histQuery, simulation_id: simulationId, reopen: '1' }
  })
}

const loadDashboard = async () => {
  loading.value = true
  error.value = ''

  try {
    const [historyRes, tierRes, routingRes] = await Promise.all([
      getSimulationHistory(12),
      getCostTier(),
      getModelRouting()
    ])

    history.value = historyRes.data || []
    costTier.value = tierRes || {}
    modelRouting.value = routingRes || { tasks: {}, providers: {} }

    const nextSelected = selectedSimulation.value
      ? history.value.find(sim => sim.simulation_id === selectedSimulation.value.simulation_id) || history.value[0] || null
      : history.value[0] || null

    selectedSimulation.value = nextSelected
    await loadSelectedRuntime(nextSelected)
  } catch (err) {
    console.error('Failed to load operations dashboard:', err)
    error.value = err?.message || 'Failed to load dashboard'
  } finally {
    loading.value = false
  }
}

const ACTIVE_STATUSES = ['starting', 'running', 'pausing', 'paused', 'stopping']

const isLiveSimulation = computed(() => {
  const status = runStatus.value.runner_status || selectedSimulation.value?.runner_status || ''
  return ACTIVE_STATUSES.includes(status) || envStatus.value.env_alive
})

let runtimePollTimer = null
let dashboardRefreshTimer = null

const startPolling = () => {
  stopPolling()

  // Fast poll: refresh selected simulation runtime every 10s when live
  runtimePollTimer = setInterval(() => {
    if (isLiveSimulation.value && selectedSimulation.value) {
      loadSelectedRuntime(selectedSimulation.value)
    }
  }, 10000)

  // Background poll: refresh full dashboard list every 60s
  dashboardRefreshTimer = setInterval(() => {
    if (!loading.value) loadDashboard()
  }, 60000)
}

const stopPolling = () => {
  if (runtimePollTimer) { clearInterval(runtimePollTimer); runtimePollTimer = null }
  if (dashboardRefreshTimer) { clearInterval(dashboardRefreshTimer); dashboardRefreshTimer = null }
}

watch(() => selectedSimulation.value?.simulation_id, (next, prev) => {
  if (next && next !== prev) {
    error.value = ''
  }
})

onMounted(async () => {
  await loadDashboard()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<style scoped>
.ops-dashboard {
  margin-top: 56px;
  padding: 28px 30px 30px;
  border: 1px solid #E5E5E5;
  background: linear-gradient(180deg, #FFFFFF 0%, #FAFAFA 100%);
}

.ops-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.ops-kicker,
.card-label,
.route-item code,
.refresh-btn,
.provider-dot,
.pill,
.status-chip,
.artifact-row-id,
.artifact-row-status,
.artifact-action-step {
  font-family: 'JetBrains Mono', monospace;
}

.ops-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: #888;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.detail-kicker {
  margin-bottom: 6px;
}

.ops-title {
  margin: 0;
  font-size: 1.8rem;
  font-weight: 550;
}

.refresh-btn {
  border: 1px solid #D6D6D6;
  background: #FFF;
  color: #333;
  padding: 10px 14px;
  font-size: 0.72rem;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.ops-error {
  margin-bottom: 16px;
  padding: 10px 12px;
  border: 1px solid #FF4500;
  background: #FFF5F0;
  color: #CC3700;
  font-size: 0.85rem;
}

.ops-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.ops-card {
  border: 1px solid #E8E8E8;
  background: #FFF;
  padding: 18px;
  min-height: 248px;
}

.card-label {
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  color: #999;
  text-transform: uppercase;
  margin-bottom: 16px;
}

.headline-row,
.admin-topline,
.sim-meta-row,
.artifact-detail-top,
.artifact-header-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.headline-row,
.admin-topline,
.sim-meta-row {
  margin-bottom: 18px;
}

.headline-value {
  font-size: 2.2rem;
  font-weight: 600;
  line-height: 1;
}

.headline-value.tier {
  text-transform: uppercase;
  font-size: 1.6rem;
}

.headline-caption,
.sim-text,
.empty-copy,
.artifact-subtle,
.artifact-row-text,
.artifact-detail-copy,
.artifact-timestamp {
  color: #777;
  font-size: 0.84rem;
  line-height: 1.5;
}

.pill-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}

.pill,
.status-chip,
.provider-dot,
.artifact-row-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  font-size: 0.68rem;
  border: 1px solid #E5E5E5;
  text-transform: uppercase;
}

.pill.complete,
.status-chip.complete,
.artifact-row-status.complete { color: #0F9F6E; background: rgba(16,185,129,0.08); }
.pill.running,
.status-chip.running,
.artifact-row-status.running { color: #C46B00; background: rgba(245,158,11,0.1); }
.pill.draft,
.status-chip.idle,
.artifact-row-status.idle { color: #6B7280; background: #F3F4F6; }
.status-chip.online { color: #2563EB; background: rgba(37,99,235,0.08); }

.metric-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-item,
.route-item {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-top: 10px;
  border-top: 1px solid #F1F1F1;
  font-size: 0.84rem;
}

.metric-item span,
.route-item span,
.detail-stat span {
  color: #777;
}

.metric-item strong,
.route-item code,
.detail-stat strong {
  color: #111;
  text-align: right;
}

.sim-id,
.artifact-row-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.84rem;
  color: #111;
}

.provider-dots {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.provider-dot.online {
  color: #0F9F6E;
  border-color: rgba(16,185,129,0.25);
  background: rgba(16,185,129,0.06);
}

.routing-list {
  margin-top: 16px;
}

.artifact-detail-shell {
  margin-top: 22px;
  border-top: 1px solid #E8E8E8;
  padding-top: 22px;
}

.artifact-header-row {
  align-items: end;
  margin-bottom: 16px;
}

.artifact-title,
.artifact-detail-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: #111;
}

.artifact-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.95fr) minmax(0, 1.6fr);
  gap: 18px;
}

.artifact-rail,
.artifact-detail-card {
  border: 1px solid #E8E8E8;
  background: #FFF;
}

.artifact-rail {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.artifact-row {
  width: 100%;
  text-align: left;
  border: 1px solid #EFEFEF;
  background: #FAFAFA;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.artifact-row:hover,
.artifact-row.active {
  border-color: #CFCFCF;
  background: #FFF;
}

.artifact-row.active {
  transform: translateX(3px);
}

.artifact-row-top,
.artifact-row-meta,
.artifact-files-header,
.artifact-status-stack {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.artifact-row-text {
  margin: 10px 0 12px;
  color: #222;
}

.artifact-row-meta,
.artifact-files-count,
.artifact-timestamp {
  font-size: 0.76rem;
  color: #8A8A8A;
}

.artifact-detail-card {
  padding: 18px;
}

.artifact-status-stack {
  flex-direction: column;
  align-items: flex-end;
}

.artifact-detail-copy {
  margin: 16px 0 18px;
  color: #333;
}

.artifact-progress-card,
.artifact-files-block {
  margin-top: 16px;
  border-top: 1px solid #F1F1F1;
  padding-top: 14px;
}

.artifact-progress-header,
.artifact-progress-meta,
.workflow-step-top,
.manifest-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.artifact-progress-header {
  align-items: flex-start;
}

.artifact-progress-title {
  font-size: 1rem;
  font-weight: 600;
  color: #111;
}

.artifact-progress-bar {
  width: 100%;
  height: 10px;
  background: #F3F4F6;
  margin: 12px 0 10px;
  overflow: hidden;
}

.artifact-progress-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #111 0%, #4B5563 100%);
}

.artifact-progress-meta,
.workflow-step-hint,
.manifest-item span {
  font-size: 0.78rem;
  color: #777;
}

.workflow-checklist,
.artifact-manifest-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.workflow-step,
.manifest-item {
  border: 1px solid #F0F0F0;
  background: #FCFCFC;
  padding: 12px;
}

.workflow-step.ready {
  border-color: rgba(15, 159, 110, 0.18);
  background: rgba(16, 185, 129, 0.05);
}

.workflow-step.live {
  border-color: rgba(37, 99, 235, 0.18);
  background: rgba(37, 99, 235, 0.05);
}

.workflow-step-label,
.workflow-step-state {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.workflow-step-state {
  color: #555;
}

.workflow-step.ready .workflow-step-state {
  color: #0F9F6E;
}

.workflow-step.live .workflow-step-state {
  color: #2563EB;
}

.manifest-item {
  align-items: flex-start;
}

.manifest-item strong {
  font-size: 0.84rem;
  color: #111;
  text-align: right;
  overflow-wrap: anywhere;
}

.artifact-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.detail-stat {
  border: 1px solid #F0F0F0;
  padding: 12px;
  background: #FCFCFC;
}

.detail-stat span {
  display: block;
  font-size: 0.75rem;
  margin-bottom: 6px;
}

.detail-stat strong {
  font-size: 0.9rem;
}

.artifact-files-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.artifact-file-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid #ECECEC;
  background: #FAFAFA;
  font-size: 0.76rem;
}

.artifact-file-ext {
  font-family: 'JetBrains Mono', monospace;
  color: #666;
}

.artifact-file-name {
  color: #222;
}

.artifact-actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.artifact-action {
  border: 1px solid #E2E2E2;
  background: #FFF;
  color: #111;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  text-align: left;
}

.artifact-action.primary {
  border-color: #111;
  background: #111;
  color: #FFF;
}

.artifact-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.artifact-action-step {
  font-size: 0.66rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: inherit;
  opacity: 0.7;
}

@media (max-width: 1100px) {
  .ops-grid,
  .artifact-layout,
  .workflow-checklist,
  .artifact-manifest-grid,
  .artifact-stats-grid,
  .artifact-actions {
    grid-template-columns: 1fr;
  }

  .ops-card {
    min-height: auto;
  }
}

@media (max-width: 720px) {
  .ops-dashboard {
    padding: 22px 18px;
  }

  .ops-header,
  .headline-row,
  .admin-topline,
  .sim-meta-row,
  .artifact-detail-top,
  .artifact-header-row {
    flex-direction: column;
  }

  .pill-row,
  .provider-dots,
  .artifact-status-stack {
    align-items: flex-start;
    justify-content: flex-start;
  }
}
</style>
