const CLIENT_KEY = 'minicpmo_client_id'

function randomId(prefix: string): string {
  const cryptoObj = typeof crypto !== 'undefined' ? crypto : null
  const rand = cryptoObj?.randomUUID
    ? cryptoObj.randomUUID().replace(/-/g, '').slice(0, 12)
    : Math.random().toString(36).slice(2, 14)
  return `${prefix}_${Date.now().toString(36)}_${rand}`
}

export function getClientId(): string {
  try {
    let id = localStorage.getItem(CLIENT_KEY)
    if (!id) {
      id = randomId('c')
      localStorage.setItem(CLIENT_KEY, id)
    }
    return id
  } catch {
    return randomId('c_tmp')
  }
}

const pageSessionId = randomId('p')

export function getPageSessionId(): string {
  return pageSessionId
}

export function getClientSurface(): string {
  const path = window.location.pathname || ''
  if (path.startsWith('/mobile-omni')) return 'mobile_omni'
  if (path.startsWith('/mobile')) return 'mobile'
  if (path.startsWith('/realtime')) return 'realtime_demo'
  if (
    path.startsWith('/omni') ||
    path.startsWith('/audio_duplex') ||
    path.startsWith('/half_duplex') ||
    path.startsWith('/turnbased')
  ) {
    return 'desktop'
  }
  return 'unknown'
}

export function appendClientIdentity(url: string): string {
  try {
    const u = new URL(url, window.location.href)
    u.searchParams.set('client_id', getClientId())
    u.searchParams.set('page_session_id', getPageSessionId())
    u.searchParams.set('page_route', window.location.pathname || '/')
    u.searchParams.set('client_surface', getClientSurface())
    return u.toString()
  } catch {
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}client_id=${encodeURIComponent(getClientId())}&page_session_id=${encodeURIComponent(getPageSessionId())}&page_route=${encodeURIComponent(window.location.pathname || '/')}&client_surface=${encodeURIComponent(getClientSurface())}`
  }
}

export function installClientIdentityGlobal(): void {
  ;(window as unknown as {
    ClientIdentity?: {
      getClientId: () => string
      getPageSessionId: () => string
      getClientSurface: () => string
      appendToUrl: (url: string) => string
    }
  }).ClientIdentity = {
    getClientId,
    getPageSessionId,
    getClientSurface,
    appendToUrl: appendClientIdentity,
  }
}
