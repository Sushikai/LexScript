<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"
const auth = useAuthStore()

interface Task {
  uuid: string
  type: string
  status: string
  progress: number
  message: string
  created_at: number
  updated_at: number
}

const tasks = ref<Task[]>([])
const loading = ref(true)

async function loadTasks() {
  loading.value = true
  try { const r = await fetch(`${API}/tasks`, { headers: auth.setTokenHeader() }); const d = await r.json(); tasks.value = d.data || [] } catch { }
  loading.value = false
}

async function cancelTask(uuid: string) {
  try { await fetch(`${API}/tasks/${uuid}`, { method: "DELETE", headers: auth.setTokenHeader() }); await loadTasks() } catch { }
}

function formatTime(ts: number) {
  const d = new Date(ts * 1000)
  return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

function statusBadge(s: string) {
  return s === "completed" ? "tag-green" :
    s === "running" || s === "processing" ? "tag-blue" :
    s === "failed" ? "tag-red" : "tag-zinc"
}

function progressColor(s: string) {
  return s === "failed" ? "progress-bar-fill-red" :
    s === "completed" ? "progress-bar-fill-green" : "progress-bar-fill-blue"
}

onMounted(loadTasks)
</script>

<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-lg font-bold">异步任务</h1>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5">文件解析 / 文书生成等后台任务进度</p>
      </div>
      <button @click="loadTasks" class="btn btn-sm btn-secondary">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
        刷新
      </button>
    </div>

    <!-- Task List -->
    <div class="space-y-2.5">
      <div v-if="loading" class="empty-state">
        <div class="skeleton w-8 h-4 rounded mb-2" />
        <div class="empty-state-title text-xs">加载中...</div>
      </div>
      <div v-else-if="tasks.length === 0" class="empty-state">
        <div class="empty-state-icon"><span>📋</span></div>
        <div class="empty-state-title">暂无后台任务</div>
        <div class="empty-state-desc">执行文件解析或文书生成后将在此显示</div>
      </div>
      <div
        v-for="t in tasks"
        :key="t.uuid"
        class="card p-4 transition-all duration-200 hover:shadow-md"
      >
        <div class="flex items-center justify-between mb-2.5">
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold">{{ t.type || "任务" }}</span>
            <span class="tag text-[10px]" :class="statusBadge(t.status)">{{ t.status }}</span>
          </div>
          <button
            v-if="t.status === 'running' || t.status === 'processing'"
            @click="cancelTask(t.uuid)"
            class="btn btn-sm btn-ghost text-[var(--text-tertiary)] hover:text-red-500 text-xs"
          >
            取消
          </button>
        </div>
        <div v-if="t.message" class="text-xs text-[var(--text-secondary)] mb-2.5">{{ t.message }}</div>
        <div class="flex items-center gap-2.5">
          <div class="progress-bar flex-1">
            <div
              class="progress-bar-fill"
              :class="progressColor(t.status)"
              :style="{ width: Math.min(t.progress || 0, 100) + '%' }"
            />
          </div>
          <span class="text-xs text-[var(--text-tertiary)] shrink-0 w-8 text-right tabular-nums">{{ t.progress || 0 }}%</span>
        </div>
        <div class="text-[10px] text-[var(--text-tertiary)] mt-2 font-mono">{{ formatTime(t.created_at) }}</div>
      </div>
    </div>
  </div>
</template>
