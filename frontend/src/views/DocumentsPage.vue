<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"

const API = "/api/v1"
const router = useRouter()

interface Document { uuid: string; title: string; doc_type: string; case_name: string; status: string; created_at: string; updated_at: string }
interface FileItem { id: number; name: string; status: string; mime: string }
interface TemplateItem { id: number; name: string; description: string }

const documents = ref<Document[]>([])
const loading = ref(false)
const showGenerate = ref(false)
const caseName = ref("")
const docType = ref("起诉状")
const extraReq = ref("")
const generating = ref(false)
const progressStatus = ref("")
const progressText = ref("")
const selectedFileIds = ref<number[]>([])
const selectedTemplateId = ref<number | null>(null)

const files = ref<FileItem[]>([])
const templates = ref<TemplateItem[]>([])

const docTypes = ["起诉状", "答辩状", "代理词", "上诉状", "合同", "律师函", "裁定书"]

const limit = ref(20)
const offset = ref(0)
const hasMore = ref(true)

async function loadDocs() {
  loading.value = true
  try {
    const r = await fetch(`${API}/documents?limit=${limit.value}&offset=${offset.value}`)
    const d = await r.json()
    documents.value = d.data || []
    hasMore.value = (d.data || []).length >= limit.value
  } catch { }
  loading.value = false
}

async function loadMore() {
  offset.value += limit.value
  loading.value = true
  try {
    const r = await fetch(`${API}/documents?limit=${limit.value}&offset=${offset.value}`)
    const d = await r.json()
    const more = d.data || []
    documents.value.push(...more)
    hasMore.value = more.length >= limit.value
  } catch { }
  loading.value = false
}

async function loadFiles() {
  try { const r = await fetch(`${API}/files?limit=200`); const d = await r.json(); files.value = d.data || [] } catch { }
}

async function loadTemplates() {
  try { const r = await fetch(`${API}/templates`); const d = await r.json(); templates.value = d.data || [] } catch { }
}

function toggleFile(id: number) {
  const idx = selectedFileIds.value.indexOf(id)
  if (idx >= 0) selectedFileIds.value.splice(idx, 1)
  else selectedFileIds.value.push(id)
}

