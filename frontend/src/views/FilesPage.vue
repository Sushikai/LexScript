<script setup lang="ts">
import { ref, onMounted } from "vue"

const API = "/api/v1"

interface FileEntry { id: number; name: string; size: number; type: string; status: string; chunks: number; created_at: string }
interface Folder { id: number; name: string; root_path: string; case_number: string; description: string }

const files = ref<FileEntry[]>([])
const folders = ref<Folder[]>([])
const loading = ref(false)
const importPath = ref("")
const uploadFile = ref<File | null>(null)
const folderName = ref("")
const folderPath = ref("")
const showImport = ref(false)
const showFolder = ref(false)
const dragOver = ref(false)
const previewFile = ref<FileEntry | null>(null)
const previewContent = ref("")
const previewLoading = ref(false)
const previewTab = ref<"preview" | "content" | "info">("preview")

async function loadFiles() {
  loading.value = true
  try { const r = await fetch(`${API}/files`); const d = await r.json(); files.value = d.data || [] } catch { }
  loading.value = false
}
async function loadFolders() {
  try { const r = await fetch(`${API}/files/folders`); const d = await r.json(); folders.value = d.data || [] } catch { }
}
async function importByPath() {
  if (!importPath.value.trim()) return
  try { await fetch(`${API}/files/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: importPath.value }) }); importPath.value = ""; showImport.value = false; await loadFiles() } catch { }
}
async function handleUpload() {
  if (!uploadFile.value) return
  const form = new FormData()
  form.append("file", uploadFile.value)
  form.append("folder_id", "0")
  try { await fetch(`${API}/files/upload`, { method: "POST", body: form }); uploadFile.value = null; await loadFiles() } catch { }
}
async function parseFile(id: number) {
  try { await fetch(`${API}/files/${id}/parse`, { method: "POST" }); await loadFiles() } catch { }
}
function onDragOver(e: DragEvent) { e.preventDefault(); dragOver.value = true }
function onDragLeave() { dragOver.value = false }
function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) { uploadFile.value = files[0]; handleUpload() }
}
async function deleteFile(id: number, name: string) {
  if (!confirm(`确认删除 "${name}"？`)) return
  try { await fetch(`${API}/files/${id}`, { method: "DELETE" }); await loadFiles() } catch { }
}
async function createFolder() {
  if (!folderName.value || !folderPath.value) return
  try { await fetch(`${API}/files/folders`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: folderName.value, root_path: folderPath.value }) }); folderName.value = ""; folderPath.value = ""; showFolder.value = false; await loadFolders() } catch { }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
  return (bytes / 1024 / 1024).toFixed(1) + " MB"
}
function formatTime(t: string) {
  if (!t) return ""
  const d = new Date(t)
  return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase() || ""
  if (["jpg", "jpeg", "png", "gif", "bmp", "webp"].includes(ext)) return "🖼"
  if (ext === "pdf") return "📕"
  if (["doc", "docx"].includes(ext)) return "📘"
  if (["xls", "xlsx"].includes(ext)) return "📊"
  if (["txt", "md"].includes(ext)) return "📄"
  if (ext === "csv") return "📋"
  return "📁"
}
function isImage(name: string) {
  return ["jpg", "jpeg", "png", "gif", "bmp", "webp"].includes(name.split(".").pop()?.toLowerCase() || "")
}
function isPdf(name: string) {
  return name.toLowerCase().endsWith(".pdf")
}
function isText(name: string) {
  return ["txt", "md", "csv", "json", "xml", "yaml", "yml", "py", "ts", "js", "html", "css"].includes(name.split(".").pop()?.toLowerCase() || "")
}

async function openPreview(f: FileEntry) {
  previewFile.value = f
  previewContent.value = ""
  previewTab.value = isImage(f.name) || isPdf(f.name) ? "preview" : "preview"
  if (!isImage(f.name) && !isPdf(f.name)) {
    previewLoading.value = true
    try {
      const r = await fetch(`${API}/files/${f.id}/content`)
      const d = await r.json()
      if (d.ok) previewContent.value = d.data?.content || "[空文件]"
    } catch { previewContent.value = "[无法加载文件内容]" }
    previewLoading.value = false
  }
}
function closePreview() {
  previewFile.value = null
  previewContent.value = ""
}

onMounted(() => { loadFiles(); loadFolders() })
</script>

<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto animate-fadeIn relative" @dragover="onDragOver" @dragleave="onDragLeave" @drop="onDrop">
    <!-- Drop Zone Overlay -->
    <transition name="fade">
      <div v-if="dragOver" class="absolute inset-0 z-50 bg-[var(--brand-500)]/10 backdrop-blur-sm rounded-2xl border-2 border-dashed border-[var(--brand-400)] flex items-center justify-center pointer-events-none">
        <div class="text-center">
          <div class="w-16 h-16 rounded-2xl bg-[var(--brand-100)] dark:bg-[var(--brand-600)]/20 flex items-center justify-center mx-auto mb-3">
            <svg class="w-8 h-8 text-[var(--brand-600)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
          </div>
          <p class="text-lg font-semibold text-[var(--brand-700)] dark:text-[var(--brand-300)]">释放以上传文件</p>
          <p class="text-sm text-[var(--brand-500)] mt-1">支持 PDF、Word、Excel、图片等格式</p>
        </div>
      </div>
    </transition>
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-lg font-bold">文件管理</h1>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5">PDF / Word / Excel / 图片 OCR 全格式解析</p>
      </div>
      <div class="flex gap-2">
        <button @click="showFolder = !showFolder" class="btn btn-sm btn-secondary">+ 文件夹</button>
        <button @click="showImport = !showImport" class="btn btn-sm btn-secondary">+ 导入</button>
        <label class="btn btn-sm btn-primary cursor-pointer">
          上传
          <input type="file" class="hidden" @change="e => { uploadFile = (e.target as HTMLInputElement).files?.[0] || null; handleUpload() }" />
        </label>
      </div>
    </div>

    <!-- Import Panel -->
    <div v-if="showImport" class="card p-3 mb-4 animate-scaleIn">
      <div class="flex gap-2">
        <input v-model="importPath" type="text" placeholder="输入本地文件/目录路径..." class="input" @keydown.enter="importByPath" />
        <button @click="importByPath" class="btn btn-sm btn-primary">导入</button>
      </div>
    </div>

    <!-- Folder Panel -->
    <div v-if="showFolder" class="card p-3 mb-4 animate-scaleIn">
      <div class="flex gap-2">
        <input v-model="folderName" type="text" placeholder="文件夹名称" class="input" />
        <input v-model="folderPath" type="text" placeholder="路径" class="input" />
        <button @click="createFolder" class="btn btn-sm btn-primary">创建</button>
      </div>
    </div>

    <!-- Folders -->
    <div v-if="folders.length" class="mb-4">
      <h2 class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2">案件文件夹</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div v-for="f in folders" :key="f.id" class="card card-interactive p-3">
          <div class="text-sm font-semibold">{{ f.name }}</div>
          <div v-if="f.case_number" class="text-xs text-[var(--text-tertiary)] mt-0.5">案号: {{ f.case_number }}</div>
          <div class="text-xs text-[var(--text-tertiary)] mt-0.5 truncate">{{ f.root_path }}</div>
        </div>
      </div>
    </div>

    <!-- Files -->
    <div class="card overflow-hidden">
      <div v-if="loading" class="empty-state">
        <div class="skeleton w-8 h-8 rounded-lg mb-2" />
        <div class="empty-state-title text-xs">加载中...</div>
      </div>
      <div v-else-if="files.length === 0" class="empty-state">
        <div class="empty-state-icon"><span>📁</span></div>
        <div class="empty-state-title">暂无文件</div>
        <div class="empty-state-desc">点击上方「导入」或「上传」添加文件</div>
      </div>
      <div v-else>
        <div
          v-for="f in files"
          :key="f.id"
          class="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-light)] last:border-0 hover:bg-[var(--surface-hover)] transition-all duration-150"
        >
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-zinc-100 to-zinc-200 dark:from-zinc-800 dark:to-zinc-700 flex items-center justify-center text-sm shrink-0 shadow-sm">{{ fileIcon(f.name) }}</div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate">{{ f.name }}</div>
            <div class="flex items-center gap-2 mt-0.5">
              <span class="text-[11px] text-[var(--text-tertiary)]">{{ formatSize(f.size) }}</span>
              <span class="status-dot" :class="f.status === 'indexed' ? 'status-dot-green' : f.status ? 'status-dot-amber' : '' " />
              <span class="text-[11px]" :class="f.status === 'indexed' ? 'text-green-500 font-medium' : f.status ? 'text-amber-500' : 'text-[var(--text-tertiary)]'">{{ f.status || "待处理" }}</span>
              <span v-if="f.chunks" class="text-[11px] text-[var(--text-tertiary)]">{{ f.chunks }} 分块</span>
            </div>
          </div>
          <div class="flex gap-1.5">
            <button @click="openPreview(f)" class="btn btn-sm btn-secondary">预览</button>
            <button v-if="f.status !== 'indexed'" @click="parseFile(f.id)" class="btn btn-sm btn-primary">解析</button>
            <button @click="deleteFile(f.id, f.name)" class="btn btn-sm btn-ghost text-[var(--text-tertiary)] hover:text-red-500">删除</button>
          </div>
        </div>
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
            <span class="text-[11px] text-[var(--text-tertiary)]">{{ formatSize(previewFile.size) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <!-- Tab switcher for text files -->
          <div v-if="isText(previewFile.name)" class="flex bg-[var(--surface-secondary)] rounded-lg p-0.5 mr-2">
            <button @click="previewTab = 'preview'" class="px-2.5 py-1 text-[11px] rounded-md transition-all" :class="previewTab === 'preview' ? 'bg-[var(--surface-primary)] shadow-sm font-medium' : 'text-[var(--text-tertiary)]'">预览</button>
            <button @click="previewTab = 'content'" class="px-2.5 py-1 text-[11px] rounded-md transition-all" :class="previewTab === 'content' ? 'bg-[var(--surface-primary)] shadow-sm font-medium' : 'text-[var(--text-tertiary)]'">原文</button>
          </div>
          <a :href="`${API}/files/${previewFile.id}/raw`" target="_blank" class="btn btn-sm btn-secondary" download>下载</a>
          <button @click="closePreview" class="btn btn-sm btn-ghost p-1">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>
      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-4 bg-[var(--surface-secondary)] rounded-b-2xl min-h-[300px]">
        <!-- Image preview -->
        <img v-if="isImage(previewFile.name)" :src="`${API}/files/${previewFile.id}/raw`" class="max-w-full max-h-[70vh] mx-auto rounded-lg shadow-md object-contain" alt="preview" />
        <!-- PDF preview -->
        <iframe v-else-if="isPdf(previewFile.name)" :src="`${API}/files/${previewFile.id}/raw`" class="w-full h-[70vh] rounded-lg" />
        <!-- Text content (preview tab) -->
        <div v-else-if="previewTab === 'preview' && previewContent" class="chat-message text-sm leading-relaxed whitespace-pre-wrap max-w-3xl mx-auto">{{ previewContent }}</div>
        <!-- Raw text -->
        <div v-else-if="previewTab === 'content' && previewContent" class="font-mono text-xs leading-relaxed whitespace-pre-wrap max-w-3xl mx-auto text-[var(--text-secondary)]">{{ previewContent }}</div>
        <!-- Loading -->
        <div v-else-if="previewLoading" class="flex flex-col items-center justify-center py-16">
          <div class="w-8 h-8 border-2 border-[var(--brand-500)] border-t-transparent rounded-full animate-spin mb-3" />
          <span class="text-xs text-[var(--text-tertiary)]">加载中...</span>
        </div>
        <!-- Fallback -->
        <div v-else class="flex flex-col items-center justify-center py-16 text-[var(--text-tertiary)]">
          <span class="text-3xl mb-3">{{ fileIcon(previewFile.name) }}</span>
          <p class="text-sm font-medium">{{ previewFile.name }}</p>
          <p class="text-xs mt-1">{{ formatSize(previewFile.size) }}</p>
          <a :href="`${API}/files/${previewFile.id}/raw`" target="_blank" class="btn btn-primary btn-sm mt-4">下载查看</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: all 0.2s ease-out; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
