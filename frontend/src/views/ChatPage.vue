<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from "vue"
import { useRouter } from "vue-router"
import { useToast } from "@/composables/useToast"
import { useAuthStore } from "@/stores/auth"
import { useChatSession } from "@/composables/useChatSession"
import { useChatMessages } from "@/composables/useChatMessages"
import ChatSessionList from "@/components/chat/ChatSessionList.vue"
import ChatMessageItem from "@/components/chat/ChatMessageItem.vue"
import ChatInputArea from "@/components/chat/ChatInputArea.vue"
import ChatSuggestionChips from "@/components/chat/ChatSuggestionChips.vue"

const API = "/api/v1"
const router = useRouter()
const auth = useAuthStore()
const { show: showToast } = useToast()
const {
  sessions,
  currentSessionId,
  loading: sessionsLoading,
  error: sessionsError,
  searchQuery,
  filteredSessions,
  loadSessions,
  createSession,
  renameSession,
  deleteSession,
  persistLastSession,
  getLastSessionId,
  clearLastSession,
  setSearchQuery,
} = useChatSession()
const {
  messages,
  streaming,
  agentSteps,
  clearMessages,
  addMessage,
  sendMessage,
} = useChatMessages()

// ── Config ──
const roles = ref<Record<string, string>>({})
const currentRole = ref("litigator")
const models = ref<string[]>([])
const currentModel = ref("")
const providerName = ref("")

const roleLabels: Record<string, string> = {
  legal_expert: "法律专家",
  litigator: "诉讼律师",
  corp_counsel: "企业法务",
  contract_specialist: "合同专员",
}

// ── UI state ──
const sidebarOpen = ref(false)
const kbOpen = ref(false)
const skillsOpen = ref(false)
const messagesEnd = ref<HTMLElement | null>(null)

// ── Skills ──
const skillsData = ref<Record<string, { name: string; description: string }[]>>({})
const activeSkill = ref<string | null>(null)
const loadingSkills = ref(false)

// ── File attachment ──
const attachedFiles = ref<{ name: string; size: number; file: File }[]>([])

// ── Knowledge Base ──
const kbFiles = ref<any[]>([])
const kbStatus = ref<any>(null)
const loadingKb = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// ══════════════════════════════════════
// INIT
// ══════════════════════════════════════

async function loadRoles() {
  try {
    const r = await fetch(`${API}/chat/roles`, { headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) roles.value = d.data
  } catch { /* ignore */ }
}

async function loadModels() {
  try {
    const [cR, pR] = await Promise.all([
      fetch(`${API}/config`, { headers: auth.setTokenHeader() }),
      fetch(`${API}/config/providers`, { headers: auth.setTokenHeader() }),
    ])
    const c = await cR.json()
    const p = await pR.json()
    if (c.ok && c.data) {
      const provider = c.data.llm_provider || "minimax"
      currentModel.value = c.data.llm_model || ""
      providerName.value = provider
      if (p.ok && p.data && p.data[provider]) {
        models.value = p.data[provider].models || []
      }
    }
  } catch { /* ignore */ }
}

async function changeModel() {
  if (!currentModel.value) return
  try {
    await fetch(`${API}/config`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...auth.setTokenHeader() },
      body: JSON.stringify({ model: currentModel.value }),
    })
  } catch { /* ignore */ }
}

