<template>
  <div class="model-router-overlay" v-if="visible" @click.self="$emit('close')">
    <div class="model-router">
      <div class="mr-header">
        <span class="mr-title">MODEL ROUTING</span>
        <div class="mr-actions">
          <button class="mr-reset" @click="resetAll" :disabled="saving">Reset All</button>
          <button class="mr-close" @click="$emit('close')">&times;</button>
        </div>
      </div>

      <div class="mr-providers">
        <span
          v-for="(info, pname) in providers"
          :key="pname"
          :class="['provider-badge', { connected: info.connected }]"
        >{{ pname }}</span>
      </div>

      <div class="mr-table">
        <div class="mr-row mr-header-row">
          <span class="mr-cell mr-task-cell">Task</span>
          <span class="mr-cell mr-provider-cell">Provider</span>
          <span class="mr-cell mr-model-cell">Model</span>
          <span class="mr-cell mr-cost-cell">Cost</span>
          <span class="mr-cell mr-action-cell"></span>
        </div>

        <div
          v-for="(task, taskName) in tasks"
          :key="taskName"
          :class="['mr-row', { overridden: task.overridden }]"
        >
          <div class="mr-cell mr-task-cell">
            <div class="task-name">{{ task.label }}</div>
            <div class="task-desc">{{ task.desc }}</div>
          </div>

          <div class="mr-cell mr-provider-cell">
            <select
              :value="task.provider"
              @change="onProviderChange(taskName, $event.target.value)"
              :disabled="saving"
            >
              <option
                v-for="(info, pname) in providers"
                :key="pname"
                :value="pname"
                :disabled="!info.connected"
              >{{ pname }}{{ info.connected ? '' : ' (no key)' }}</option>
            </select>
          </div>

          <div class="mr-cell mr-model-cell">
            <select
              :value="task.model"
              @change="onModelChange(taskName, task.provider, $event.target.value)"
              :disabled="saving"
            >
              <option
                v-for="m in getModelsForProvider(task.provider)"
                :key="m.id"
                :value="m.id"
              >{{ m.id }}</option>
              <!-- Allow current model even if not in list -->
              <option
                v-if="!getModelsForProvider(task.provider).find(m => m.id === task.model)"
                :value="task.model"
              >{{ task.model }}</option>
            </select>
          </div>

          <div class="mr-cell mr-cost-cell">
            {{ getModelCost(task.provider, task.model) }}
          </div>

          <div class="mr-cell mr-action-cell">
            <button
              v-if="task.overridden"
              class="mr-undo"
              @click="resetTask(taskName)"
              title="Reset to default"
              :disabled="saving"
            >&#x21A9;</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getModelRouting, setTaskModel, resetTaskModel, resetAllModelRouting } from '../api/settings'

defineProps({ visible: Boolean })
defineEmits(['close'])

const tasks = ref({})
const providers = ref({})
const saving = ref(false)

async function load() {
  try {
    const res = await getModelRouting()
    tasks.value = res.tasks || {}
    providers.value = res.providers || {}
  } catch (e) {
    console.error('Failed to load model routing:', e)
  }
}

function getModelsForProvider(provider) {
  return (providers.value[provider] && providers.value[provider].models) || []
}

function getModelCost(provider, model) {
  const models = getModelsForProvider(provider)
  const m = models.find(x => x.id === model)
  return m ? m.cost : '?'
}

async function onProviderChange(taskName, newProvider) {
  const models = getModelsForProvider(newProvider)
  const firstModel = models.length ? models[0].id : ''
  if (!firstModel) return
  saving.value = true
  try {
    const res = await setTaskModel(taskName, newProvider, firstModel)
    tasks.value = res.tasks || tasks.value
  } catch (e) { console.error(e) }
  finally { saving.value = false }
}

async function onModelChange(taskName, provider, newModel) {
  saving.value = true
  try {
    const res = await setTaskModel(taskName, provider, newModel)
    tasks.value = res.tasks || tasks.value
  } catch (e) { console.error(e) }
  finally { saving.value = false }
}

async function resetTask(taskName) {
  saving.value = true
  try {
    const res = await resetTaskModel(taskName)
    tasks.value = res.tasks || tasks.value
  } catch (e) { console.error(e) }
  finally { saving.value = false }
}

async function resetAll() {
  saving.value = true
  try {
    const res = await resetAllModelRouting()
    tasks.value = res.tasks || tasks.value
  } catch (e) { console.error(e) }
  finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped>
.model-router-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  font-family: 'JetBrains Mono', monospace;
}

.model-router {
  background: #111;
  border: 1px solid #333;
  width: 680px;
  max-height: 80vh;
  overflow-y: auto;
  color: #ccc;
}

.mr-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #333;
}

.mr-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #fff;
}

.mr-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mr-reset {
  padding: 3px 10px;
  border: 1px solid #444;
  background: none;
  color: #888;
  font-family: inherit;
  font-size: 10px;
  cursor: pointer;
}
.mr-reset:hover { color: #FF4500; border-color: #FF4500; }

.mr-close {
  background: none;
  border: none;
  color: #666;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}
.mr-close:hover { color: #fff; }

.mr-providers {
  display: flex;
  gap: 6px;
  padding: 10px 16px;
  border-bottom: 1px solid #222;
}

.provider-badge {
  padding: 2px 8px;
  border: 1px solid #333;
  font-size: 10px;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.provider-badge.connected {
  border-color: #2a5;
  color: #2a5;
}

.mr-table {
  padding: 4px 0;
}

.mr-row {
  display: flex;
  align-items: center;
  padding: 6px 16px;
  border-bottom: 1px solid #1a1a1a;
}

.mr-row.overridden {
  background: #1a1500;
}

.mr-header-row {
  border-bottom: 1px solid #333;
}

.mr-header-row .mr-cell {
  font-size: 9px;
  color: #555;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.mr-cell { display: flex; align-items: center; }
.mr-task-cell { flex: 2.2; flex-direction: column; align-items: flex-start; gap: 1px; }
.mr-provider-cell { flex: 1.2; }
.mr-model-cell { flex: 2; }
.mr-cost-cell { flex: 1; font-size: 10px; color: #666; }
.mr-action-cell { flex: 0.4; justify-content: center; }

.task-name {
  font-size: 11px;
  color: #ddd;
}

.task-desc {
  font-size: 9px;
  color: #555;
}

.mr-row select {
  width: 100%;
  padding: 3px 4px;
  background: #0a0a0a;
  border: 1px solid #2a2a2a;
  color: #bbb;
  font-family: inherit;
  font-size: 10px;
  cursor: pointer;
}

.mr-row select:focus {
  outline: none;
  border-color: #FF4500;
}

.mr-undo {
  background: none;
  border: 1px solid #444;
  color: #888;
  width: 22px;
  height: 22px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mr-undo:hover { color: #FF4500; border-color: #FF4500; }
</style>
