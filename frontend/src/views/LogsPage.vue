<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"
const auth = useAuthStore()

interface Log {
  id: number
  action: string
  target: string
  detail: string
  created_at: number
}

const logs = ref<Log[]>([])
const loading = ref(true)

async function loadLogs() {
  loading.value = true
  try { const r = await fetch(`${API}/logs`, { headers: auth.setTokenHeader() }); const d = await r.json(); logs.value = d.data || [] } catch { }
  loading.value = false
}
function formatTime(ts: number) {
  const d = new Date(ts * 1000)
  return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

onMounted(loadLogs)
</script>

<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-lg font-bold">操作日志</h1>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5">系统操作记录</p>
      </div>
      <button @click="loadLogs" class="btn btn-sm btn-secondary">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
        刷新
      </button>
    </div>

    <!-- Logs List -->
    <div class="card overflow-hidden">
      <div v-if="loading" class="empty-state">
        <div class="skeleton w-12 h-4 rounded mb-2" />
        <div class="empty-state-title text-xs">加载中...</div>
      </div>
      <div v-else-if="logs.length === 0" class="empty-state">
        <div class="empty-state-icon"><span>📄</span></div>
        <div class="empty-state-title">暂无操作记录</div>
      </div>
      <div v-else class="divide-y divide-[var(--border-light)]">
        <div
          v-for="log in logs"
          :key="log.id"
          class="px-4 py-3 hover:bg-[var(--surface-hover)] transition-all duration-150"
        >
          <div class="flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full bg-[var(--brand-400)] shrink-0" />
            <span class="text-sm font-medium">{{ log.action }}</span>
            <span v-if="log.target" class="text-xs text-[var(--text-tertiary)]">· {{ log.target }}</span>
            <span class="ml-auto text-[11px] text-[var(--text-tertiary)] font-mono">{{ formatTime(log.created_at) }}</span>
          </div>
          <div v-if="log.detail" class="text-xs text-[var(--text-secondary)] mt-0.5 ml-3.5">{{ log.detail }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