async function loadMessagesForSession(uuid: string) {
  clearMessages()
  try {
    const r = await fetch(`${API}/chat/sessions/${uuid}`, { headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok && d.data) {
      const msgs = d.data.messages || []
      for (const m of msgs) {
        if (m.role === "user" || m.role === "assistant") {
          addMessage(m.role, m.content)
        }
      }
    }
  } catch { /* ignore */ }
}

async function initChat() {
  await Promise.all([loadRoles(), loadModels()])
  await loadSessions()

  // Restore last session
  const lastId = getLastSessionId()
  if (lastId && sessions.value.some((s) => s.uuid === lastId)) {
    currentSessionId.value = lastId
    await loadMessagesForSession(lastId)
    checkActiveSkill()
    return
  }

  // Pick first session
  if (sessions.value.length > 0) {
    const first = sessions.value[0].uuid
    currentSessionId.value = first
    persistLastSession(first)
    await loadMessagesForSession(first)
    checkActiveSkill()
    return
  }

  // Auto-create default session
  const uuid = await createSession("新对话", currentRole.value, currentModel.value)
  if (uuid) checkActiveSkill()
}

// ══════════════════════════════════════
// SESSION HANDLERS
// ══════════════════════════════════════

async function handleNewSession() {
  activeSkill.value = null
  const uuid = await createSession("新对话", currentRole.value, currentModel.value)
  if (uuid) {
    clearMessages()
    await loadSessions()
    sidebarOpen.value = false
    checkActiveSkill()
  }
}

async function handleSelectSession(uuid: string) {
  sidebarOpen.value = false
  currentSessionId.value = uuid
  persistLastSession(uuid)
  await loadMessagesForSession(uuid)
  checkActiveSkill()
}

async function handleRenameSession(uuid: string, title: string) {
  await renameSession(uuid, title)
}

async function handleDeleteSession(uuid: string) {
  await deleteSession(uuid)
  if (messages.value.length > 0 && currentSessionId.value === uuid) {
    clearMessages()
    clearLastSession()
    if (sessions.value.length > 0) {
      handleSelectSession(sessions.value[0].uuid)
    }
  }
}

// ══════════════════════════════════════
// CHAT HANDLERS
// ══════════════════════════════════════

async function uploadAttachedFiles(): Promise<boolean> {
  if (!attachedFiles.value.length) return true
  let allOk = true
  for (const af of attachedFiles.value) {
    const fd = new FormData()
    fd.append("file", af.file)
    try {
      await fetch(`${API}/knowledge/upload`, { method: "POST", headers: auth.setTokenHeader(), body: fd })
    } catch {
      allOk = false
    }
  }
  attachedFiles.value = []
  refreshKb()
  return allOk
}

async function handleSend(text: string) {
  if (!text.trim() || streaming.value) return

  let sessionId = currentSessionId.value
  if (!sessionId) {
    sessionId = await createSession("新对话", currentRole.value, currentModel.value)
    if (!sessionId) return
    await loadSessions()
    sidebarOpen.value = false
  }

  await uploadAttachedFiles()
  addMessage("user", text)

  const scroll = () => nextTick(() => messagesEnd.value?.scrollIntoView({ behavior: "smooth" }))

  const result = await sendMessage(
    sessionId,
    text,
    currentRole.value,
    currentModel.value || undefined,
    scroll,
    scroll,
  )

  if (result && result !== sessionId) {
    currentSessionId.value = result
    persistLastSession(result)
    await loadSessions()
  }

  scroll()
}

async function handleRegenerate() {
  if (streaming.value || !currentSessionId.value) return

  const msgs = [...messages.value]
  let lastUserIdx = -1
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === "user") {
      lastUserIdx = i
      break
    }
  }
  if (lastUserIdx === -1) return

  const userText = msgs[lastUserIdx].content

  clearMessages()
  for (let i = 0; i < lastUserIdx; i++) {
    addMessage(msgs[i].role as "user" | "assistant", msgs[i].content)
  }

  addMessage("user", userText)
  const scroll = () => nextTick(() => messagesEnd.value?.scrollIntoView({ behavior: "smooth" }))
  await sendMessage(
    currentSessionId.value,
    userText,
    currentRole.value,
    currentModel.value || undefined,
    scroll,
    scroll,
  )
  scroll()
}

function handleSuggestion(text: string) {
  handleSend(text)
}

function handleAttachFiles(files: File[]) {
  for (const f of files) {
    attachedFiles.value.push({ name: f.name, size: f.size, file: f })
  }
}

function handleRemoveFile(idx: number) {
  attachedFiles.value.splice(idx, 1)
}

function onCopy(_text: string) { /* handled by child */ }
function onLike(_id: string) { /* future: sync to backend */ }
function onDislike(_id: string) { /* future: sync to backend */ }

// ══════════════════════════════════════
// LEGAL SKILLS
// ══════════════════════════════════════

