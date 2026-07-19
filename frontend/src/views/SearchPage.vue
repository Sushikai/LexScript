<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"
const router = useRouter()
const auth = useAuthStore()

const query = ref("")
const mode = ref<"hybrid" | "semantic" | "keyword">("hybrid")
const results = ref<any[]>([])
const searching = ref(false)
const hasSearched = ref(false)

// Preview modal state
const previewFile = ref<{ id: number; name: string } | null>(null)
const previewContent = ref("")
const previewLoading = ref(false)
const previewMime = ref("")

function headers() {
  return { "Content-Type": "application/json", ...auth.setTokenHeader() }
}

async function doSearch() {
  if (!query.value.trim()) return
  searching.value = true
  hasSearched.value = true
  try {
    const r = await fetch(`${API}/search`, { method: "POST", headers: headers(), body: JSON.stringify({ query: query.value, mode: mode.value, top_k: 20 }) })
    if (r.status === 401) { auth.logout(); router.push("/login"); return }
    const d = await r.json()
    results.value = d.data || []
  } catch { results.value = [] }
  searching.value = false
}

async function searchByStatute() {
  if (!query.value.trim()) return
  searching.value = true; hasSearched.value = true
  try {
    const r = await fetch(`${API}/search/by-statute`, { method: "POST", headers: headers(), body: JSON.stringify({ query: query.value }) })
    const d = await r.json()
    results.value = (d.data || []).map((r: any) => ({ ...r, _type: "statute_ref" }))
  } catch { results.value = [] }
  searching.value = false
}

function sendToChat(r: any) {
  const text = r.content || r.document || r.text || ""
  localStorage.setItem("lex_search_to_chat", JSON.stringify({ text, title: r.title || r.name || r._source_name || "" }))
  router.push("/chat")
}

function generateDoc(r: any) {
  const text = r.content || r.document || r.text || ""
  const title = r.title || r.name || r._source_name || ""
  localStorage.setItem("lex_search_to_doc", JSON.stringify({ text, title }))
  router.push("/documents")
}

// ── Preview ──────────────────────────────────
function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase() || ""
  if (["jpg", "jpeg", "png", "gif", "bmp", "webp"].includes(ext)) return "🖼"
  if (ext === "pdf") return "📕"
  if (["doc", "docx"].includes(ext)) return "📘"
  if (["xls", "xlsx"].includes(ext)) return "📊"
  if (["txt", "md"].includes(ext)) return "📄"
  return "📁"
}

function isImage(name: string) {
  return ["jpg", "jpeg", "png", "gif", "bmp", "webp"].includes(name.split(".").pop()?.toLowerCase() || "")
}
function isPdf(name: string) { return name.toLowerCase().endsWith(".pdf") }

async function openPreview(r: any) {
  const fid = r.file_id
  if (!fid) return
  previewFile.value = { id: fid, name: r.file_name || r._source_name || `文件 ${fid}` }
  previewContent.value = ""
  previewLoading.value = true
  try {
    const res = await fetch(`${API}/files/${fid}/content`, { headers: auth.setTokenHeader() })
    if (!res.ok) { previewContent.value = "[无法加载文件内容]"; return }
    const d = await res.json()
    if (d.ok) {
      previewContent.value = d.data?.content || "[空文件]"
      previewMime.value = d.data?.mime || ""
    }
  } catch { previewContent.value = "[无法加载文件内容]" }
  previewLoading.value = false
}

function closePreview() {
  previewFile.value = null
  previewContent.value = ""
}

function resultText(r: any): string {
  return r.content || r.document || r.text || ""
}

const modes = [
  { value: "hybrid" as const, label: "混合检索", desc: "语义 + 关键词" },
  { value: "semantic" as const, label: "语义检索", desc: "向量相似度" },
  { value: "keyword" as const, label: "关键词检索", desc: "BM25" },
]
</script>

