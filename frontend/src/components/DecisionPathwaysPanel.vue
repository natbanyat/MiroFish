<template>
  <div class="decision-pathways-panel">
    <div class="pathways-header">
      <div>
        <p class="eyebrow">Phase 3 Preview</p>
        <h2>Decision Pathways</h2>
        <p class="pathways-summary">{{ pathways?.root_question || 'Scenario pathways will appear once report evidence is available.' }}</p>
      </div>
      <div class="pathways-metrics" v-if="pathways">
        <div class="metric-chip">
          <span class="metric-label">Branches</span>
          <span class="metric-value">{{ pathways.pathways?.length || 0 }}</span>
        </div>
        <div class="metric-chip">
          <span class="metric-label">Evidence</span>
          <span class="metric-value">{{ pathways.evidence_ledger?.length || 0 }}</span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="panel-state loading-state">
      <div class="spinner"></div>
      <span>Building pathway branches from report evidence...</span>
    </div>

    <div v-else-if="error" class="panel-state error-state">
      <span>{{ error }}</span>
      <button class="retry-btn" @click="$emit('refresh')">Retry</button>
    </div>

    <template v-else-if="pathways?.pathways?.length">
      <div class="tree-shell">
        <div class="tree-root">
          <span class="root-label">Decision root</span>
          <h3>{{ pathways.title }}</h3>
          <p>{{ pathways.methodology }}</p>
        </div>
        <div class="tree-branches">
          <article
            v-for="branch in pathways.pathways"
            :key="branch.id"
            class="branch-card"
            :class="`branch-card--${branch.stance}`"
          >
            <div class="branch-topline">
              <span class="branch-pill">{{ branch.label }}</span>
              <span class="branch-confidence" :class="`branch-confidence--${branch.confidence}`">{{ branch.confidence }}</span>
            </div>
            <div class="branch-probability-row">
              <strong>{{ branch.probability }}%</strong>
              <span>evidence-weighted path probability</span>
            </div>
            <div class="branch-probability-bar">
              <span :style="{ width: `${branch.probability}%` }"></span>
            </div>
            <p class="branch-description">{{ branch.summary }}</p>

            <div v-if="branch.key_signals?.length" class="signal-block">
              <span class="block-label">Key signals</span>
              <div class="signal-list">
                <span v-for="signal in branch.key_signals" :key="signal" class="signal-chip">{{ signal }}</span>
              </div>
            </div>

            <div class="evidence-block">
              <span class="block-label">Evidence trace</span>
              <div class="evidence-list">
                <div v-for="item in branch.evidence" :key="`${branch.id}-${item.section_ref}-${item.snippet}`" class="evidence-item">
                  <div class="evidence-meta">
                    <span class="section-ref">{{ item.section_ref }}</span>
                    <span class="section-title">{{ item.section_title }}</span>
                    <span class="evidence-weight">{{ item.weight.toFixed(2) }}</span>
                  </div>
                  <p>{{ item.snippet }}</p>
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div v-if="pathways.evidence_ledger?.length" class="ledger-block">
        <div class="ledger-header">
          <div>
            <p class="eyebrow">Traceability</p>
            <h3>Evidence ledger</h3>
          </div>
          <button class="refresh-btn" @click="$emit('refresh')">Refresh pathways</button>
        </div>
        <div class="ledger-list">
          <div v-for="item in pathways.evidence_ledger" :key="`ledger-${item.section_ref}-${item.snippet}`" class="ledger-row">
            <div>
              <span class="section-ref">{{ item.section_ref }}</span>
              <span class="ledger-title">{{ item.section_title }}</span>
            </div>
            <p>{{ item.snippet }}</p>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="panel-state empty-state">
      <span>Decision pathways will populate once the report has enough section evidence.</span>
      <button class="retry-btn" @click="$emit('refresh')">Refresh</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  pathways: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

defineEmits(['refresh'])
</script>

<style scoped>
.decision-pathways-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pathways-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid #E5E7EB;
  border-radius: 14px;
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
}

.eyebrow {
  margin: 0 0 6px 0;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6B7280;
}

.pathways-header h2,
.ledger-header h3,
.tree-root h3 {
  margin: 0;
  color: #111827;
  font-family: 'Times New Roman', Times, serif;
}

