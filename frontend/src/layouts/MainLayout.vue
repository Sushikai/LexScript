<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter, useRoute } from "vue-router"
import CommandPalette from "@/components/CommandPalette.vue"

const router = useRouter()
const route = useRoute()

const mobileNavOpen = ref(false)
const darkMode = ref(localStorage.getItem("lexscript-theme") === "dark")
const systemInfo = ref({ service: "LexScript", version: "0.2.0" })

interface NavItem {
  path: string
  label: string
  icon: string
  badge?: number | string
}

const navGroups = [
  {
    label: "核心功能",
    items: [
      { path: "/", label: "工作台", icon: "dashboard" },
      { path: "/chat", label: "AI 对话", icon: "chat" },
      { path: "/search", label: "智能检索", icon: "search" },
    ] as NavItem[],
  },
  {
    label: "文档管理",
    items: [
      { path: "/files", label: "文件库", icon: "folder" },
      { path: "/documents", label: "文书管理", icon: "document" },
      { path: "/templates", label: "模板库", icon: "template" },
    ] as NavItem[],
  },
  {
    label: "知识库",
    items: [
      { path: "/statutes", label: "法条检索", icon: "law" },
      { path: "/tasks", label: "异步任务", icon: "tasks" },
    ] as NavItem[],
  },
  {
    label: "系统",
    items: [
      { path: "/config", label: "系统设置", icon: "settings" },
      { path: "/logs", label: "操作日志", icon: "log" },
    ] as NavItem[],
  },
]

const mobileNav = [
  { path: "/", label: "工作台", icon: "dashboard" },
  { path: "/chat", label: "AI", icon: "chat" },
  { path: "/search", label: "搜索", icon: "search" },
  { path: "/files", label: "文件", icon: "folder" },
  { path: "/documents", label: "文书", icon: "document" },
  { path: "/statutes", label: "法条", icon: "law" },
  { path: "/config", label: "设置", icon: "settings" },
]

const SVG_ICONS: Record<string, string> = {
  dashboard: `<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />`,
  chat: `<path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />`,
  search: `<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />`,
  folder: `<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />`,
  document: `<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />`,
  template: `<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M18.75 4.236c.982.143 1.954.317 2.916.52A6.003 6.003 0 0016.27 9.728M18.75 4.236V4.5c0 2.108-.966 3.99-2.48 5.228m0 0a6.023 6.023 0 01-2.77.896m0 0a6.023 6.023 0 01-2.77-.896" />`,
  law: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />`,
  tasks: `<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />`,
  settings: `<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />`,
  log: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />`,
}

function toggleDark() {
  darkMode.value = !darkMode.value
  document.documentElement.classList.toggle("dark", darkMode.value)
  localStorage.setItem("lexscript-theme", darkMode.value ? "dark" : "light")
}

async function loadInfo() {
  try {
    const r = await fetch("/api/v1/info")
    const d = await r.json()
    if (d.ok) systemInfo.value = d.data || d
  } catch { /* ignore */ }
}

function isActive(path: string) {
  if (path === "/") return route.path === "/"
  return route.path.startsWith(path)
}

// Init theme
if (darkMode.value) {
  document.documentElement.classList.add("dark")
}

onMounted(loadInfo)
</script>

