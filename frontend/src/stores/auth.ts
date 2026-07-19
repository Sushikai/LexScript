import { defineStore } from "pinia"
import { ref, computed } from "vue"

const API = "/api/v1"

export interface User {
  id: number
  username: string
  email?: string
  role: string
  display_name?: string
}

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem("lex_access_token"))

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  function getToken(): string | null {
    return token.value
  }

  function setTokenHeader(): Record<string, string> {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {}
  }

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const r = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      })
      const d = await r.json()
      if (d.ok && d.data?.access_token) {
        token.value = d.data.access_token
        localStorage.setItem("lex_access_token", d.data.access_token)
        // Fetch user info
        const u = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${d.data.access_token}` },
        })
        const ud = await u.json()
        if (ud.ok) user.value = ud.data
        return true
      }
      return false
    } catch {
      return false
    }
  }

  async function autoLogin() {
    // Try stored token first
    if (token.value) {
      try {
        const u = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${token.value}` },
        })
        const ud = await u.json()
        if (ud.ok) {
          user.value = ud.data
          return
        }
      } catch { /* fall through to login */ }
    }
    // Auto-login as root (default dev account)
    try {
      const r = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "root", password: "123456" }),
      })
      const d = await r.json()
      if (d.ok) {
        token.value = d.data.access_token
        localStorage.setItem("lex_access_token", d.data.access_token)
        const u = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${d.data.access_token}` },
        })
        const ud = await u.json()
        if (ud.ok) user.value = ud.data
      }
    } catch {
      user.value = { id: 0, username: "root", role: "admin", display_name: "root" }
    }
  }

  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem("lex_access_token")
  }

  return { user, token, isAuthenticated, getToken, setTokenHeader, login, autoLogin, logout }
})
