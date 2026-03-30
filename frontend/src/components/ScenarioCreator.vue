<template>
  <div class="scenario-creator">
    <!-- Scenario selector bar -->
    <div class="selector-bar">
      <div class="selector-left">
        <select
          class="scenario-dropdown"
          :value="selectedId"
          @change="onSelect($event.target.value)"
          :disabled="generating"
        >
          <option value="">-- Write manually --</option>
          <option
            v-for="s in scenarios"
            :key="s.id"
            :value="s.id"
          >{{ s.title }}</option>
        </select>
        <button
          v-if="selectedId"
          class="icon-btn delete-btn"
          @click="onDelete"
          title="Delete scenario"
        >&times;</button>
      </div>
      <div class="selector-right">
        <button
          class="ai-btn"
          @click="showCreator = !showCreator"
          :class="{ active: showCreator }"
          :disabled="generating"
        >
          <span class="ai-icon">*</span> AI Create
        </button>
      </div>
    </div>

    <!-- AI Creator panel (slides down) -->
    <div v-if="showCreator" class="creator-panel">
      <div class="creator-header">
        <span class="creator-label">Describe your scenario in plain language</span>
        <button class="icon-btn" @click="showCreator = false">&times;</button>
      </div>
      <textarea
        v-model="aiInput"
        class="ai-input"
        placeholder="e.g. A major Chinese university is caught falsifying research data in Nature publications. How does the academic community and public respond?"
        rows="3"
        :disabled="generating"
        @keydown.ctrl.enter="onGenerate"
      ></textarea>
      <div class="creator-actions">
        <span class="hint">Ctrl+Enter to generate</span>
        <button
          class="generate-btn"
          @click="onGenerate"
          :disabled="!aiInput.trim() || generating"
        >
          <span v-if="!generating">Generate Scenario</span>
          <span v-else>Generating...</span>
        </button>
      </div>
      <div v-if="genError" class="gen-error">{{ genError }}</div>

      <!-- Generated preview -->
      <div v-if="generatedScenario" class="preview-panel">
        <div class="preview-header">
          <span class="preview-title">{{ generatedScenario.title }}</span>
          <div class="preview-meta">
            {{ generatedScenario.estimated_actors }} actors
            / {{ generatedScenario.recommended_window_hours }}h window
          </div>
        </div>
        <div class="preview-question">{{ generatedScenario.prediction_question }}</div>
        <div class="preview-actors">
          <span
            v-for="(a, i) in generatedScenario.key_actors"
            :key="i"
            class="actor-tag"
          >{{ a.name }}</span>
        </div>
        <div class="preview-actions">
          <button class="use-btn" @click="onUseScenario">Use This</button>
          <button class="save-btn" @click="onSaveAndUse">Save & Use</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listScenarios, getScenario, saveScenario, deleteScenario, generateScenario } from '../api/scenarios'

const emit = defineEmits(['select-prompt'])

const scenarios = ref([])
const selectedId = ref('')
const showCreator = ref(false)
const aiInput = ref('')
const generating = ref(false)
const genError = ref('')
const generatedScenario = ref(null)

async function loadScenarios() {
  try {
    const res = await listScenarios()
    scenarios.value = res.scenarios || []
  } catch (e) {
    console.warn('Failed to load scenarios:', e)
  }
}

async function onSelect(id) {
  selectedId.value = id
  if (!id) {
    emit('select-prompt', '')
    return
  }
  try {
    const res = await getScenario(id)
    emit('select-prompt', res.rendered_prompt || '')
  } catch (e) {
    console.error('Failed to load scenario:', e)
  }
}

async function onDelete() {
  if (!selectedId.value) return
  try {
    await deleteScenario(selectedId.value)
    selectedId.value = ''
    emit('select-prompt', '')
    await loadScenarios()
  } catch (e) {
    console.error('Failed to delete:', e)
  }
}

