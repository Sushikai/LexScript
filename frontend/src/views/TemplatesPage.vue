<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import DOMPurify from "dompurify"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"
const auth = useAuthStore()

interface Template { id: number; name: string; category: string; content: string; variables: string; description: string }

const templates = ref<Template[]>([])
const categories = ref<string[]>([])
const activeCategory = ref("")
const showEditor = ref(false)
const editTemplate = ref<Partial<Template>>({ name: "", category: "", content: "", description: "", variables: "[]" })
const previewHtml = ref("")
const saving = ref(false)

async function loadTemplates() {
  try { const r = await fetch(`${API}/templates`, { headers: auth.setTokenHeader() }); const d = await r.json(); templates.value = d.data || [] } catch { }
}
async function loadBuiltins() {
  try { const r = await fetch(`${API}/templates/builtins`, { headers: auth.setTokenHeader() }); const d = await r.json(); if (d.ok) categories.value = d.data || [] } catch { }
}
function editTemplateFn(t: Template) {
  editTemplate.value = { ...t }
  showEditor.value = true
}
function newTemplate() {
  editTemplate.value = { name: "", category: "起诉状", content: "", description: "", variables: "[]" }
  showEditor.value = true
}
async function saveTemplate() {
  saving.value = true
  const isNew = !editTemplate.value.id
  try {
    if (isNew) {
      await fetch(`${API}/templates`, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify(editTemplate.value) })
    } else {
      await fetch(`${API}/templates/${editTemplate.value.id}`, { method: "PATCH", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify(editTemplate.value) })
    }
    showEditor.value = false; await loadTemplates()
  } catch { }
  saving.value = false
}
async function deleteTemplate(id: number, name: string) {
  if (!confirm(`确认删除模板 "${name}"？`)) return
  try { await fetch(`${API}/templates/${id}`, { method: "DELETE", headers: auth.setTokenHeader() }); await loadTemplates() } catch { }
}
async function previewTemplate(t: Template) {
  try {
    const r = await fetch(`${API}/templates/${t.id}/preview`, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify({ variables: {} }) })
    const d = await r.json()
    if (d.ok) previewHtml.value = d.data?.content || ""
  } catch { }
}

const filteredTemplates = computed(() => {
  if (!activeCategory.value) return templates.value
  return templates.value.filter(t => t.category === activeCategory.value)
})

onMounted(() => { loadTemplates(); loadBuiltins() })
</script>

<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-lg font-bold">模板库</h1>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5">起诉状 / 答辩状 / 代理词 / 合同 / 律师函</p>
      </div>
      <button @click="newTemplate" class="btn btn-sm btn-primary">+ 新建模板</button>
    </div>

    <!-- Category Filter -->
    <div class="flex gap-1.5 mb-4 overflow-x-auto pb-1 scrollbar-none">
      <button
        @click="activeCategory = ''"
        class="btn btn-sm"
        :class="!activeCategory ? 'btn-primary' : 'btn-secondary'"
      >全部</button>
      <button
        v-for="cat in categories"
        :key="cat"
        @click="activeCategory = cat"
        class="btn btn-sm"
        :class="activeCategory === cat ? 'btn-primary' : 'btn-secondary'"
      >{{ cat }}</button>
    </div>

    <!-- Template Grid -->
    <div v-if="filteredTemplates.length === 0" class="empty-state">
      <div class="empty-state-icon"><span>📋</span></div>
      <div class="empty-state-title">暂无模板</div>
      <div class="empty-state-desc">点击「+ 新建模板」添加</div>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div
        v-for="t in filteredTemplates"
        :key="t.id"
        class="card card-interactive p-4"
      >
        <div class="text-sm font-semibold mb-1">{{ t.name }}</div>
        <div class="tag tag-blue text-[10px] mb-2">{{ t.category }}</div>
        <p v-if="t.description" class="text-xs text-[var(--text-tertiary)] mb-3 truncate-2">{{ t.description }}</p>
        <p v-else class="text-xs text-[var(--text-tertiary)] mb-3 italic">无描述</p>
        <div class="flex gap-1.5">
          <button @click="editTemplateFn(t)" class="btn btn-sm btn-secondary flex-1">编辑</button>
          <button @click="previewTemplate(t)" class="btn btn-sm btn-secondary flex-1">预览</button>
          <button @click="deleteTemplate(t.id, t.name)" class="btn btn-sm btn-ghost text-[var(--text-tertiary)] hover:text-red-500">删除</button>
        </div>
      </div>
    </div>

    <!-- Editor Modal -->
    <div v-if="showEditor" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="showEditor = false">
      <div class="w-full max-w-2xl bg-[var(--surface-primary)] rounded-2xl shadow-xl border border-[var(--border-light)] p-5 max-h-[85vh] overflow-y-auto animate-scaleIn">
        <h3 class="text-sm font-semibold mb-4">{{ editTemplate.id ? "编辑模板" : "新建模板" }}</h3>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-[var(--text-tertiary)] mb-1 block">名称</label>
            <input v-model="editTemplate.name" type="text" class="input" />
          </div>
          <div>
            <label class="text-xs text-[var(--text-tertiary)] mb-1 block">分类</label>
            <select v-model="editTemplate.category" class="select">
              <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
            </select>
          </div>
          <div>
            <label class="text-xs text-[var(--text-tertiary)] mb-1 block">描述</label>
            <input v-model="editTemplate.description" type="text" class="input" />
          </div>
          <div>
            <label class="text-xs text-[var(--text-tertiary)] mb-1 block">模板内容 (Jinja2)</label>
            <textarea v-model="editTemplate.content" rows="10" class="input font-mono resize-none"></textarea>
          </div>
        </div>
        <div class="flex gap-2 mt-4">
          <button @click="showEditor = false" class="btn btn-sm btn-secondary flex-1">取消</button>
          <button @click="saveTemplate" :disabled="saving || !editTemplate.name" class="btn btn-sm btn-primary flex-1">{{ saving ? "保存中..." : "保存" }}</button>
        </div>
      </div>
    </div>

    <!-- Preview Modal -->
    <div v-if="previewHtml" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="previewHtml = ''">
      <div class="w-full max-w-2xl bg-[var(--surface-primary)] rounded-2xl shadow-xl border border-[var(--border-light)] p-5 max-h-[80vh] overflow-y-auto animate-scaleIn">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold">预览</h3>
          <button @click="previewHtml = ''" class="btn btn-sm btn-ghost p-1">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div class="chat-message text-sm leading-relaxed" v-html="DOMPurify.sanitize(previewHtml)" />
      </div>
    </div>
  </div>
</template>
