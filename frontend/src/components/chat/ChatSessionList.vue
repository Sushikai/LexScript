<script setup lang="ts">
import { ref, nextTick } from "vue"
import type { Session } from "@/types"

const props = defineProps<{
  sessions: Session[]
  currentSessionId: string | null
  loading: boolean
  error: string | null
  searchQuery: string
}>()

const emit = defineEmits<{
  select: [uuid: string]
  create: []
  delete: [uuid: string]
  rename: [uuid: string, title: string]
  "update:searchQuery": [value: string]
  close: []
}>()

const editingId = ref<string | null>(null)
const editTitle = ref("")
const editInput = ref<HTMLInputElement | null>(null)

function startRename(session: Session) {
  editingId.value = session.uuid
  editTitle.value = session.title
  nextTick(() => editInput.value?.focus())
}

function commitRename() {
  if (!editingId.value) return
  const title = editTitle.value.trim()
  if (title) {
    emit("rename", editingId.value, title)
  }
  editingId.value = null
  editTitle.value = ""
}

function cancelRename() {
  editingId.value = null
  editTitle.value = ""
}

function handleKeydownRename(e: KeyboardEvent) {
  if (e.key === "Enter") commitRename()
  else if (e.key === "Escape") cancelRename()
}

function relativeTime(dateStr: string): string {
  if (!dateStr) return ""
  const t = new Date(dateStr).getTime()
  if (!t) return ""
  const diff = Date.now() - t
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "刚刚"
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return new Date(dateStr).toLocaleDateString("zh-CN")
}
</script>

<template>
  <aside
    class="hidden md:flex flex-col w-64 bg-[var(--surface-secondary)] border-r border-[var(--border-light)] h-full shrink-0"
  >
    <!-- Header -->
    <div class="p-3 border-b border-[var(--border-light)] space-y-2">
      <button
        @click="emit('create')"
        class="btn btn-primary btn-md w-full justify-center gap-2"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
        新对话
        <kbd class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/20 text-white/80">⌘N</kbd>
      </button>
      <div class="relative">
        <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
        <input
          :value="searchQuery"
          @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
          type="text"
          placeholder="搜索会话..."
          class="w-full bg-[var(--surface-primary)] border border-[var(--border-light)] rounded-lg pl-8 pr-3 py-1.5 text-xs outline-none focus:border-[var(--brand-400)] focus:shadow-[0_0_0_2px_rgba(59,130,246,0.1)] transition-all placeholder:text-[var(--text-tertiary)]"
        />
      </div>
    </div>

    <!-- Sessions -->
    <div class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
      <!-- Loading -->
      <div v-if="loading" class="space-y-2 px-2 py-4">
        <div v-for="i in 3" :key="i" class="flex items-center gap-3">
          <div class="skeleton w-8 h-8 rounded-lg" />
          <div class="flex-1 space-y-1.5">
            <div class="skeleton w-3/4 h-3 rounded" />
            <div class="skeleton w-1/2 h-2 rounded" />
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center py-8 text-center">
        <svg class="w-8 h-8 text-red-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
        <span class="text-xs text-[var(--text-secondary)] mb-2">{{ error }}</span>
        <button @click="emit('create')" class="btn btn-sm btn-secondary">创建新会话</button>
      </div>

      <!-- No match (search but no results) -->
      <div v-else-if="searchQuery && sessions.length === 0" class="flex flex-col items-center justify-center py-10 text-center">
        <svg class="w-8 h-8 text-[var(--text-quaternary)] mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
        <span class="text-xs text-[var(--text-tertiary)]">无匹配会话</span>
      </div>

      <!-- Empty (no sessions at all) -->
      <div v-else-if="sessions.length === 0" class="empty-state py-10">
        <div class="empty-state-icon"><span class="text-lg">💬</span></div>
        <div class="empty-state-title">暂无对话</div>
        <div class="empty-state-desc">点击上方「新对话」开始</div>
      </div>

      <!-- Session list -->
      <template v-else>
        <div
          v-for="s in sessions"
          :key="s.uuid"
          class="group flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs cursor-pointer transition-all duration-150"
          :class="currentSessionId === s.uuid ? 'bg-[var(--brand-50)] dark:bg-[var(--brand-600)]/15 text-[var(--brand-700)] dark:text-[var(--brand-300)] font-medium' : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'"
          @click="emit('select', s.uuid)"
        >
          <div
            class="w-7 h-7 rounded-lg flex items-center justify-center text-xs shrink-0"
            :class="currentSessionId === s.uuid ? 'bg-[var(--brand-100)] dark:bg-[var(--brand-600)]/30 text-[var(--brand-600)] dark:text-[var(--brand-400)]' : 'bg-[var(--surface-tertiary)] text-[var(--text-tertiary)]'"
          >💬</div>
          <div class="flex-1 min-w-0">
            <!-- Rename mode -->
            <input
              v-if="editingId === s.uuid"
              ref="editInput"
              v-model="editTitle"
              @keydown="handleKeydownRename"
              @blur="commitRename"
              @click.stop
              class="w-full bg-[var(--surface-primary)] border border-[var(--brand-400)] rounded px-1.5 py-0.5 text-xs outline-none"
            />
            <!-- Normal title -->
            <div v-else class="flex items-center gap-1.5" @dblclick.stop="startRename(s)">
              <span class="truncate max-w-[120px]">{{ s.title }}</span>
              <span v-if="s.model" class="text-[9px] font-mono opacity-60 truncate max-w-[50px]">{{ s.model }}</span>
            </div>
            <div class="flex items-center gap-2 mt-0.5">
              <span class="text-[10px] text-[var(--text-tertiary)] opacity-60">{{ relativeTime(s.created_at) }}</span>
            </div>
          </div>
          <button
            @click.stop="emit('delete', s.uuid)"
            class="opacity-0 group-hover:opacity-100 p-0.5 rounded text-[var(--text-tertiary)] hover:text-red-500 transition-all duration-150 shrink-0"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
          </button>
        </div>
      </template>
    </div>
  </aside>
</template>
