import type { ProjectsResponse } from './types'

/** Dev-only: `?mock=1` serves src/mocks/sample.json instead of the backend. Stripped from production builds. */
export const isMockMode = (): boolean =>
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('mock') === '1'

export async function fetchProjects(refresh = false): Promise<ProjectsResponse> {
  // `import.meta.env.DEV` is a compile-time constant, so this branch (and the JSON chunk) is removed in production.
  if (import.meta.env.DEV && isMockMode()) {
    const sample = await import('./mocks/sample.json')
    return sample.default as ProjectsResponse
  }

  const response = await fetch(`/api/projects${refresh ? '?refresh=true' : ''}`)
  if (!response.ok) {
    throw new Error(`Backend responded with ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as ProjectsResponse
}
