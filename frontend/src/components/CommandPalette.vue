<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue"
import { useRouter } from "vue-router"

const router = useRouter()
const open = ref(false)
const query = ref("")
const selectedIndex = ref(0)

interface Command {
  id: string
  label: string
  desc: string
  icon: string
  action: () => void
}

const commands = computed<Command[]>(() => {
  const base: Command[] = [
    { id: "dashboard", label: "工作台", desc: "返回首页仪表盘", icon: "dashboard", action: () => router.push("/") },
    { id: "chat", label: "AI 对话", desc: "开始新的法律咨询对话", icon: "chat", action: () => router.push("/chat") },
    { id: "files", label: "文件库", desc: "管理上传的法律文件", icon: "folder", action: () => router.push("/files") },
    { id: "documents", label: "文书管理", desc: "AI 生成法律文书", icon: "document", action: () => router.push("/documents") },
    { id: "templates", label: "模板库", desc: "预置法律文书模板", icon: "template", action: () => router.push("/templates") },
    { id: "statutes", label: "法条检索", desc: "法律法规搜索引擎", icon: "law", action: () => router.push("/statutes") },
    { id: "search", label: "智能检索", desc: "语义+关键词全文检索", icon: "search", action: () => router.push("/search") },
    { id: "tasks", label: "异步任务", desc: "查看后台任务进度", icon: "tasks", action: () => router.push("/tasks") },
    { id: "config", label: "系统设置", desc: "配置模型和系统参数", icon: "settings", action: () => router.push("/config") },
    { id: "logs", label: "操作日志", desc: "查看系统操作记录", icon: "log", action: () => router.push("/logs") },
  ]
  if (!query.value.trim()) return base
  const q = query.value.toLowerCase()
  return base.filter((c) => c.label.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q))
})

function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault()
    open.value = !open.value
    if (open.value) query.value = ""
    return
  }
  if (!open.value) return
  if (e.key === "Escape") {
    open.value = false
    return
  }
  if (e.key === "ArrowDown") {
    e.preventDefault()
    selectedIndex.value = Math.min(selectedIndex.value + 1, commands.value.length - 1)
    return
  }
  if (e.key === "ArrowUp") {
    e.preventDefault()
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
    return
  }
  if (e.key === "Enter" && commands.value[selectedIndex.value]) {
    e.preventDefault()
    commands.value[selectedIndex.value].action()
    open.value = false
    return
  }
}

function execute(cmd: Command) {
  cmd.action()
  open.value = false
}

onMounted(() => window.addEventListener("keydown", onKeydown))
onUnmounted(() => window.removeEventListener("keydown", onKeydown))

const SVG_ICONS: Record<string, string> = {
  dashboard: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6z" /></svg>`,
  chat: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>`,
  folder: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" /></svg>`,
  document: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>`,
  template: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M18.75 4.236c.982.143 1.954.317 2.916.52A6.003 6.003 0 0016.27 9.728M18.75 4.236V4.5c0 2.108-.966 3.99-2.48 5.228m0 0a6.023 6.023 0 01-2.77.896m0 0a6.023 6.023 0 01-2.77-.896" /></svg>`,
  law: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>`,
  search: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>`,
  tasks: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3-3" /></svg>`,
  settings: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /></svg>`,
  log: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
}
</script>

<template>
  <teleport to="body">
    <transition name="cmd">
      <div v-if="open" class="fixed inset-0 z-[9999] flex items-start justify-center pt-[10vh]" @click.self="open = false">
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" />
        <div class="relative w-full max-w-lg bg-[var(--surface-primary)] rounded-xl shadow-2xl border border-[var(--border-light)] overflow-hidden animate-scaleIn">
          <!-- Search Input -->
          <div class="flex items-center gap-3 px-4 border-b border-[var(--border-light)]">
            <svg class="w-4 h-4 text-[var(--text-tertiary)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
            <input
              v-model="query"
              ref="inputRef"
              type="text"
              placeholder="搜索功能或输入命令..."
              class="flex-1 bg-transparent border-none outline-none py-3.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]"
              autofocus
            />
            <kbd class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-tertiary)] text-[var(--text-tertiary)]">ESC</kbd>
          </div>

          <!-- Results -->
          <div class="max-h-72 overflow-y-auto p-2">
            <div v-if="commands.length === 0" class="flex flex-col items-center py-8 text-[var(--text-tertiary)]">
              <svg class="w-8 h-8 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
              <span class="text-xs">未找到匹配项</span>
            </div>
            <button
              v-for="(cmd, i) in commands"
              :key="cmd.id"
              @click="execute(cmd)"
              @mouseenter="selectedIndex = i"
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-100"
              :class="i === selectedIndex ? 'bg-[var(--brand-50)] dark:bg-[var(--brand-600)]/15 text-[var(--brand-700)] dark:text-[var(--brand-300)]' : 'text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'"
            >
              <span class="w-7 h-7 rounded-md bg-[var(--surface-tertiary)] flex items-center justify-center shrink-0" :class="i === selectedIndex ? 'bg-[var(--brand-100)] dark:bg-[var(--brand-600)]/20' : ''" v-html="SVG_ICONS[cmd.icon]" />
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium">{{ cmd.label }}</div>
                <div class="text-[11px] text-[var(--text-tertiary)] truncate">{{ cmd.desc }}</div>
              </div>
              <kbd v-if="i < 9" class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-tertiary)] text-[var(--text-quaternary)]">{{ i + 1 }}</kbd>
            </button>
          </div>

          <!-- Footer -->
          <div class="px-4 py-2.5 border-t border-[var(--border-light)] flex items-center gap-3 text-[10px] text-[var(--text-tertiary)]">
            <span class="flex items-center gap-1"><kbd class="font-mono px-1 py-0.5 rounded bg-[var(--surface-tertiary)]">↑↓</kbd> 导航</span>
            <span class="flex items-center gap-1"><kbd class="font-mono px-1 py-0.5 rounded bg-[var(--surface-tertiary)]">↵</kbd> 打开</span>
            <span class="flex items-center gap-1 ml-auto"><kbd class="font-mono px-1 py-0.5 rounded bg-[var(--surface-tertiary)]">⌘K</kbd> 切换</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.cmd-enter-active, .cmd-leave-active { transition: all 0.2s var(--ease-out); }
.cmd-enter-from, .cmd-leave-to { opacity: 0; }
.cmd-enter-from > div:last-child, .cmd-leave-to > div:last-child { transform: scale(0.95) translateY(-10px); }
</style>
