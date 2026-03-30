<template>
  <div class="cost-tier-toggle">
    <div class="tier-label">MODEL TIER</div>
    <div class="tier-buttons">
      <button
        v-for="tier in tiers"
        :key="tier.id"
        :class="['tier-btn', { active: currentTier === tier.id }]"
        @click="selectTier(tier.id)"
        :disabled="switching"
      >
        <span class="tier-name">{{ tier.label }}</span>
        <span class="tier-cost">{{ tier.est }}</span>
      </button>
    </div>
    <div class="tier-detail" v-if="tierInfo">
      <span class="tier-providers">
        <span
          v-for="(configured, provider) in tierInfo.providers_configured"
          :key="provider"
          :class="['provider-dot', { connected: configured }]"
          :title="provider + (configured ? ' (connected)' : ' (no key)')"
        >{{ provider.charAt(0).toUpperCase() }}</span>
      </span>
      <span class="tier-models" v-if="tierInfo.boost_models">
        {{ tierInfo.boost_models[0] }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCostTier, setCostTier } from '../api/settings'

const tiers = [
  { id: 'cheap', label: 'CHEAP', est: '~$0.10' },
  { id: 'medium', label: 'MEDIUM', est: '~$0.50' },
  { id: 'expensive', label: 'QUALITY', est: '~$1.00' },
]

const currentTier = ref('cheap')
const tierInfo = ref(null)
const switching = ref(false)

async function loadTier() {
  try {
    const res = await getCostTier()
    currentTier.value = res.current_tier || 'cheap'
    tierInfo.value = res
  } catch (e) {
    console.warn('Failed to load cost tier:', e)
  }
}

async function selectTier(tier) {
  if (tier === currentTier.value || switching.value) return
  switching.value = true
  try {
    const res = await setCostTier(tier)
    currentTier.value = res.current_tier || tier
    tierInfo.value = res
  } catch (e) {
    console.error('Failed to set cost tier:', e)
  } finally {
    switching.value = false
  }
}

onMounted(loadTier)
</script>

<style scoped>
.cost-tier-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.tier-label {
  color: #666;
  letter-spacing: 0.5px;
  font-size: 10px;
}

.tier-buttons {
  display: flex;
  border: 1px solid #000;
}

.tier-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 12px;
  background: #fff;
  border: none;
  border-right: 1px solid #000;
  cursor: pointer;
  transition: all 0.15s;
  min-width: 72px;
}

.tier-btn:last-child {
  border-right: none;
}

.tier-btn:hover:not(.active):not(:disabled) {
  background: #f5f5f5;
}

.tier-btn.active {
  background: #000;
  color: #fff;
}

.tier-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.tier-name {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
}

.tier-cost {
  font-size: 9px;
  opacity: 0.6;
  margin-top: 1px;
}

.tier-btn.active .tier-cost {
  color: #FF4500;
  opacity: 1;
}

.tier-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #999;
  font-size: 10px;
}

.tier-providers {
  display: flex;
  gap: 3px;
}

.provider-dot {
  width: 16px;
  height: 16px;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  background: #eee;
  color: #aaa;
  cursor: default;
}

.provider-dot.connected {
  background: #000;
  color: #fff;
}

.tier-models {
  color: #666;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