async function onGenerate() {
  if (!aiInput.value.trim() || generating.value) return
  generating.value = true
  genError.value = ''
  generatedScenario.value = null

  try {
    const res = await generateScenario(aiInput.value.trim())
    generatedScenario.value = res
  } catch (e) {
    genError.value = e.message || 'Generation failed'
  } finally {
    generating.value = false
  }
}

function onUseScenario() {
  if (!generatedScenario.value) return
  const prompt = generatedScenario.value.rendered_prompt || ''
  emit('select-prompt', prompt)
  showCreator.value = false
}

async function onSaveAndUse() {
  if (!generatedScenario.value) return
  try {
    const res = await saveScenario(generatedScenario.value)
    await loadScenarios()
    selectedId.value = res.id
    emit('select-prompt', res.rendered_prompt || '')
    showCreator.value = false
  } catch (e) {
    genError.value = 'Save failed: ' + (e.message || '')
  }
}

onMounted(loadScenarios)
</script>

<style scoped>
.scenario-creator {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  margin-bottom: 12px;
}

.selector-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.selector-left {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.scenario-dropdown {
  flex: 1;
  min-width: 0;
  padding: 6px 8px;
  border: 1px solid #333;
  background: #111;
  color: #ccc;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23666'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  padding-right: 24px;
  text-overflow: ellipsis;
}

.scenario-dropdown:focus {
  outline: none;
  border-color: #FF4500;
}

.icon-btn {
  background: none;
  border: 1px solid #333;
  color: #666;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-btn:hover {
  color: #fff;
  border-color: #666;
}

.delete-btn:hover {
  color: #FF4500;
  border-color: #FF4500;
}

.ai-btn {
  padding: 5px 12px;
  border: 1px solid #FF4500;
  background: transparent;
  color: #FF4500;
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.5px;
  transition: all 0.15s;
  white-space: nowrap;
}

.ai-btn:hover,
.ai-btn.active {
  background: #FF4500;
  color: #000;
}

.ai-btn:disabled {
  opacity: 0.4;
  cursor: wait;
}

.ai-icon {
  font-size: 14px;
}

/* Creator panel */
.creator-panel {
  margin-top: 8px;
  border: 1px solid #333;
  background: #0a0a0a;
  padding: 10px;
}

.creator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.creator-label {
  color: #888;
  font-size: 10px;
  letter-spacing: 0.3px;
}

.ai-input {
  width: 100%;
  padding: 8px;
  border: 1px solid #222;
  background: #000;
  color: #ddd;
  font-family: inherit;
  font-size: 12px;
  resize: vertical;
  line-height: 1.5;
}

.ai-input:focus {
  outline: none;
  border-color: #FF4500;
}

.ai-input::placeholder {
  color: #444;
}

.creator-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.hint {
  color: #444;
  font-size: 10px;
}

.generate-btn {
  padding: 6px 16px;
  border: none;
  background: #FF4500;
  color: #000;
  font-family: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.5px;
}

.generate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.gen-error {
  margin-top: 8px;
  padding: 6px 8px;
  border: 1px solid #ff3333;
  background: #1a0000;
  color: #ff6666;
  font-size: 11px;
}

/* Preview */
.preview-panel {
  margin-top: 10px;
  border: 1px solid #2a2a2a;
  padding: 10px;
  background: #050505;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
}

.preview-title {
  font-weight: 700;
  color: #fff;
  font-size: 13px;
}

.preview-meta {
  color: #666;
  font-size: 10px;
  white-space: nowrap;
}

.preview-question {
  color: #FF4500;
  font-size: 11px;
  margin-bottom: 8px;
  line-height: 1.4;
}

.preview-actors {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 10px;
}

.actor-tag {
  padding: 2px 6px;
  border: 1px solid #333;
  color: #aaa;
  font-size: 10px;
}

.preview-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.use-btn,
.save-btn {
  padding: 5px 14px;
  border: 1px solid #444;
  background: transparent;
  color: #ccc;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}

.use-btn:hover {
  border-color: #ccc;
  color: #fff;
}

.save-btn {
  border-color: #FF4500;
  color: #FF4500;
}

.save-btn:hover {
  background: #FF4500;
  color: #000;
}
</style>
