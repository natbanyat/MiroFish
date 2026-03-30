import service from './index'

export function listScenarios() {
  return service.get('/api/scenarios')
}

export function getScenario(id) {
  return service.get(`/api/scenarios/${id}`)
}

export function saveScenario(data) {
  return service.post('/api/scenarios', data)
}

export function deleteScenario(id) {
  return service.delete(`/api/scenarios/${id}`)
}

export function generateScenario(description) {
  return service.post('/api/scenarios/generate', { description })
}

export function generateSeed(description) {
  return service.post('/api/scenarios/generate-seed', { description })
}

export function listSeeds() {
  return service.get('/api/scenarios/seeds')
}

export function getSeed(filename) {
  return service.get(`/api/scenarios/seeds/${filename}`)
}

export function generateScenarioOptions(seedContent) {
  return service.post('/api/scenarios/generate-scenario-options', { seed_content: seedContent })
}

export function expandScenarioOption(seedContent, option) {
  return service.post('/api/scenarios/expand-scenario-option', { seed_content: seedContent, option })
}