async function generateDoc() {
  if (!caseName.value.trim()) return
  generating.value = true
  progressStatus.value = "准备中..."
  progressText.value = ""

  try {
    const r = await fetch(`${API}/documents/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        case_name: caseName.value,
        doc_type: docType.value,
        file_ids: selectedFileIds.value,
        template_id: selectedTemplateId.value,
        extra_requirements: extraReq.value,
      }),
    })

    const reader = r.body?.getReader()
    if (!reader) { generating.value = false; return }

    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const parts = buffer.split("\n\n")
      buffer = parts.pop() || ""

      for (const part of parts) {
        if (!part.trim()) continue
        const lines = part.split("\n")
        let eventType = ""
        let dataStr = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) eventType = line.slice(7).trim()
          else if (line.startsWith("data: ")) dataStr = line.slice(6).trim()
        }
        if (!eventType || !dataStr) continue

        try {
          const data = JSON.parse(dataStr)

          if (eventType === "status") {
            progressStatus.value = data.message || data.status || ""
          } else if (eventType === "chunk") {
            progressText.value += data.text || ""
          } else if (eventType === "done") {
            const docUuid = data.document?.uuid || ""
            if (docUuid) router.push(`/documents/${docUuid}`)
          } else if (eventType === "error") {
            progressStatus.value = `❌ ${data.message || "生成失败"}`
          }
        } catch { /* skip */ }
      }
    }
  } catch { progressStatus.value = "网络错误" }
  generating.value = false
}

async function deleteDoc(uuid: string) {
  if (!confirm("确认删除？")) return
  try { await fetch(`${API}/documents/${uuid}`, { method: "DELETE" }); loadDocs() } catch { }
}

function formatTime(t: string) {
  if (!t) return ""
  const d = new Date(t)
  return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

const statusColors: Record<string, string> = {
  draft: "tag-zinc", generating: "tag-amber", completed: "tag-green", failed: "tag-red",
}
const statusLabels: Record<string, string> = {
  draft: "草稿", generating: "生成中", completed: "已完成", failed: "失败",
}

onMounted(() => { loadDocs(); loadFiles(); loadTemplates() })
</script>

<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-lg font-bold">文书管理</h1>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5">AI 一键生成法律文书</p>
      </div>
      <button @click="showGenerate = !showGenerate" class="btn btn-sm btn-primary">+ 生成文书</button>
    </div>

    <!-- Generate Panel -->
    <div v-if="showGenerate" class="card p-4 mb-4 animate-scaleIn">
      <div class="flex items-center gap-2 mb-3">
        <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white text-xs">📝</div>
        <h3 class="text-sm font-semibold">一键生成文书</h3>
      </div>
      <div class="space-y-3">
        <div>
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">案件名称</label>
          <input v-model="caseName" type="text" placeholder="如: 张三诉李四合同纠纷案" class="input" />
        </div>
        <div class="flex gap-3">
          <div class="flex-1">
            <label class="text-xs text-[var(--text-tertiary)] mb-1 block">文书类型</label>
            <select v-model="docType" class="select">
              <option v-for="t in docTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div class="flex-1">
            <label class="text-xs text-[var(--text-tertiary)] mb-1 block">模板（可选）</label>
            <select v-model="selectedTemplateId" class="select">
              <option :value="null">不指定模板</option>
              <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
        </div>

        <!-- File Selector -->
        <div v-if="files.length > 0">
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">关联文件（可选）</label>
          <div class="max-h-32 overflow-y-auto bg-[var(--surface-secondary)] border border-[var(--border-light)] rounded-lg p-2 space-y-1">
            <label v-for="f in files" :key="f.id" class="flex items-center gap-2 px-2 py-1 rounded hover:bg-[var(--surface-hover)] cursor-pointer text-xs">
              <input type="checkbox" :checked="selectedFileIds.includes(f.id)" @change="toggleFile(f.id)" class="rounded border-[var(--border-medium)]" />
              <span class="text-[var(--text-secondary)] truncate">{{ f.name }}</span>
              <span class="ml-auto text-[var(--text-tertiary)] shrink-0">{{ f.status }}</span>
            </label>
          </div>
        </div>

        <div>
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">额外要求（可选）</label>
          <textarea v-model="extraReq" placeholder="如: 侧重于违约责任分析" class="input resize-none h-16"></textarea>
        </div>

        <!-- Progress -->
        <div v-if="generating" class="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <div class="flex items-center gap-2 mb-1">
            <div class="w-3 h-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            <span class="text-xs font-medium text-blue-600 dark:text-blue-400">{{ progressStatus }}</span>
          </div>
          <div v-if="progressText" class="max-h-24 overflow-y-auto text-xs text-[var(--text-secondary)] bg-[var(--surface-primary)] rounded p-2 mt-1 leading-relaxed whitespace-pre-wrap">{{ progressText.slice(-500) }}</div>
        </div>

        <button v-if="!generating" @click="generateDoc" :disabled="!caseName.trim()" class="btn btn-md btn-primary w-full">开始生成</button>
      </div>
    </div>

    <!-- Docs List -->
    <div class="card overflow-hidden">
      <div v-if="loading && documents.length === 0" class="empty-state">
        <div class="skeleton w-8 h-8 rounded-lg mb-2" />
        <div class="empty-state-title text-xs">加载中...</div>
      </div>
      <div v-else-if="documents.length === 0" class="empty-state">
        <div class="empty-state-icon"><span>📝</span></div>
        <div class="empty-state-title">暂无文书</div>
        <div class="empty-state-desc">点击「+ 生成文书」创建</div>
      </div>
      <div v-else>
        <div v-for="doc in documents" :key="doc.uuid" class="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-light)] last:border-0 hover:bg-[var(--surface-hover)] transition-all duration-150 cursor-pointer" @click="router.push(`/documents/${doc.uuid}`)">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-100 to-amber-200 dark:from-amber-900/30 dark:to-amber-800/30 flex items-center justify-center text-sm shrink-0 shadow-sm">📄</div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium truncate">{{ doc.title || doc.case_name }}</span>
              <span v-if="doc.status" class="tag text-[10px]" :class="statusColors[doc.status] || 'tag-zinc'">{{ statusLabels[doc.status] || doc.status }}</span>
            </div>
            <div class="flex items-center gap-2 mt-0.5">
              <span class="tag tag-blue text-[10px]">{{ doc.doc_type || "文书" }}</span>
              <span class="text-[11px] text-[var(--text-tertiary)]">· {{ doc.case_name }}</span>
              <span class="text-[11px] text-[var(--text-tertiary)]">· {{ formatTime(doc.created_at) }}</span>
            </div>
          </div>
          <button @click.stop="deleteDoc(doc.uuid)" class="btn btn-sm btn-ghost text-[var(--text-tertiary)] hover:text-red-500">删除</button>
        </div>

        <!-- Load More -->
        <div v-if="hasMore" class="flex justify-center p-3 border-t border-[var(--border-light)]">
          <button @click="loadMore" :disabled="loading" class="btn btn-sm btn-secondary">{{ loading ? "加载中..." : "加载更多" }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
