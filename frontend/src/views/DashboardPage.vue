<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const auth = useAuthStore()
const info = ref<any>(null)
const health = ref<any>(null)
const stats = ref({ files: 0, sessions: 0, documents: 0, templates: 0, tasks: 0, kb_files: 0 })
const loading = ref(true)
const recentLogs = ref<any[]>([])
const showQuickActions = ref(true)

interface FeatureCard {
  title: string
  desc: string
  path: string
  icon: string
  gradient: string
  stat: number
  statLabel: string
}

const features: FeatureCard[] = [
  { title: "AI 对话", desc: "多角色法律 AI 助手，支持知识库检索", path: "/chat", icon: "💬", gradient: "from-blue-500 to-indigo-600", stat: 0, statLabel: "对话" },
  { title: "文件库", desc: "PDF/Word/Excel/OCR 智能解析入库", path: "/files", icon: "📁", gradient: "from-emerald-500 to-teal-600", stat: 0, statLabel: "文件" },
  { title: "文书生成", desc: "一键生成起诉状、答辩状、代理词等", path: "/documents", icon: "📝", gradient: "from-amber-500 to-orange-600", stat: 0, statLabel: "文书" },
  { title: "模板库", desc: "预置+自定义法律文书模板", path: "/templates", icon: "📋", gradient: "from-rose-500 to-pink-600", stat: 0, statLabel: "模板" },
  { title: "法条检索", desc: "法律法规搜索引擎，智能匹配", path: "/statutes", icon: "⚖️", gradient: "from-violet-500 to-purple-600", stat: 0, statLabel: "法条" },
  { title: "智能检索", desc: "语义+关键词混合全文检索", path: "/search", icon: "🔍", gradient: "from-cyan-500 to-sky-600", stat: 0, statLabel: "检索" },
]

const quickActions = [
  { label: "新建对话", icon: "💬", path: "/chat", color: "bg-blue-500" },
  { label: "上传文件", icon: "📄", path: "/files", color: "bg-emerald-500" },
  { label: "生成文书", icon: "📝", path: "/documents", color: "bg-amber-500" },
  { label: "检索法条", icon: "⚖️", path: "/statutes", color: "bg-violet-500" },
]

async function loadData() {
  loading.value = true
  try {
    const h = auth.setTokenHeader()
    const [infoR, healthR, filesR, sessR, docsR, tmplR, tasksR, kbR] = await Promise.all([
      fetch("/api/v1/info"),
      fetch("/api/v1/health"),
      fetch("/api/v1/files", { headers: h }),
      fetch("/api/v1/chat/sessions", { headers: h }),
      fetch("/api/v1/documents", { headers: h }),
      fetch("/api/v1/templates", { headers: h }),
      fetch("/api/v1/tasks", { headers: h }),
      fetch("/api/v1/knowledge/files", { headers: h }).catch(() => new Response('{"data":[]}')),
    ])
    info.value = (await infoR.json()) || null
    health.value = (await healthR.json()) || null
    const f = (await filesR.json()).data || []
    const s = (await sessR.json()).data || []
    const d = (await docsR.json()).data || []
    const t = (await tmplR.json()).data || []
    const tk = (await tasksR.json()).data || []
    const kb = (await kbR.json()).data || []
    stats.value = {
      files: f.length, sessions: s.length,
      documents: d.length, templates: t.length,
      tasks: tk.filter((x: any) => x.status === "running" || x.status === "processing").length,
      kb_files: kb.length,
    }
    features[0].stat = stats.value.sessions
    features[1].stat = stats.value.files
    features[2].stat = stats.value.documents
    features[3].stat = stats.value.templates

    // Load recent logs
    const logsR = await fetch("/api/v1/logs?limit=5", { headers: h }).catch(() => new Response('{"data":[]}'))
    const logsD = await logsR.json()
    recentLogs.value = (logsD.data || []).slice(0, 5)
  } catch { /* server offline */ }
  loading.value = false
}