async function loadSkills() {
  loadingSkills.value = true
  try {
    const r = await fetch(`${API}/legal-skills`, { headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) skillsData.value = d.data
  } catch { /* ignore */ }
  loadingSkills.value = false
}

async function checkActiveSkill() {
  if (!currentSessionId.value) {
    activeSkill.value = null
    return
  }
  try {
    const r = await fetch(`${API}/legal-skills/sessions/${currentSessionId.value}/active`, { headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) activeSkill.value = d.data?.skill_name || null
  } catch {
    activeSkill.value = null
  }
}

async function applySkill(name: string) {
  if (!currentSessionId.value) return
  try {
    await fetch(`${API}/legal-skills/sessions/${currentSessionId.value}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...auth.setTokenHeader() },
      body: JSON.stringify({ skill_name: name }),
    })
    activeSkill.value = name
  } catch { /* ignore */ }
}

async function removeSkill() {
  if (!currentSessionId.value) return
  try {
    await fetch(`${API}/legal-skills/sessions/${currentSessionId.value}/skill`, { method: "DELETE", headers: auth.setTokenHeader() })
    activeSkill.value = null
  } catch { /* ignore */ }
}

function toggleSkills() {
  skillsOpen.value = !skillsOpen.value
  if (skillsOpen.value && Object.keys(skillsData.value).length === 0) loadSkills()
}

// ══════════════════════════════════════
// KNOWLEDGE BASE
// ══════════════════════════════════════

async function loadKbStatus() {
  try {
    const r = await fetch(`${API}/knowledge/status`, { headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) kbStatus.value = d.data
  } catch { /* ignore */ }
}

async function loadKbFiles() {
  loadingKb.value = true
  try {
    const r = await fetch(`${API}/knowledge/files`, { headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) kbFiles.value = d.data
  } catch { /* ignore */ }
  loadingKb.value = false
}

function refreshKb() {
  loadKbStatus()
  loadKbFiles()
}

async function handleUpload(e: Event) {
  const el = e.target as HTMLInputElement
  const file = el.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append("file", file)
    await fetch(`${API}/knowledge/upload`, { method: "POST", headers: auth.setTokenHeader(), body: fd })
    refreshKb()
  } catch { /* ignore */ }
  uploading.value = false
  if (fileInput.value) fileInput.value.value = ""
}

async function regFile(fileId: number) {
  try {
    await fetch(`${API}/knowledge/reg/${fileId}`, { method: "POST", headers: auth.setTokenHeader() })
    refreshKb()
  } catch { /* ignore */ }
}

async function reindexFile(fileId: number) {
  try {
    await fetch(`${API}/knowledge/reindex/${fileId}`, { method: "POST", headers: auth.setTokenHeader() })
    refreshKb()
  } catch { /* ignore */ }
}

async function retryFailedKb() {
  try {
    await fetch(`${API}/knowledge/retry-failed`, { method: "POST", headers: auth.setTokenHeader() })
    refreshKb()
  } catch { /* ignore */ }
}

async function regAllKb() {
  try {
    await fetch(`${API}/knowledge/reg-all`, { method: "POST", headers: auth.setTokenHeader() })
    refreshKb()
  } catch { /* ignore */ }
}

async function importAllKb() {
  try {
    await fetch(`${API}/knowledge/import`, { method: "POST", headers: auth.setTokenHeader() })
    refreshKb()
  } catch { /* ignore */ }
}

const statusBadge = (s: string) => {
  if (s === "indexed") return "tag-green"
  if (s === "pending") return "tag-amber"
  if (s === "indexing") return "tag-blue"
  if (s === "failed") return "tag-red"
  return ""
}

const statusLabel = (s: string) =>
  s === "indexed" ? "已索引" : s === "pending" ? "待索引" : s === "indexing" ? "索引中" : s === "failed" ? "失败" : s

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ══════════════════════════════════════
// LIFECYCLE
// ══════════════════════════════════════

const kbHandler = (e: KeyboardEvent) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "n") {
    e.preventDefault()
    handleNewSession()
  }
}

onMounted(() => {
  initChat()
  refreshKb()
  loadSkills()
  window.addEventListener("keydown", kbHandler)
})

onUnmounted(() => {
  window.removeEventListener("keydown", kbHandler)
})

const categoryIcons: Record<string, string> = {
  "诉讼策略": "⚖",
  "合同审查": "📋",
  "证据实务": "🔍",
  "法律文书": "📝",
  "公司商事": "🏢",
  "劳动人事": "👥",
  "执行实务": "🔨",
  "法律检索": "📚",
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Chat Header -->
    <div
      class="flex items-center gap-2 px-4 py-2.5 bg-[var(--surface-primary)] md:bg-transparent md:glass-panel border-b border-[var(--border-light)] shrink-0"
      style="backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);"
    >
      <button
        @click="sidebarOpen = !sidebarOpen"
        class="md:hidden p-1.5 rounded-lg text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
      </button>
      <h2 class="text-sm font-semibold shrink-0">AI 对话</h2>
      <div class="flex items-center gap-2 ml-2">
        <select v-model="currentRole" class="select text-[11px] py-1.5 max-w-[110px]">
          <option v-for="(prompt, key) in roles" :key="key" :value="key">{{ roleLabels[key] || key }}</option>
        </select>
        <select
          v-if="models.length"
          v-model="currentModel"
          @change="changeModel"
          class="select text-[11px] py-1.5 max-w-[150px] hidden sm:inline-block"
        >
          <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <span
        v-if="activeSkill && currentSessionId"
        class="tag tag-amber text-[10px] hidden sm:inline-flex items-center gap-1 max-w-[120px] truncate cursor-pointer"
        @click="toggleSkills"
        :title="`已启用: ${activeSkill}`"
      >
        <span>✦</span><span class="truncate">{{ activeSkill }}</span>
      </span>
      <div class="flex-1" />
      <button
        @click="toggleSkills"
        class="btn btn-ghost btn-sm gap-1.5"
        :class="skillsOpen ? 'text-amber-500 bg-[var(--surface-hover)]' : activeSkill ? 'text-amber-500' : ''"
        title="法律技能"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" /></svg>
        <span class="hidden sm:inline text-[11px]">技能</span>
      </button>
      <button
        @click="kbOpen = !kbOpen"
        class="btn btn-ghost btn-sm gap-1.5"
        :class="kbOpen ? 'text-[var(--brand-600)] dark:text-[var(--brand-400)] bg-[var(--surface-hover)]' : ''"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>
        <span class="hidden sm:inline text-[11px]">知识库</span>
      </button>
      <span class="text-[10px] text-[var(--text-tertiary)] font-mono ml-1">{{ providerName }}</span>
    </div>

    <div class="flex flex-1 overflow-hidden">
      <!-- Session List Sidebar -->
      <ChatSessionList
        :sessions="filteredSessions"
        :currentSessionId="currentSessionId"
        :loading="sessionsLoading"
        :error="sessionsError"
        :searchQuery="searchQuery"
        @select="handleSelectSession"
        @create="handleNewSession"
        @delete="handleDeleteSession"
        @rename="handleRenameSession"
        @update:searchQuery="setSearchQuery"
        @close="sidebarOpen = false"
      />

      <!-- Messages Area -->
      <div class="flex-1 flex flex-col min-w-0">
        <!-- Streaming Progress -->
        <div v-if="streaming" class="h-[2px] bg-[var(--surface-tertiary)] overflow-hidden shrink-0">
          <div class="h-full w-full bg-gradient-to-r from-[var(--brand-400)] via-[var(--brand-600)] to-[var(--brand-400)] bg-[length:200%_100%] animate-shimmer-slide" />
        </div>

        <div class="flex-1 overflow-y-auto px-4 md:px-6 py-6">
          <!-- Empty State -->
          <div v-if="messages.length === 0" class="empty-state h-full relative overflow-hidden">
            <div class="absolute -top-20 -right-20 w-64 h-64 bg-gradient-to-br from-[var(--brand-200)]/30 to-transparent dark:from-[var(--brand-600)]/10 rounded-full blur-3xl pointer-events-none" />
            <div class="absolute -bottom-20 -left-20 w-48 h-48 bg-gradient-to-tr from-[var(--brand-300)]/20 to-transparent dark:from-[var(--brand-500)]/8 rounded-full blur-3xl pointer-events-none" />
            <div class="relative">
              <div class="empty-state-icon">
                <span class="text-xl">&#9878;</span>
              </div>
              <div class="empty-state-title">LexScript AI 法律助手</div>
              <div class="empty-state-desc mb-5">分析案情、起草文书、检索法条、管理知识库文件</div>
              <div class="flex gap-2 justify-center">
                <button @click="handleNewSession" class="btn btn-primary btn-lg">开始新对话</button>
                <button @click="kbFiles.length > 0 ? router.push('/files') : fileInput?.click()" class="btn btn-secondary btn-lg">上传文件</button>
              </div>
              <div class="grid grid-cols-3 gap-2 mt-8 max-w-sm mx-auto">
                <div class="p-3 rounded-xl bg-white/70 dark:bg-[var(--dark-surface-elevated)]/60 backdrop-blur-md border border-white/30 dark:border-white/5 shadow-sm text-center transition-all duration-200 hover:scale-105 hover:shadow-md">
                  <div class="text-lg mb-1">⚖️</div>
                  <div class="text-[10px] text-[var(--text-tertiary)]">案情分析</div>
                </div>
                <div class="p-3 rounded-xl bg-white/70 dark:bg-[var(--dark-surface-elevated)]/60 backdrop-blur-md border border-white/30 dark:border-white/5 shadow-sm text-center transition-all duration-200 hover:scale-105 hover:shadow-md">
                  <div class="text-lg mb-1">📝</div>
                  <div class="text-[10px] text-[var(--text-tertiary)]">文书起草</div>
                </div>
                <div class="p-3 rounded-xl bg-white/70 dark:bg-[var(--dark-surface-elevated)]/60 backdrop-blur-md border border-white/30 dark:border-white/5 shadow-sm text-center transition-all duration-200 hover:scale-105 hover:shadow-md">
                  <div class="text-lg mb-1">🔍</div>
                  <div class="text-[10px] text-[var(--text-tertiary)]">法条检索</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Messages -->
          <div v-for="(msg, idx) in messages" :key="msg.id">
            <ChatMessageItem
              :message="msg"
              :isStreaming="streaming && idx === messages.length - 1 && msg.role === 'assistant'"
              :isLast="idx === messages.length - 1"
              @copy="onCopy"
              @like="onLike"
              @dislike="onDislike"
              @regenerate="handleRegenerate"
            />
          </div>
          <div ref="messagesEnd" />
        </div>

        <!-- Agent Steps (while streaming without content) -->
        <div
          v-if="streaming && agentSteps.length > 0 && messages.length > 0 && !messages[messages.length - 1].content"
          class="px-4 md:px-6 pb-2 bg-[var(--surface-primary)] shrink-0"
        >
          <div class="max-w-3xl mx-auto flex items-center gap-3 bg-[var(--surface-secondary)] rounded-lg px-3 py-2">
            <div v-for="(step, si) in agentSteps" :key="si" class="flex items-center gap-1.5 text-xs">
              <span v-if="step.status === 'active'" class="w-3.5 h-3.5 rounded-full border-2 border-[var(--brand-500)] border-t-transparent animate-spin" />
              <span v-else-if="step.status === 'done'" class="text-green-500">✓</span>
              <span v-else class="text-[var(--text-quaternary)]">○</span>
              <span
                :class="step.status === 'active' ? 'text-[var(--brand-600)] dark:text-[var(--brand-400)] font-medium' : step.status === 'done' ? 'text-green-600 dark:text-green-400' : 'text-[var(--text-tertiary)]'"
              >{{ step.label }}</span>
              <span v-if="si < agentSteps.length - 1" class="text-[var(--text-quaternary)] mx-0.5">→</span>
            </div>
          </div>
        </div>

        <!-- Suggestion Chips -->
        <ChatSuggestionChips v-if="messages.length === 0" @select="handleSuggestion" />

        <!-- Input Area -->
        <ChatInputArea
          :disabled="streaming"
          :streaming="streaming"
          :attachedFiles="attachedFiles"
          :currentRole="currentRole"
          :currentModel="currentModel"
          :activeSkill="activeSkill"
          :roleLabels="roleLabels"
          @send="handleSend"
          @attachFiles="handleAttachFiles"
          @removeFile="handleRemoveFile"
        />
      </div>

      <!-- Skills Panel -->
      <aside
        v-show="skillsOpen"
        class="fixed md:static inset-0 z-40 md:z-auto md:w-80 bg-[var(--surface-primary)] md:bg-transparent md:glass-panel md:border-l border-[var(--border-light)] flex flex-col shrink-0 overflow-hidden animate-slideInRight md:animate-none"
      >
        <div class="md:hidden fixed inset-0 bg-black/30 -z-10" @click="skillsOpen = false" />
        <div class="p-3.5 border-b border-[var(--border-light)]">
          <div class="flex items-center justify-between mb-2.5">
            <h3 class="text-sm font-semibold flex items-center gap-2">
              <svg class="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" /></svg>
              法律技能
            </h3>
            <div class="flex items-center gap-1">
              <button v-if="activeSkill" @click="removeSkill()" class="btn btn-ghost btn-sm p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20" title="移除技能">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
              <button @click="loadSkills" class="btn btn-ghost btn-sm p-1.5" title="刷新">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
              </button>
              <button @click="skillsOpen = false" class="md:hidden btn btn-ghost btn-sm p-1.5">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          </div>
          <div class="text-[10px] text-[var(--text-tertiary)]">启用专业技能后，AI 将遵循该领域的专业规范作答</div>
          <div v-if="activeSkill" class="mt-2 flex items-center gap-1.5 text-[11px] text-amber-600 dark:text-amber-400 bg-[var(--surface-tertiary)] rounded-md px-2.5 py-1.5">
            <span>✦ 已启用: <strong>{{ activeSkill }}</strong></span>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto">
          <div v-if="loadingSkills" class="flex flex-col items-center justify-center py-10 text-[var(--text-tertiary)]">
            <div class="skeleton w-10 h-10 rounded-lg mb-2" />
            <span class="text-xs">加载中...</span>
          </div>
          <div v-else-if="Object.keys(skillsData).length === 0" class="empty-state py-10">
            <svg class="w-10 h-10 mb-2 text-[var(--text-quaternary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" /></svg>
            <span class="empty-state-title">暂无技能数据</span>
            <span class="empty-state-subtitle text-[10px] text-[var(--text-tertiary)]">在聊天中描述你想要的技能，AI 可以帮你创建</span>
          </div>
          <div class="px-3.5 py-1.5 text-[9px] text-[var(--text-tertiary)] border-b border-[var(--border-light)]">在聊天中描述你想要的技能，AI 可以帮你创建</div>
          <div v-for="(skills, category) in skillsData" :key="category">
            <div class="flex items-center gap-1.5 px-3.5 py-2 text-[10px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wider bg-[var(--surface-secondary)] border-b border-[var(--border-light)] sticky top-0">
              <span>{{ categoryIcons[category] || '📌' }}</span>
              <span>{{ category }}</span>
              <span class="ml-auto text-[9px] opacity-60">{{ skills.length }}</span>
            </div>
            <div v-for="skill in skills" :key="skill.name" class="group flex items-start gap-2.5 px-3.5 py-3 border-b border-[var(--border-light)] hover:bg-[var(--surface-hover)] transition-colors duration-150">
              <div class="flex-1 min-w-0">
                <div class="text-xs font-medium truncate flex items-center gap-1.5">
                  {{ skill.name.replace(category + '_', '') }}
                  <span v-if="!skill.builtin" class="text-[8px] px-1 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">用户创建</span>
                </div>
                <div class="text-[10px] text-[var(--text-tertiary)] mt-0.5 leading-relaxed line-clamp-2">{{ skill.description }}</div>
              </div>
              <button
                v-if="currentSessionId"
                class="shrink-0 btn btn-xs"
                :class="activeSkill === skill.name ? 'btn-ghost text-red-500 hover:text-red-600' : 'btn-primary'"
                @click="activeSkill === skill.name ? removeSkill() : applySkill(skill.name)"
              >
                {{ activeSkill === skill.name ? '移除' : '启用' }}
              </button>
            </div>
          </div>
        </div>
      </aside>

      <!-- Knowledge Base Panel -->
      <aside
        v-show="kbOpen"
        class="fixed md:static inset-0 z-40 md:z-auto md:w-80 bg-[var(--surface-primary)] md:bg-transparent md:glass-panel md:border-l border-[var(--border-light)] flex flex-col shrink-0 overflow-hidden animate-slideInRight md:animate-none"
      >
        <div class="md:hidden fixed inset-0 bg-black/30 -z-10" @click="kbOpen = false" />
        <div class="p-3.5 border-b border-[var(--border-light)]">
          <div class="flex items-center justify-between mb-2.5">
            <h3 class="text-sm font-semibold flex items-center gap-2">
              <svg class="w-4 h-4 text-[var(--brand-500)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>
              知识库
            </h3>
            <div class="flex items-center gap-1">
              <button @click="refreshKb" class="btn btn-ghost btn-sm p-1.5" title="刷新">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
              </button>
              <button @click="kbOpen = false" class="md:hidden btn btn-ghost btn-sm p-1.5">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          </div>
          <div class="flex flex-wrap gap-x-2.5 gap-y-1 text-[11px] mb-2">
            <span class="flex items-center gap-1.5"><span class="status-dot status-dot-green" />{{ kbStatus?.indexed || 0 }} 已索引</span>
            <span class="flex items-center gap-1.5"><span class="status-dot status-dot-amber" />{{ kbStatus?.pending || 0 }} 待索引</span>
            <span v-if="kbStatus?.failed" class="flex items-center gap-1.5"><span class="status-dot status-dot-red" />{{ kbStatus.failed }} 失败</span>
          </div>
          <div class="text-[10px] text-[var(--text-tertiary)] font-mono truncate bg-[var(--surface-secondary)] rounded-md px-2 py-1" :title="kbStatus?.path">{{ kbStatus?.path || '加载中...' }}</div>
          <div class="flex gap-1.5 mt-2.5">
            <button @click="fileInput?.click()" :disabled="uploading" class="btn btn-primary btn-sm flex-1">
              {{ uploading ? '上传中...' : '上传文件' }}
            </button>
            <button @click="importAllKb" class="btn btn-secondary btn-sm">扫描</button>
            <button @click="regAllKb" class="btn btn-secondary btn-sm text-[var(--brand-600)] dark:text-[var(--brand-400)]">全部索引</button>
          </div>
          <div v-if="kbStatus?.failed" class="flex gap-1.5 mt-2">
            <button @click="retryFailedKb" class="btn btn-sm btn-danger flex-1 text-[11px]">重试失败 ({{ kbStatus.failed }})</button>
          </div>
          <input ref="fileInput" type="file" class="hidden" @change="handleUpload" />
        </div>
        <div class="flex-1 overflow-y-auto">
          <div v-if="loadingKb" class="flex flex-col items-center justify-center py-10 text-[var(--text-tertiary)]">
            <div class="skeleton w-10 h-10 rounded-lg mb-2" />
            <span class="text-xs">加载中...</span>
          </div>
          <div v-else-if="kbFiles.length === 0" class="empty-state py-10">
            <svg class="w-10 h-10 mb-2 text-[var(--text-quaternary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
            <span class="empty-state-title">暂无文件</span>
            <span class="empty-state-desc">上传文件到知识库</span>
          </div>
          <div v-for="f in kbFiles" :key="f.id" class="group flex items-start gap-2.5 px-3.5 py-3 border-b border-[var(--border-light)] hover:bg-[var(--surface-hover)] transition-colors duration-150">
            <div class="w-7 h-7 rounded-lg bg-[var(--surface-tertiary)] flex items-center justify-center shrink-0 mt-0.5">
              <svg class="w-3.5 h-3.5 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-medium truncate" :class="f.status === 'failed' ? 'text-[#dc2626]' : ''">{{ f.name }}</div>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-[10px] text-[var(--text-tertiary)] font-mono">{{ formatSize(f.size) }}</span>
                <span class="tag" :class="statusBadge(f.status)">{{ statusLabel(f.status) }}</span>
                <span v-if="f.chunk_count" class="text-[10px] text-[var(--text-tertiary)]">{{ f.chunk_count }} 分片</span>
              </div>
              <div v-if="f.status === 'failed' && f.error" class="text-[9px] text-red-400 mt-1 truncate max-w-[200px]" :title="f.error">{{ f.error }}</div>
            </div>
            <div class="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
              <button v-if="f.status === 'failed'" @click="reindexFile(f.id)" class="btn btn-ghost btn-sm p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20" title="重新索引">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
              </button>
              <button v-if="f.status !== 'indexed'" @click="regFile(f.id)" class="btn btn-ghost btn-sm p-1 text-[var(--text-tertiary)] hover:text-amber-500" title="索引此文件">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" /></svg>
              </button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>