.pathways-summary,
.tree-root p {
  margin: 8px 0 0 0;
  color: #4B5563;
  line-height: 1.6;
  font-size: 14px;
}

.pathways-metrics {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.metric-chip {
  min-width: 92px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #E5E7EB;
  background: #FFFFFF;
}

.metric-label {
  display: block;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #9CA3AF;
  margin-bottom: 4px;
}

.metric-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}

.tree-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.tree-root {
  position: relative;
  padding: 18px 20px;
  border-radius: 16px;
  background: #111827;
  color: #F9FAFB;
}

.root-label {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.tree-root h3,
.tree-root p {
  color: inherit;
}

.tree-branches {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.branch-card {
  padding: 18px;
  border-radius: 16px;
  border: 1px solid #E5E7EB;
  background: #FFFFFF;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
}

.branch-card--primary {
  border-color: #CBD5E1;
}

.branch-card--upside {
  border-color: #BBF7D0;
  background: linear-gradient(180deg, #FFFFFF 0%, #F0FDF4 100%);
}

.branch-card--downside {
  border-color: #FECACA;
  background: linear-gradient(180deg, #FFFFFF 0%, #FEF2F2 100%);
}

.branch-topline,
.branch-probability-row,
.evidence-meta,
.ledger-header,
.ledger-row > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.branch-pill,
.branch-confidence,
.section-ref,
.evidence-weight,
.retry-btn,
.refresh-btn {
  font-family: 'JetBrains Mono', monospace;
}

.branch-pill {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  background: #F3F4F6;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #374151;
}

.branch-confidence {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6B7280;
}

.branch-confidence--high { color: #047857; }
.branch-confidence--medium { color: #B45309; }
.branch-confidence--low { color: #B91C1C; }

.branch-probability-row {
  margin-top: 16px;
}

.branch-probability-row strong {
  font-size: 28px;
  color: #111827;
}

.branch-probability-row span {
  color: #6B7280;
  font-size: 12px;
  text-align: right;
  max-width: 130px;
}

.branch-probability-bar {
  margin-top: 10px;
  width: 100%;
  height: 8px;
  background: #E5E7EB;
  border-radius: 999px;
  overflow: hidden;
}

.branch-probability-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #111827;
}

.branch-card--upside .branch-probability-bar span { background: #15803D; }
.branch-card--downside .branch-probability-bar span { background: #DC2626; }

.branch-description,
.evidence-item p,
.ledger-row p {
  margin: 14px 0 0 0;
  color: #374151;
  font-size: 13px;
  line-height: 1.7;
}

.signal-block,
.evidence-block,
.ledger-block {
  margin-top: 16px;
}

.block-label {
  display: block;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #6B7280;
}

.signal-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.signal-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  font-size: 12px;
  color: #334155;
}

.evidence-list,
.ledger-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-item,
.ledger-row {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid #E5E7EB;
}

.section-ref {
  display: inline-flex;
  padding: 3px 7px;
  border-radius: 999px;
  background: #111827;
  color: #FFFFFF;
  font-size: 10px;
}

.section-title,
.ledger-title {
  flex: 1;
  color: #374151;
  font-size: 12px;
  font-weight: 600;
}

.evidence-weight {
  font-size: 11px;
  color: #6B7280;
}

.ledger-block {
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid #E5E7EB;
  background: #FFFFFF;
}

.retry-btn,
.refresh-btn {
  border: 1px solid #D1D5DB;
  background: #FFFFFF;
  color: #374151;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 11px;
  cursor: pointer;
}

.retry-btn:hover,
.refresh-btn:hover {
  background: #F9FAFB;
}

.panel-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 28px;
  border: 1px dashed #D1D5DB;
  border-radius: 14px;
  background: #FFFFFF;
  color: #6B7280;
  text-align: center;
}

.panel-state.error-state {
  border-color: #FECACA;
  color: #B91C1C;
}

.spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid #E5E7EB;
  border-top-color: #111827;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .pathways-header {
    flex-direction: column;
  }

  .tree-branches {
    grid-template-columns: 1fr;
  }
}
</style>