<template>
  <div class="p-4 md:p-6 max-w-4xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="mb-5">
      <h1 class="text-lg font-bold">全文检索</h1>
      <p class="text-xs text-[var(--text-secondary)] mt-0.5">语义 / 关键词 / 混合检索 · 按法条反查文书</p>
    </div>

    <!-- Search Input -->
    <div class="card p-4 mb-4">
      <div class="flex gap-2">
        <div class="relative flex-1">
          <svg class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
          <input v-model="query" type="text" placeholder="输入检索关键词..." class="input pl-9" @keydown.enter="doSearch" />
        </div>
        <button @click="doSearch" :disabled="searching" class="btn btn-sm btn-primary">{{ searching ? "检索中..." : "检索" }}</button>
        <button @click="searchByStatute" :disabled="searching" class="btn btn-sm btn-secondary whitespace-nowrap">按法条反查</button>
      </div>

      <!-- Mode selector -->
      <div class="flex gap-1.5 mt-3">
        <button
          v-for="m in modes"
          :key="m.value"
          @click="mode = m.value"
          class="btn btn-sm transition-all duration-150"
          :class="mode === m.value ? 'btn-primary' : 'btn-ghost text-[var(--text-tertiary)]'"
        >
          {{ m.label }}
          <span class="opacity-60">· {{ m.desc }}</span>
        </button>
      </div>
    </div>

    <!-- Results -->
    <div v-if="hasSearched" class="space-y-2">
      <div class="text-xs text-[var(--text-tertiary)] mb-2">共 <strong class="text-[var(--text-secondary)]">{{ results.length }}</strong> 条结果</div>
      <div
        v-for="(r, i) in results"
        :key="i"
        class="card card-interactive p-3"
      >
        <div class="flex items-center gap-2">
          <div class="text-sm font-semibold flex-1 min-w-0 truncate">{{ r.title || r.name || `结果 ${i + 1}` }}</div>
          <!-- Source type badge -->
          <span v-if="r._source_type === 'file'" class="tag tag-blue text-[10px] shrink-0">文件</span>
          <span v-else-if="r._source_type === 'document'" class="tag tag-purple text-[10px] shrink-0">文书</span>
          <span v-else-if="r._source_type === 'chunk'" class="tag tag-gray text-[10px] shrink-0">段落</span>
          <span v-if="r._type === 'statute_ref'" class="tag tag-amber text-[10px] shrink-0">法条</span>
          <span v-if="r.doc_type" class="tag tag-green text-[10px] shrink-0">{{ r.doc_type }}</span>
        </div>
        <div v-if="r._source_name" class="text-[11px] text-[var(--text-tertiary)] mt-0.5 flex items-center gap-1">
          <svg class="w-3 h-3 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
          {{ r._source_name }}
        </div>
        <div class="flex items-center gap-2 mt-0.5">
          <span v-if="r.score != null" class="text-[11px] text-[var(--text-tertiary)]">得分: {{ Number(r.score).toFixed(3) }}</span>
          <span v-if="r.file_id" class="text-[11px] text-[var(--text-tertiary)]">#{{ r.file_id }}</span>
        </div>
        <div class="text-xs text-[var(--text-secondary)] mt-1.5 truncate-2 leading-relaxed">{{ resultText(r) }}</div>
        <div class="flex gap-1.5 mt-2">
          <button v-if="r.file_id" @click="openPreview(r)" class="btn btn-sm btn-secondary text-[11px]">
            <svg class="w-3 h-3 inline mr-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            预览
          </button>
          <button @click="sendToChat(r)" class="btn btn-sm btn-secondary text-[11px]">发送到 AI 对话</button>
          <button @click="generateDoc(r)" class="btn btn-sm btn-secondary text-[11px]">生成文书</button>
        </div>
      </div>
      <div v-if="results.length === 0" class="empty-state !py-12">
        <div class="empty-state-icon"><span>🔍</span></div>
        <div class="empty-state-title">无匹配结果</div>
        <div class="empty-state-desc">尝试更换检索词或切换检索模式</div>
      </div>
    </div>
  </div>

  <!-- Preview Modal -->
  <div v-if="previewFile" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-2 md:p-4" @click.self="closePreview">
    <div class="w-full max-w-4xl bg-[var(--surface-primary)] rounded-2xl shadow-xl border border-[var(--border-light)] flex flex-col max-h-[90vh] animate-scaleIn">
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--border-light)] shrink-0">
        <div class="flex items-center gap-2 min-w-0">
          <span class="text-lg">{{ fileIcon(previewFile.name) }}</span>
          <div class="min-w-0">
            <h3 class="text-sm font-semibold truncate">{{ previewFile.name }}</h3>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <a :href="`${API}/files/${previewFile.id}/raw`" target="_blank" class="btn btn-sm btn-secondary text-[11px]" download>下载原始文件</a>
          <button @click="closePreview" class="btn btn-sm btn-ghost p-1">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>
      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-4 bg-[var(--surface-secondary)] rounded-b-2xl min-h-[300px]">
        <!-- Image -->
        <img v-if="isImage(previewFile.name)" :src="`${API}/files/${previewFile.id}/raw`" class="max-w-full max-h-[70vh] mx-auto rounded-lg shadow-md object-contain" alt="preview" />
        <!-- PDF -->
        <iframe v-else-if="isPdf(previewFile.name)" :src="`${API}/files/${previewFile.id}/raw`" class="w-full h-[70vh] rounded-lg" />
        <!-- Text content -->
        <div v-else-if="previewContent && !previewLoading" class="chat-message text-sm leading-relaxed whitespace-pre-wrap max-w-3xl mx-auto">{{ previewContent }}</div>
        <!-- Loading -->
        <div v-else-if="previewLoading" class="flex flex-col items-center justify-center py-16">
          <div class="w-8 h-8 border-2 border-[var(--brand-500)] border-t-transparent rounded-full animate-spin mb-3" />
          <span class="text-xs text-[var(--text-tertiary)]">加载中...</span>
        </div>
        <!-- Fallback -->
        <div v-else class="flex flex-col items-center justify-center py-16 text-[var(--text-tertiary)]">
          <span class="text-3xl mb-3">{{ fileIcon(previewFile.name) }}</span>
          <p class="text-sm font-medium">{{ previewFile.name }}</p>
          <a :href="`${API}/files/${previewFile.id}/raw`" target="_blank" class="btn btn-primary btn-sm mt-4">下载查看</a>
        </div>
      </div>
    </div>
  </div>
</template>
