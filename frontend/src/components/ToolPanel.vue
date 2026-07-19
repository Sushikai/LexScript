<script setup lang="ts">
import { ref, onMounted } from "vue"
import type { FileEntry, Statute, Template } from "@/types"

const API = "/api/v1"

type PanelTab = "files" | "statutes" | "templates" | "info"
const activeTab = ref<PanelTab>("files")

const files = ref<FileEntry[]>([])
async function loadFiles() {
  try { const r = await fetch(`${API}/files`); const d = await r.json(); files.value = (d.data || []).slice(0, 20) } catch { files.value = [] }
}

const statuteQuery = ref("")
const statutes = ref<Statute[]>([])
const searching = ref(false)
async function searchStatutes() {
  if (!statuteQuery.value.trim()) return
  searching.value = true
  try {
    const r = await fetch(`${API}/statutes/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: statuteQuery.value, limit: 10 }),
    })
    const d = await r.json()
    statutes.value = (d.data || []).slice(0, 10)
  } catch { statutes.value = [] }
  searching.value = false
}

const templates = ref<Template[]>([])
async function loadTemplates() {
  try { const r = await fetch(`${API}/templates`); const d = await r.json(); templates.value = (d.data || []).slice(0, 20) } catch { templates.value = [] }
}

const info = ref<Record<string, string>>({})
async function loadInfo() {
  try {
    const r = await fetch(`${API}/info`)
    const d = await r.json()
    if (d.ok) {
      info.value = {
        服务: `${d.service} v${d.version}`,
        绑定: `${d.host}:${d.port}`,
        "LAN IP": d.lan_ip || "未检测",
        "公网隧道": d.tunnel_url || "未启动",
        状态: "运行中",
      }
    }
  } catch { info.value = { 状态: "无法连接" } }
}

onMounted(() => { loadFiles(); loadTemplates(); loadInfo() })
</script>

<template>
  <div class="w-72 border-l border-[var(--border-light)] bg-[var(--surface-secondary)] flex flex-col overflow-hidden">
    <!-- Tabs -->
    <div class="flex border-b border-[var(--border-light)] text-xs">
      <button
        v-for="tab in (['files', 'statutes', 'templates', 'info'] as PanelTab[])"
        :key="tab"
        class="flex-1 py-2.5 text-center transition-all duration-150 font-medium"
        :class="activeTab === tab
          ? 'text-[var(--brand-600)] dark:text-[var(--brand-400)] border-b-2 border-[var(--brand-500)] bg-[var(--surface-primary)]'
          : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'"
        @click="activeTab = tab"
      >
        {{ tab === "files" ? "📁 文件" : tab === "statutes" ? "⚖ 法条" : tab === "templates" ? "📋 模板" : "📊 状态" }}
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-3 space-y-2">
      <!-- Files -->
      <div v-show="activeTab === 'files'">
        <div v-if="files.length === 0" class="empty-state !py-8">
          <div class="empty-state-icon !w-10 !h-10"><span>📁</span></div>
          <div class="empty-state-title text-xs">暂无文件</div>
          <div class="empty-state-desc text-[11px]">导入文件后在此查看</div>
        </div>
        <div v-for="f in files" :key="f.id" class="card p-2.5 cursor-pointer hover:border-[var(--brand-300)] transition-all duration-150">
          <div class="text-sm font-medium truncate">{{ f.name }}</div>
          <div class="flex items-center gap-2 mt-1 text-[11px] text-[var(--text-tertiary)]">
            <span>{{ (f.size / 1024).toFixed(1) }} KB</span>
            <span class="status-dot" :class="f.status === 'indexed' ? 'status-dot-green' : 'status-dot-amber'" />
            <span :class="f.status === 'indexed' ? 'text-green-500' : 'text-amber-500'">{{ f.status || "待处理" }}</span>
          </div>
        </div>
      </div>

      <!-- Statutes -->
      <div v-show="activeTab === 'statutes'">
        <div class="flex gap-1.5 mb-3">
          <input
            v-model="statuteQuery"
            type="text"
            placeholder="搜索法条..."
            class="input text-xs"
            @keydown.enter="searchStatutes"
          />
          <button class="btn btn-sm btn-primary shrink-0" :disabled="searching" @click="searchStatutes">
            {{ searching ? '...' : '搜索' }}
          </button>
        </div>
        <div v-if="statutes.length === 0 && !statuteQuery" class="empty-state !py-8">
          <div class="empty-state-icon !w-10 !h-10"><span>⚖</span></div>
          <div class="empty-state-title text-xs">搜索法条</div>
          <div class="empty-state-desc text-[11px]">输入关键词搜索法律法规</div>
        </div>
        <div v-for="s in statutes" :key="s.code" class="card p-3">
          <div class="text-sm font-semibold">{{ s.name }}</div>
          <div class="text-[11px] text-[var(--text-tertiary)] mt-0.5">{{ s.code }} · {{ s.category }}</div>
          <div class="text-xs text-[var(--text-secondary)] mt-1.5 truncate-2">{{ s.content }}</div>
        </div>
      </div>

      <!-- Templates -->
      <div v-show="activeTab === 'templates'">
        <div v-if="templates.length === 0" class="empty-state !py-8">
          <div class="empty-state-icon !w-10 !h-10"><span>📋</span></div>
          <div class="empty-state-title text-xs">暂无模板</div>
        </div>
        <div v-for="t in templates" :key="t.id" class="card p-3 cursor-pointer hover:border-[var(--brand-300)] transition-all duration-150">
          <div class="text-sm font-medium">{{ t.name }}</div>
          <div class="text-[11px] text-[var(--text-tertiary)] mt-0.5">{{ t.category }}</div>
        </div>
      </div>

      <!-- Info -->
      <div v-show="activeTab === 'info'">
        <div class="space-y-1">
          <div v-for="(val, key) in info" :key="key" class="flex justify-between items-center py-2 px-3 rounded-lg bg-[var(--surface-primary)] border border-[var(--border-light)]">
            <span class="text-xs text-[var(--text-tertiary)]">{{ key }}</span>
            <span class="text-xs font-medium text-right max-w-[55%] truncate">{{ val }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
