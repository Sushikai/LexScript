<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { marked } from "marked"
import DOMPurify from "dompurify"

const API = "/api/v1"
const route = useRoute()
const router = useRouter()

const doc = ref<any>(null)
const loading = ref(true)

async function loadDoc() {
  loading.value = true
  try {
    const r = await fetch(`${API}/documents/${route.params.uuid}`)
    const d = await r.json()
    if (d.ok) doc.value = d.data
    else router.push("/documents")
  } catch { router.push("/documents") }
  loading.value = false
}
async function exportDoc(fmt: string) {
  window.open(`${API}/documents/${route.params.uuid}/export?fmt=${fmt}`, "_blank")
}
async function regenerate() {
  if (!confirm("确认重新生成？当前内容将被覆盖")) return
  try {
    const r = await fetch(`${API}/documents/${route.params.uuid}/regenerate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_name: doc.value?.case_name || "", doc_type: doc.value?.doc_type || "起诉状" }) })
    const d = await r.json()
    if (d.ok) await loadDoc()
  } catch { }
}

function renderMarkdown(text: string) {
  if (!text) return ""
  try {
    const html = marked.parse(text, { breaks: true }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return DOMPurify.sanitize(text)
  }
}

onMounted(loadDoc)
</script>

<template>
  <div class="p-4 md:p-6 max-w-4xl mx-auto animate-fadeIn">
    <!-- Loading -->
    <div v-if="loading" class="empty-state">
      <div class="skeleton w-24 h-4 rounded mb-2" />
      <div class="skeleton w-32 h-3 rounded" />
    </div>

    <div v-else-if="doc" class="space-y-4">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <button @click="router.push('/documents')" class="text-xs text-[var(--brand-600)] dark:text-[var(--brand-400)] hover:underline mb-2 inline-flex items-center gap-1 transition-colors">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" /></svg>
            返回文书列表
          </button>
          <h1 class="text-lg font-bold">{{ doc.title || doc.case_name }}</h1>
          <div class="flex items-center gap-2 mt-1.5 flex-wrap">
            <span class="tag tag-blue">{{ doc.doc_type }}</span>
            <span class="text-xs text-[var(--text-tertiary)]">· {{ doc.case_name }}</span>
            <span v-if="doc.status" class="tag" :class="doc.status === 'completed' ? 'tag-green' : 'tag-amber'">{{ doc.status }}</span>
          </div>
        </div>
        <div class="flex gap-2 flex-wrap">
          <button @click="exportDoc('md')" class="btn btn-sm btn-secondary">MD</button>
          <button @click="exportDoc('docx')" class="btn btn-sm btn-secondary">DOCX</button>
          <button @click="exportDoc('pdf')" class="btn btn-sm btn-danger">PDF</button>
          <button @click="regenerate" class="btn btn-sm btn-primary">重新生成</button>
        </div>
      </div>

      <!-- Content -->
      <div class="card card-elevated p-4 md:p-6">
        <div class="chat-message text-sm leading-relaxed" v-html="renderMarkdown(doc.content)" />
      </div>
    </div>
  </div>
</template>
