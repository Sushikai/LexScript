import { ref, computed } from "vue"
import type { Session } from "@/types"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"

function authHeaders(): Record<string, string> {
  const store = useAuthStore()
  return store.setTokenHeader()
}

const sessions = ref<Session[]>([])
const currentSessionId = ref<string | null>(null)
const loading = ref(false)
const searchQuery = ref("")
const error = ref<string | null>(null)

const LS_KEY = "lexscript_last_session"

export function useChatSession() {
  const filteredSessions = computed(() => {
    if (!searchQuery.value) return sessions.value
    const q = searchQuery.value.toLowerCase()
    return sessions.value.filter((s) => s.title.toLowerCase().includes(q))
  })

  async function loadSessions() {
    loading.value = true
    error.value = null
    try {
      const r = await fetch(`${API}/chat/sessions`, { headers: authHeaders() })
      const d = await r.json()
      sessions.value = (d.data || []).map((s: Session) => ({
        ...s,
        title: s.title || "新对话",
      }))
    } catch (e) {
      error.value = "加载会话失败"
    }
    loading.value = false
  }

  async function createSession(
    title = "新对话",
    role = "litigator",
    model = ""
  ): Promise<string | null> {
    try {
      const r = await fetch(`${API}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ title, role, model }),
      })
      const d = await r.json()
      if (d.ok && d.data?.uuid) {
        const uuid = d.data.uuid
        sessions.value.unshift({ uuid, title, role, model, created_at: "" })
        persistLastSession(uuid)
        currentSessionId.value = uuid
        return uuid
      }
    } catch {
      /* ignore */
    }
    return null
  }

  async function selectSession(uuid: string) {
    currentSessionId.value = uuid
    persistLastSession(uuid)
    try {
      const r = await fetch(`${API}/chat/sessions/${uuid}`, { headers: authHeaders() })
      const d = await r.json()
      if (d.ok && d.data) {
        return d.data.messages || []
      }
    } catch {
      /* ignore */
    }
    return null
  }

  async function renameSession(uuid: string, title: string) {
    if (!title.trim()) return false
    try {
      const r = await fetch(`${API}/chat/sessions/${uuid}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ title }),
      })
      const d = await r.json()
      if (d.ok) {
        const idx = sessions.value.findIndex((s) => s.uuid === uuid)
        if (idx >= 0) sessions.value[idx] = { ...sessions.value[idx], title }
        return true
      }
    } catch {
      /* ignore */
    }
    return false
  }

  async function deleteSession(uuid: string) {
    try {
      await fetch(`${API}/chat/sessions/${uuid}`, { method: "DELETE", headers: authHeaders() })
      sessions.value = sessions.value.filter((s) => s.uuid !== uuid)
      if (currentSessionId.value === uuid) {
        currentSessionId.value = null
        localStorage.removeItem(LS_KEY)
      }
    } catch {
      /* ignore */
    }
  }

  function persistLastSession(uuid: string) {
    localStorage.setItem(LS_KEY, uuid)
  }

  function getLastSessionId(): string | null {
    return localStorage.getItem(LS_KEY)
  }

  function clearLastSession() {
    localStorage.removeItem(LS_KEY)
  }

  function setSearchQuery(q: string) {
    searchQuery.value = q
  }

  return {
    sessions,
    currentSessionId,
    loading,
    searchQuery,
    error,
    filteredSessions,
    loadSessions,
    createSession,
    selectSession,
    renameSession,
    deleteSession,
    persistLastSession,
    getLastSessionId,
    clearLastSession,
    setSearchQuery,
  }
}
