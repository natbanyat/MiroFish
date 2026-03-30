import service from './index'

export function getCostTier() {
  return service.get('/api/settings/cost-tier')
}

export function setCostTier(tier) {
  return service.post('/api/settings/cost-tier', { tier })
}

export function getModelRouting() {
  return service.get('/api/settings/model-routing')
}

export function setTaskModel(task, provider, model) {
  return service.post('/api/settings/model-routing', { task, provider, model })
}

export function resetTaskModel(task) {
  return service.post('/api/settings/model-routing', { task, reset: true })
}

export function resetAllModelRouting() {
  return service.post('/api/settings/model-routing/reset')
}
