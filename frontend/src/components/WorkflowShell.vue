<template>
  <div class="workflow-shell">
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH</div>
      </div>

      <div class="header-center">
        <div class="view-switcher">
          <button
            v-for="mode in viewModes"
            :key="mode"
            class="switch-btn"
            :class="{ active: modelValue === mode }"
            @click="$emit('update:modelValue', mode)"
          >
            {{ viewModeLabels[mode] || mode }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Step {{ currentStep }}/5</span>
          <span class="step-name">{{ stepName }}</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <main class="content-area">
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <slot name="left" />
      </div>

      <div class="panel-wrapper right" :class="rightPanelClass" :style="rightPanelStyle">
        <slot name="right" />
      </div>
    </main>

    <StageNav v-if="showStageNav" :currentStep="currentStep" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import StageNav from './StageNav.vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: 'split'
  },
  currentStep: {
    type: Number,
    required: true
  },
  stepName: {
    type: String,
    required: true
  },
  statusText: {
    type: String,
    required: true
  },
  statusClass: {
    type: String,
    default: 'processing'
  },
  showStageNav: {
    type: Boolean,
    default: true
  },
  rightPanelClass: {
    type: [String, Array, Object],
    default: ''
  },
  viewModes: {
    type: Array,
    default: () => ['graph', 'split', 'workbench']
  },
  viewModeLabels: {
    type: Object,
    default: () => ({
      graph: 'Graph',
      split: 'Split',
      workbench: 'Workbench'
    })
  }
})

defineEmits(['update:modelValue'])

const router = useRouter()

const leftPanelStyle = computed(() => {
  if (props.modelValue === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (props.modelValue === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (props.modelValue === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (props.modelValue === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})
</script>

<style scoped>
.workflow-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

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
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
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

.status-indicator.ready .dot,
.status-indicator.completed .dot {
  background: #4CAF50;
}

.status-indicator.processing .dot {
  background: #FF5722;
  animation: pulse 1s infinite;
}

.status-indicator.error .dot {
  background: #F44336;
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}

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
</style>