function formatTime(ts: number) {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

onMounted(loadData)
</script>

<template>
  <div class="p-4 md:p-6 max-w-6xl mx-auto space-y-5 animate-fadeIn">
    <!-- Header Section -->
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-xl font-bold tracking-tight">工作台</h1>
          <span class="tag tag-zinc text-[10px]">v0.2</span>
        </div>
        <p class="text-xs text-[var(--text-secondary)] mt-1">本地私有化法律 AI 智能工作台</p>
      </div>
      <div v-if="health" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border-light)]">
        <span class="status-dot status-dot-green" />
        <span class="text-[11px] font-medium text-[var(--text-secondary)]">系统运行中</span>
      </div>
      <div v-else-if="!loading" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30">
        <span class="status-dot status-dot-red" />
        <span class="text-[11px] font-medium text-red-600 dark:text-red-400">服务未连接</span>
      </div>
    </div>

    <!-- Stats Row -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
      <div v-for="s in [
        { label: '文件', count: stats.files, icon: '📄', color: 'from-emerald-500 to-teal-500' },
        { label: '对话', count: stats.sessions, icon: '💬', color: 'from-blue-500 to-indigo-500' },
        { label: '文书', count: stats.documents, icon: '📝', color: 'from-amber-500 to-orange-500' },
        { label: '模板', count: stats.templates, icon: '📋', color: 'from-rose-500 to-pink-500' },
        { label: '知识库', count: stats.kb_files, icon: '📚', color: 'from-violet-500 to-purple-500' },
        { label: '运行中', count: stats.tasks, icon: '⚡', color: 'from-cyan-500 to-sky-500' },
      ]" :key="s.label" class="card card-interactive p-3 flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-br flex items-center justify-center text-base shrink-0 shadow-sm" :class="s.color">
          {{ s.icon }}
        </div>
        <div>
          <div class="text-lg font-bold tabular-nums">{{ s.count }}</div>
          <div class="text-[10px] text-[var(--text-tertiary)] font-medium">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
      <button
        v-for="a in quickActions"
        :key="a.label"
        @click="router.push(a.path)"
        class="btn btn-md btn-secondary shrink-0 gap-2"
      >
        <span>{{ a.icon }}</span>
        {{ a.label }}
      </button>
    </div>

    <!-- Feature Grid -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider">功能模块</h2>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <button
          v-for="f in features"
          :key="f.path"
          @click="router.push(f.path)"
          class="card card-interactive p-4 text-left group"
        >
          <div class="flex items-start gap-3.5">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center text-lg shrink-0 shadow-sm" :class="f.gradient">{{ f.icon }}</div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold group-hover:text-[var(--brand-600)] dark:group-hover:text-[var(--brand-400)] transition-colors">{{ f.title }}</div>
              <div class="text-xs text-[var(--text-tertiary)] mt-0.5 truncate-2">{{ f.desc }}</div>
            </div>
          </div>
          <div v-if="f.stat > 0" class="mt-3 pt-3 border-t border-[var(--border-light)] flex justify-between items-center">
            <span class="text-[11px] text-[var(--text-tertiary)]">{{ f.statLabel }}</span>
            <span class="text-sm font-bold tabular-nums text-[var(--brand-600)] dark:text-[var(--brand-400)]">{{ f.stat }}</span>
          </div>
        </button>
      </div>
    </div>

    <!-- Access Info + Recent Activity -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Access Info -->
      <div v-if="info?.ok" class="card p-4 lg:col-span-2">
        <h2 class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-3">访问入口</h2>
        <div class="space-y-1.5">
          <div class="flex items-center justify-between bg-[var(--surface-secondary)] rounded-lg px-3 py-2">
            <span class="text-xs text-[var(--text-tertiary)]">本机</span>
            <span class="text-xs font-mono text-[var(--brand-600)] dark:text-[var(--brand-400)] font-medium">{{ info.local_url }}</span>
          </div>
          <div v-if="info.lan_url" class="flex items-center justify-between bg-[var(--surface-secondary)] rounded-lg px-3 py-2">
            <span class="text-xs text-[var(--text-tertiary)]">局域网</span>
            <span class="text-xs font-mono text-[var(--brand-600)] dark:text-[var(--brand-400)] font-medium">{{ info.lan_url }}</span>
          </div>
          <div v-if="info.tunnel_url" class="flex items-center justify-between bg-[var(--surface-secondary)] rounded-lg px-3 py-2">
            <span class="text-xs text-[var(--text-tertiary)]">公网隧道</span>
            <span class="text-xs font-mono text-[var(--brand-600)] dark:text-[var(--brand-400)] font-medium">{{ info.tunnel_url }}</span>
          </div>
        </div>
      </div>

      <!-- Recent Activity -->
      <div class="card p-4">
        <h2 class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-3">最近操作</h2>
        <div v-if="recentLogs.length === 0" class="flex flex-col items-center justify-center py-6 text-[var(--text-tertiary)]">
          <span class="text-lg mb-1">📄</span>
          <span class="text-xs">暂无操作记录</span>
        </div>
        <div v-else class="space-y-2">
          <div v-for="log in recentLogs" :key="log.id" class="flex items-center gap-2.5 text-xs">
            <span class="w-1.5 h-1.5 rounded-full bg-[var(--brand-400)] shrink-0" />
            <span class="text-[var(--text-secondary)] truncate">{{ log.action }}</span>
            <span class="ml-auto text-[var(--text-tertiary)] shrink-0 font-mono text-[10px]">{{ formatTime(log.created_at) }}</span>
          </div>
          <button @click="router.push('/logs')" class="w-full text-center text-[11px] text-[var(--brand-600)] dark:text-[var(--brand-400)] pt-2 hover:underline mt-1">查看全部 &rarr;</button>
        </div>
      </div>
    </div>

    <!-- Loading / Offline -->
    <div v-if="loading" class="flex items-center justify-center py-8">
      <div class="flex items-center gap-3 text-xs text-[var(--text-tertiary)]">
        <div class="typing-dots"><span /><span /><span /></div>
        加载中...
      </div>
    </div>
    <div v-else-if="!health" class="card p-4 text-center">
      <p class="text-xs text-red-500 dark:text-red-400">后端服务未连接，部分功能不可用</p>
    </div>
  </div>
</template>