<template>
  <div class="h-screen flex bg-[var(--surface-primary)] text-[var(--text-primary)] overflow-hidden">
    <!-- Desktop Sidebar -->
    <aside class="hidden md:flex flex-col w-60 bg-[var(--surface-secondary)] border-r border-[var(--border-light)] h-full fixed left-0 top-0 z-30">
      <!-- Brand -->
      <div class="h-14 flex items-center gap-3 px-5 border-b border-[var(--border-light)]">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)] flex items-center justify-center text-white text-sm font-bold shadow-sm shadow-[var(--brand-500)]/20">&#9878;</div>
        <div>
          <div class="text-sm font-bold tracking-tight">LexScript</div>
          <div class="text-[10px] text-[var(--text-tertiary)] font-medium">法律 AI 智能工作台</div>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        <div v-for="group in navGroups" :key="group.label">
          <div class="section-title px-2">{{ group.label }}</div>
          <div class="space-y-0.5">
            <button
              v-for="item in group.items"
              :key="item.path"
              @click="router.push(item.path)"
              :class="['sidebar-item', isActive(item.path) ? 'sidebar-item-active' : '']"
            >
              <span class="sidebar-icon">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" v-html="SVG_ICONS[item.icon] || ''" />
              </span>
              <span>{{ item.label }}</span>
            </button>
          </div>
        </div>
      </nav>

      <!-- Bottom -->
      <div class="p-3 border-t border-[var(--border-light)] space-y-2">
        <button @click="() => {}" class="sidebar-item text-[10px]">
          <kbd class="font-mono text-[9px] px-1 py-0.5 rounded bg-[var(--surface-tertiary)]">⌘K</kbd>
          <span>快速命令</span>
        </button>
        <button @click="toggleDark" class="sidebar-item text-[10px]">
          <span class="sidebar-icon">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <path v-if="darkMode" stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
              <path v-else stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
            </svg>
          </span>
          <span>{{ darkMode ? '浅色模式' : '深色模式' }}</span>
        </button>
        <div class="flex items-center justify-between px-2 pt-1">
          <span class="text-[10px] text-[var(--text-tertiary)]">v{{ systemInfo.version }}</span>
          <span class="text-[9px] text-[var(--text-quaternary)]">数据不出本机</span>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="md:ml-60 flex flex-col flex-1 h-full min-w-0">
      <!-- Mobile Top Bar -->
      <header class="md:hidden h-12 flex items-center justify-between px-4 bg-[var(--surface-primary)] border-b border-[var(--border-light)] shrink-0">
        <button @click="mobileNavOpen = !mobileNavOpen" class="p-1.5 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
        </button>
        <div class="flex items-center gap-2">
          <span class="w-6 h-6 rounded-md bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)] flex items-center justify-center text-white text-[10px] font-bold">&#9878;</span>
          <span class="text-sm font-semibold">LexScript</span>
        </div>
        <button @click="toggleDark" class="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
            <path v-if="darkMode" stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
          </svg>
        </button>
      </header>

      <!-- Page Content -->
      <main class="flex-1 overflow-y-auto">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

      <!-- Status Bar -->
      <footer class="hidden md:flex items-center justify-between px-4 py-1 bg-[var(--surface-secondary)] border-t border-[var(--border-light)] text-[10px] text-[var(--text-tertiary)] shrink-0">
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1">
            <span class="status-dot status-dot-green" />
            <span>系统在线</span>
          </span>
          <span>v{{ systemInfo.version }}</span>
        </div>
        <div class="flex items-center gap-3">
          <span>{{ systemInfo.service }}</span>
          <span>数据不出本机</span>
        </div>
      </footer>

      <!-- Mobile Bottom Tab Bar -->
      <nav class="md:hidden flex items-center justify-around bg-[var(--surface-primary)] border-t border-[var(--border-light)] py-1 shrink-0 safe-area-bottom">
        <button
          v-for="item in mobileNav"
          :key="item.path"
          @click="router.push(item.path)"
          class="flex flex-col items-center gap-0.5 py-1 px-3 rounded-lg transition-colors"
          :class="isActive(item.path) ? 'text-[var(--brand-600)] dark:text-[var(--brand-400)]' : 'text-[var(--text-tertiary)]'"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" v-html="SVG_ICONS[item.icon] || ''" />
          <span class="text-[10px] font-medium">{{ item.label }}</span>
        </button>
      </nav>
    </div>

    <!-- Mobile Menu Overlay -->
    <transition name="fade">
      <div v-if="mobileNavOpen" class="fixed inset-0 z-40 md:hidden">
        <div class="absolute inset-0 bg-black/40" @click="mobileNavOpen = false" />
        <div class="absolute left-0 top-0 bottom-0 w-64 bg-[var(--surface-primary)] shadow-xl animate-slideInLeft">
          <div class="h-14 flex items-center justify-between px-5 border-b border-[var(--border-light)]">
            <span class="font-semibold text-sm">导航</span>
            <button @click="mobileNavOpen = false" class="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] transition-colors">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <div class="p-3 space-y-6 overflow-y-auto h-[calc(100%-3.5rem)]">
            <div v-for="group in navGroups" :key="group.label">
              <div class="section-title px-2">{{ group.label }}</div>
              <div class="space-y-0.5">
                <button
                  v-for="item in group.items"
                  :key="item.path"
                  @click="router.push(item.path); mobileNavOpen = false"
                  :class="['sidebar-item', isActive(item.path) ? 'sidebar-item-active' : '']"
                >
                  <span class="sidebar-icon">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" v-html="SVG_ICONS[item.icon] || ''" />
                  </span>
                  <span>{{ item.label }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
  <CommandPalette />
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s var(--ease-out); }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.page-enter-active, .page-leave-active {
  transition: all 0.2s var(--ease-out);
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
