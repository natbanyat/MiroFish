<template>
  <div v-if="visible" class="stage-nav">
    <button
      v-for="stage in stages"
      :key="stage.step"
      class="stage-btn"
      :class="{ active: stage.step === currentStep, disabled: !stage.enabled }"
      :disabled="!stage.enabled"
      @click="navigate(stage)"
    >
      <span class="stage-step">{{ stage.step }}</span>
      <span class="stage-icon">{{ stage.icon }}</span>
      <span class="stage-label">{{ stage.label }}</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { reopenEnv } from '../api/simulation'
import { buildHistoryQuery, getRouteWorkflowIds } from '../workflow/history'

const router = useRouter()
const route = useRoute()

const props = defineProps({
  currentStep: { type: Number, required: true }
})

const workflowIds = computed(() => getRouteWorkflowIds(route))
const projectId = computed(() => workflowIds.value.projectId)
const simulationId = computed(() => workflowIds.value.simulationId)
const reportId = computed(() => workflowIds.value.reportId)

// Only show when navigating from history (at least simulation_id present)
const visible = computed(() => !!simulationId.value)

const stages = computed(() => [
  { step: 1, icon: '\u25C7', label: 'Graph', enabled: !!projectId.value },
  { step: 2, icon: '\u25C8', label: 'Env Setup', enabled: !!simulationId.value },
  { step: 3, icon: '\u25BA', label: 'Run', enabled: !!simulationId.value },
  { step: 4, icon: '\u25C6', label: 'Report', enabled: !!reportId.value },
  { step: 5, icon: '\u25C9', label: 'Interact', enabled: !!simulationId.value },
])

// Shared query params to preserve across navigation
const histQuery = computed(() => buildHistoryQuery(workflowIds.value))

const navigate = async (stage) => {
  if (!stage.enabled || stage.step === props.currentStep) return

  switch (stage.step) {
    case 1:
      router.push({ name: 'Process', params: { projectId: projectId.value }, query: histQuery.value })
      break
    case 2:
      router.push({ name: 'Simulation', params: { simulationId: simulationId.value }, query: histQuery.value })
      break
    case 3:
      router.push({ name: 'SimulationRun', params: { simulationId: simulationId.value }, query: histQuery.value })
      break
    case 4:
      router.push({ name: 'Report', params: { reportId: reportId.value }, query: histQuery.value })
      break
    case 5:
      // Reopen env then navigate
      try {
        await reopenEnv({ simulation_id: simulationId.value })
      } catch { /* env may already be alive */ }
      router.push({
        name: 'Interaction',
        params: reportId.value ? { reportId: reportId.value } : {},
        query: { ...histQuery.value, simulation_id: simulationId.value, reopen: '1' }
      })
      break
  }
}
</script>

<style scoped>
.stage-nav {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
  max-width: calc(100vw - 32px);
  padding: 8px;
  background: rgba(17, 17, 17, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  z-index: 9999;
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(14px);
}

.stage-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: #9CA3AF;
  font-family: 'JetBrains Mono', 'Space Grotesk', monospace;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.stage-btn:hover:not(.disabled):not(.active) {
  background: rgba(255, 255, 255, 0.08);
  color: #F3F4F6;
  transform: translateY(-1px);
}

.stage-btn.active {
  background: linear-gradient(135deg, rgba(255, 69, 0, 0.9), rgba(255, 122, 0, 0.84));
  border-color: rgba(255, 255, 255, 0.16);
  color: #fff;
  box-shadow: 0 10px 24px rgba(255, 69, 0, 0.24);
}

.stage-btn.disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.stage-step {
  font-size: 10px;
  opacity: 0.72;
}

.stage-icon {
  font-size: 14px;
}

.stage-label {
  font-size: 12px;
}

@media (max-width: 720px) {
  .stage-nav {
    gap: 4px;
    bottom: 18px;
    padding: 6px;
  }

  .stage-btn {
    padding: 8px 10px;
  }

  .stage-label {
    font-size: 11px;
  }
}
</style>
