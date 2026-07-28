const TOKEN_KEY = 'weekly_scorer_admin_token'
const USER_KEY = 'weekly_scorer_admin_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function decodeToken(token) {
  try {
    // token 格式: base64(payload).hex(signature)，payload 在索引 0
    const payload = token.split('.')[0]
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

function isTokenExpired(token) {
  const decoded = decodeToken(token)
  if (!decoded || !decoded.exp) return true
  return decoded.exp * 1000 < Date.now()
}

export function setAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user || {}))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getAdminUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || '{}')
  } catch {
    return {}
  }
}

export function isAdminLoggedIn() {
  const token = getToken()
  if (!token) return false
  if (isTokenExpired(token)) {
    clearAuth()
    return false
  }
  return true
}
