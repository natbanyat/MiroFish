<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <div class="nav-center">
        <CostTierToggle />
        <button class="model-gear" @click="showModelRouter = true" title="Model Routing">&#x2699;</button>
      </div>
      <ModelRouter :visible="showModelRouter" @close="showModelRouter = false" />
      <div class="nav-links">
        <a href="https://github.com/666ghj/MiroFish" target="_blank" class="github-link">
          Visit our GitHub <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">Universal Swarm Intelligence Engine</span>
            <span class="version-text">/ v0.1-preview</span>
          </div>
          
          <h1 class="main-title">
            Upload any report<br>
            <span class="gradient-text">Simulate the future</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              Even from a single paragraph, <span class="highlight-bold">MiroFish</span> extracts real-world seeds and auto-generates a parallel world of up to <span class="highlight-orange">millions of Agents</span>. Inject variables from a god-view perspective and find <span class="highlight-code">"local optimal solutions"</span> through complex group dynamics.
            </p>
            <p class="slogan-text">
              Let the future rehearse in Agent swarms. Let decisions win through simulation.<span class="blinking-cursor">_</span>
            </p>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <!-- Logo 区域 -->
          <div class="logo-container">
            <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="MiroFish Logo" class="hero-logo" />
          </div>
          
          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> System Status
          </div>
          
          <h2 class="section-title">Ready</h2>
          <p class="section-desc">
            Prediction engine on standby. Upload one or more unstructured files to initialize a simulation.
          </p>
          
          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">Low Cost</div>
              <div class="metric-label">~$5 per simulation</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">Scalable</div>
              <div class="metric-label">Up to 1M+ Agent simulation</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 (新增区域) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> Workflow
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">Graph Build</div>
                  <div class="step-desc">Reality seed extraction & individual/group memory injection & GraphRAG construction</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">Environment Setup</div>
                  <div class="step-desc">Entity relation extraction & persona generation & simulation parameter injection</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">Run Simulation</div>
                  <div class="step-desc">Dual-platform parallel simulation & auto prediction parsing & dynamic memory updates</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">Report Generation</div>
                  <div class="step-desc">ReportAgent uses a rich toolset to deeply interact with the post-simulation environment</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">Deep Interaction</div>
                  <div class="step-desc">Chat with any individual in the simulated world & converse with ReportAgent</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：交互控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- 上传区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / Reality Seed</span>
                <span class="console-meta">Upload files or generate with AI</span>
              </div>

              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />

                <div v-if="files.length === 0 && !seedGenerating" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">Drag & drop files here</div>
                  <div class="upload-hint">or click to browse</div>
                </div>

                <div v-else-if="seedGenerating" class="upload-placeholder">
                  <div class="upload-icon seed-spin">*</div>
                  <div class="upload-title">Generating reality seed...</div>
                  <div class="upload-hint">AI is writing a background document</div>
                </div>

                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">{{ file._aiGenerated ? '*' : '' }}</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">&times;</button>
                  </div>
                </div>
              </div>

              <div class="seed-text-card" :class="{ active: seedText.trim().length > 0 }">
                <div class="seed-text-header">
                  <div>
                    <div class="seed-text-title">Paste reality seed text</div>
                    <div class="seed-text-subtitle">Direct text works too. We wrap it into a .txt seed behind the scenes.</div>
                  </div>
                  <button
                    v-if="seedText.trim()"
                    class="seed-text-clear"
                    @click="seedText = ''"
                    :disabled="loading"
                  >
                    Clear
                  </button>
                </div>

                <textarea
                  v-model="seedText"
                  class="seed-textarea"
                  placeholder="Paste notes, a briefing, a transcript, or any raw reality seed here..."
                  rows="6"
                  :disabled="loading"
                ></textarea>

                <div class="seed-text-footer">
                  <span>{{ seedTextStats }}</span>
                  <span v-if="seedText.trim()">Will upload as pasted-reality-seed.txt</span>
                </div>
              </div>

              <!-- Seed controls: saved dropdown + generate new -->
              <div class="seed-controls">
                <!-- Saved seeds dropdown -->
                <div class="seed-saved-row">
                  <select
                    class="seed-select"
                    v-model="selectedSeedFilename"
                    :disabled="seedGenerating || loading"
                    @change="onSeedSelected"
                  >
                    <option value="">— Pick a saved seed —</option>
                    <option v-for="s in savedSeeds" :key="s.filename" :value="s.filename">
                      {{ s.title }} ({{ s.word_count }}w)
                    </option>
                  </select>
                </div>

                <!-- Generate new seed -->
                <div class="seed-gen-bar">
                  <input
                    v-model="seedDescription"
                    class="seed-input"
                    placeholder="Or describe a scenario to generate a new seed..."
                    :disabled="seedGenerating || loading"
                    @keydown.enter="generateRealitySeed"
                  />
                  <button
                    class="seed-btn"
                    @click="generateRealitySeed"
                    :disabled="!seedDescription.trim() || seedGenerating || loading"
                  >
                    <span v-if="!seedGenerating">* Generate Seed</span>
                    <span v-else>Generating...</span>
                  </button>
                </div>
                <div v-if="seedError" class="seed-error">{{ seedError }}</div>

                <!-- Scenario options panel (shown after a seed is loaded) -->
                <div v-if="activeSeedContent && !scenarioOptionsLoading && scenarioOptions.length === 0" class="seed-actions-row">
                  <span class="seed-loaded-label">Seed loaded: {{ activeSeedTitle }}</span>
                  <button class="seed-btn" @click="generateScenarioOpts" :disabled="loading">
                    * Generate Scenario Options
                  </button>
                </div>

                <div v-if="scenarioOptionsLoading" class="seed-options-loading">
                  <span class="seed-spin">*</span> Generating scenario options...
                </div>

                <!-- 4-5 scenario option cards -->
                <div v-if="scenarioOptions.length > 0" class="scenario-options-panel">
                  <div class="options-header">Pick a scenario to expand:</div>
                  <div
                    v-for="opt in scenarioOptions"
                    :key="opt.id"
                    class="scenario-option-card"
                    :class="{ 'selected': selectedOption?.id === opt.id, 'expanding': expandingOption === opt.id }"
                    @click="pickScenarioOption(opt)"
                  >
                    <div class="opt-title">{{ opt.title }}</div>
                    <div class="opt-angle">{{ opt.angle }}</div>
                    <div class="opt-question">{{ opt.prediction_question }}</div>
                    <div v-if="expandingOption === opt.id" class="opt-expanding">Expanding...</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分割线 -->
            <div class="console-divider">
              <span>Input Parameters</span>
            </div>

            <!-- 输入区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / Simulation Prompt</span>
              </div>
              <ScenarioCreator @select-prompt="onScenarioSelect" />
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// Describe your simulation or prediction goal in natural language — or use AI Create above to generate a structured prompt"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">Engine: MiroFish-V1.0</div>
              </div>
            </div>

            <!-- 启动按钮 -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">Launch Engine</span>
                <span v-else>Initializing...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <OperationsDashboard />

      <!-- 历史项目数据库 -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import OperationsDashboard from '../components/OperationsDashboard.vue'
import CostTierToggle from '../components/CostTierToggle.vue'
import ScenarioCreator from '../components/ScenarioCreator.vue'
import ModelRouter from '../components/ModelRouter.vue'
import { generateSeed, listSeeds, getSeed, generateScenarioOptions, expandScenarioOption } from '../api/scenarios'

const router = useRouter()

// 表单数据
const formData = ref({
  simulationRequirement: ''
})

// 文件列表
const files = ref([])
const seedText = ref('')

// 状态
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// 文件输入引用
const fileInput = ref(null)

// 计算属性:是否可以提交
const hasRealitySeed = computed(() => {
  return files.value.length > 0 || seedText.value.trim().length > 0
})

const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && hasRealitySeed.value
})

const seedTextStats = computed(() => {
  const text = seedText.value.trim()
  const chars = text.length
  const words = text ? text.split(/\s+/).filter(Boolean).length : 0
  if (!chars) return 'No pasted text yet'
  return `${chars} chars · ${words} words`
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 移除文件
const removeFile = (index) => {
  files.value.splice(index, 1)
}

const buildPendingFiles = () => {
  const pendingFiles = [...files.value]

  if (seedText.value.trim()) {
    const blob = new Blob([seedText.value.trim()], { type: 'text/plain' })
    pendingFiles.push(new File([blob], 'pasted-reality-seed.txt', { type: 'text/plain' }))
  }

  return pendingFiles
}

// Model router panel
const showModelRouter = ref(false)

// Reality seed generation
const seedDescription = ref('')
const seedGenerating = ref(false)
const seedError = ref('')

// Saved seeds
const savedSeeds = ref([])
const selectedSeedFilename = ref('')
const activeSeedContent = ref('')
const activeSeedTitle = ref('')

// Scenario options
const scenarioOptions = ref([])
const scenarioOptionsLoading = ref(false)
const selectedOption = ref(null)
const expandingOption = ref(null)

const loadSavedSeeds = async () => {
  try {
    const res = await listSeeds()
    if (res && res.seeds) savedSeeds.value = res.seeds
  } catch (e) {
    console.warn('Could not load saved seeds:', e)
  }
}

const onSeedSelected = async () => {
  if (!selectedSeedFilename.value) {
    activeSeedContent.value = ''
    activeSeedTitle.value = ''
    scenarioOptions.value = []
    return
  }
  try {
    const res = await getSeed(selectedSeedFilename.value)
    if (res && res.content) {
      activeSeedContent.value = res.content
      activeSeedTitle.value = res.title
      scenarioOptions.value = []
      selectedOption.value = null
      // Add to upload files
      _addSeedAsFile(res.content, selectedSeedFilename.value, res.title)
    }
  } catch (e) {
    seedError.value = 'Failed to load seed: ' + (e.message || String(e))
  }
}

const _addSeedAsFile = (content, filename, title) => {
  // Remove any existing seed file
  files.value = files.value.filter(f => !f._aiGenerated)
  const blob = new Blob([content], { type: 'text/markdown' })
  const file = new File([blob], filename, { type: 'text/markdown' })
  file._aiGenerated = true
  file._seedTitle = title
  files.value.push(file)
}

const generateRealitySeed = async () => {
  if (!seedDescription.value.trim() || seedGenerating.value) return
  seedGenerating.value = true
  seedError.value = ''

  try {
    const res = await generateSeed(seedDescription.value.trim())
    if (!res || !res.success) {
      throw new Error((res && res.error) || 'Seed generation returned unsuccessful')
    }

    // Fetch full content then treat as active seed
    const full = await getSeed(res.filename)
    activeSeedContent.value = full ? full.content : (res.content_preview || '')
    activeSeedTitle.value = res.title
    scenarioOptions.value = []
    selectedOption.value = null

    _addSeedAsFile(activeSeedContent.value, res.filename, res.title)

    // Refresh saved seeds list
    await loadSavedSeeds()
    selectedSeedFilename.value = res.filename

    seedDescription.value = ''
  } catch (e) {
    console.error('Seed generation error:', e)
    seedError.value = (e && e.message) || String(e) || 'Seed generation failed'
  } finally {
    seedGenerating.value = false
  }
}

const generateScenarioOpts = async () => {
  if (!activeSeedContent.value) return
  scenarioOptionsLoading.value = true
  scenarioOptions.value = []
  try {
    const res = await generateScenarioOptions(activeSeedContent.value)
    if (res && res.options) scenarioOptions.value = res.options
  } catch (e) {
    seedError.value = 'Failed to generate options: ' + (e.message || String(e))
  } finally {
    scenarioOptionsLoading.value = false
  }
}

const pickScenarioOption = async (opt) => {
  if (expandingOption.value) return
  expandingOption.value = opt.id
  selectedOption.value = opt
  try {
    const res = await expandScenarioOption(activeSeedContent.value, opt)
    if (res && res.rendered_prompt) {
      formData.value.simulationRequirement = res.rendered_prompt
      // Clear the options panel once picked
      scenarioOptions.value = []
      selectedOption.value = null
    }
  } catch (e) {
    seedError.value = 'Failed to expand scenario: ' + (e.message || String(e))
  } finally {
    expandingOption.value = null
  }
}

// Load seeds on mount
loadSavedSeeds()

// 场景选择回调
const onScenarioSelect = (prompt) => {
  formData.value.simulationRequirement = prompt
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// 开始模拟 - 立即跳转，API调用在Process页面进行
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  const pendingFiles = buildPendingFiles()
  if (!pendingFiles.length) return
  
  // 存储待上传的数据
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(pendingFiles, formData.value.simulationRequirement)
    
    // 立即跳转到Process页面（使用特殊标识表示新建项目）
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* 全局变量与重置 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  /* 
    使用 Space Grotesk 作为主要标题字体，JetBrains Mono 作为代码/标签字体
    确保已在 index.html 引入这些 Google Fonts 
  */
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 顶部导航 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
  position: relative;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.nav-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
}

.model-gear {
  background: none;
  border: 1px solid #444;
  color: #888;
  width: 28px;
  height: 28px;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.model-gear:hover {
  color: #FF4500;
  border-color: #FF4500;
}

.nav-links {
  display: flex;
  align-items: center;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.github-link:hover {
  opacity: 0.8;
}

.arrow {
  font-family: sans-serif;
}

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}

.version-text {
  color: #999;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 0.8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.logo-container {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  padding-right: 40px;
}

.hero-logo {
  max-width: 500px; /* 调整logo大小 */
  width: 100%;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* 左侧面板 */
.left-panel {
  flex: 0.8;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 项目模拟步骤介绍 */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* 右侧交互控制台 */
.right-panel {
  flex: 1.2;
}

.console-box {
  border: 1px solid #CCC; /* 外部实线 */
  padding: 8px; /* 内边距形成双重边框感 */
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.upload-zone {
  border: 1px dashed #CCC;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #FAFAFA;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #F0F0F0;
  border-color: #999;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.seed-text-card {
  margin-top: 12px;
  border: 1px solid #E5E5E5;
  background: #FAFAFA;
  padding: 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.seed-text-card.active {
  border-color: #FF4500;
  box-shadow: inset 0 0 0 1px rgba(255, 69, 0, 0.08);
}

.seed-text-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.seed-text-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #111;
}

.seed-text-subtitle {
  margin-top: 3px;
  font-size: 0.72rem;
  color: #888;
  line-height: 1.5;
}

.seed-text-clear {
  border: 1px solid #DDD;
  background: #FFF;
  color: #666;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  padding: 6px 10px;
  cursor: pointer;
  height: fit-content;
}

.seed-textarea {
  width: 100%;
  min-height: 140px;
  border: 1px solid #DDD;
  background: #FFF;
  padding: 12px 14px;
  resize: vertical;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  line-height: 1.6;
  color: #222;
}

.seed-textarea:focus {
  outline: none;
  border-color: #FF4500;
}

.seed-text-footer {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: #888;
}

/* Seed controls wrapper */
.seed-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.seed-saved-row {
  display: flex;
  gap: 6px;
}

.seed-select {
  flex: 1;
  padding: 7px 10px;
  border: 1px solid #DDD;
  background: #FAFAFA;
  font-family: monospace;
  font-size: 0.78rem;
  color: #333;
  cursor: pointer;
}

.seed-select:focus {
  outline: none;
  border-color: #FF4500;
}

.seed-actions-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}

.seed-loaded-label {
  font-size: 0.72rem;
  color: #888;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.seed-options-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  color: #888;
  padding: 6px 0;
}

/* Scenario options cards */
.scenario-options-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.options-header {
  font-size: 0.72rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.scenario-option-card {
  border: 1px solid #E0E0E0;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: #FAFAFA;
}

.scenario-option-card:hover {
  border-color: #FF4500;
  background: #FFF8F6;
}

.scenario-option-card.selected,
.scenario-option-card.expanding {
  border-color: #FF4500;
  background: #FFF8F6;
}

.opt-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #222;
  margin-bottom: 3px;
}

.opt-angle {
  font-size: 0.75rem;
  color: #FF4500;
  margin-bottom: 3px;
}

.opt-question {
  font-size: 0.73rem;
  color: #666;
  font-style: italic;
}

.opt-expanding {
  font-size: 0.72rem;
  color: #FF4500;
  margin-top: 4px;
}

/* Seed generator bar */
.seed-gen-bar {
  display: flex;
  gap: 6px;
}

.seed-input {
  flex: 1;
  padding: 7px 10px;
  border: 1px solid #DDD;
  background: var(--white);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #333;
}

.seed-input:focus {
  outline: none;
  border-color: #FF4500;
}

.seed-input::placeholder {
  color: #BBB;
}

.seed-btn {
  padding: 7px 14px;
  border: 1px solid #FF4500;
  background: transparent;
  color: #FF4500;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  letter-spacing: 0.3px;
  transition: all 0.15s;
}

.seed-btn:hover:not(:disabled) {
  background: #FF4500;
  color: #000;
}

.seed-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.seed-error {
  margin-top: 6px;
  padding: 5px 8px;
  border: 1px solid #FF4500;
  background: #FFF5F0;
  color: #CC3700;
  font-family: var(--font-mono);
  font-size: 0.7rem;
}

.seed-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 1px;
}

.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

/* 可点击状态（非禁用） */
.start-engine-btn:not(:disabled) {
  background: var(--black);
  border: 1px solid var(--black);
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  transform: none;
  border: 1px solid #E5E5E5;
}

/* 引导动画：微妙的边框脉冲 */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }
  
  .hero-section {
    flex-direction: column;
  }
  
  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }
  
  .hero-logo {
    max-width: 200px;
    margin-bottom: 20px;
  }

  .seed-text-header,
  .seed-text-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
