<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useToast } from "@/composables/useToast"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"
const auth = useAuthStore()
const { show } = useToast()

interface Statute { code: string; name: string; category: string; content: string; source?: string; score?: number }

const query = ref("")
const results = ref<Statute[]>([])
const categories = ref<string[]>([])
const activeCategory = ref("")
const searching = ref(false)
const selected = ref<Statute | null>(null)
const searchMode = ref<"keyword" | "semantic" | "hybrid">("keyword")
const showInsert = ref(false)
const showBulk = ref(false)

// Insert form
const insertCode = ref("")
const insertName = ref("")
const insertCategory = ref("民法典")
const insertContent = ref("")
const insertSource = ref("")

// Bulk import
const bulkPath = ref("")
const importing = ref(false)
const indexing = ref(false)
const syncing = ref(false)
const vectorStats = ref<{ indexed: number; total_in_db: number } | null>(null)
const syncResult = ref<string | null>(null)
const totalCount = ref(0)

async function loadCategories() {
  try { const r = await fetch(`${API}/statutes/categories`, { headers: auth.setTokenHeader() }); const d = await r.json(); categories.value = d.data || [] } catch { }
}
async function search() {
  if (!query.value.trim()) return
  searching.value = true
  try {
    let url = `${API}/statutes/search`
    const body: any = { keyword: query.value, category: activeCategory.value || undefined, limit: 30 }
    if (searchMode.value === "semantic") {
      url = `${API}/statutes/semantic-search`
      body.query = query.value
      delete body.keyword
    } else if (searchMode.value === "hybrid") {
      url = `${API}/statutes/hybrid-search`
    }
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify(body) })
    const d = await r.json()
    results.value = d.data || []
  } catch { show("检索失败", "error") }
  searching.value = false
}

async function insertStatute() {
  if (!insertCode.value || !insertName.value || !insertContent.value) return
  try {
    await fetch(`${API}/statutes/upsert`, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify({ code: insertCode.value, name: insertName.value, category: insertCategory.value, content: insertContent.value, source: insertSource.value || undefined }) })
    showInsert.value = false; insertCode.value = ""; insertName.value = ""; insertContent.value = ""; insertSource.value = ""
    show("法条已保存", "success")
  } catch { show("保存失败", "error") }
}

async function bulkImport() {
  if (!bulkPath.value.trim()) return
  importing.value = true
  try {
    const r = await fetch(`${API}/statutes/bulk-import`, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify({ directory: bulkPath.value || null }) })
    const d = await r.json()
    if (d.ok) show(`批量导入完成: ${d.data.imported} 条`, "success")
    else show(d.message || "导入失败", "error")
  } catch { show("导入失败", "error") }
  importing.value = false
}

async function indexVector() {
  indexing.value = true
  try {
    const r = await fetch(`${API}/statutes/index-vector`, { method: "POST", headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) { vectorStats.value = d.data; show(`向量索引完成: ${d.data.indexed} 条`, "success") }
  } catch { show("向量索引失败", "error") }
  indexing.value = false
}

async function syncFromApi() {
  syncing.value = true; syncResult.value = null
  try {
    const r = await fetch(`${API}/statutes/sync`, { method: "POST", headers: auth.setTokenHeader() })
    const d = await r.json()
    if (d.ok) {
      const data = d.data
      if (data.synced > 0) syncResult.value = `同步完成: ${data.synced} 条更新, 共 ${data.total_after} 条`
      else if (data.error) syncResult.value = `同步暂不可用: ${data.error}`
      else syncResult.value = data.message || "同步完成, 无新数据"
      if (data.synced > 0) loadVectorStats()
    } else syncResult.value = d.message || "同步失败"
  } catch { syncResult.value = "网络错误, 同步失败" }
  syncing.value = false
}

async function loadVectorStats() {
  try {
    const r = await fetch(`${API}/statutes/search`, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify({ keyword: "", limit: 1 }) })
    const d = await r.json(); totalCount.value = d.data?.length || 0
    vectorStats.value = await fetch(`${API}/statutes/index-vector`, { method: "POST", headers: auth.setTokenHeader() }).then(r => r.json()).then(d => d.data || null).catch(() => null)
  } catch { }
}

async function loadCount() {
  try {
    const r = await fetch(`${API}/statutes/search`, { method: "POST", headers: { "Content-Type": "application/json", ...auth.setTokenHeader() }, body: JSON.stringify({ keyword: "", limit: 1 }) })
    const d = await r.json()
    if (d.data) totalCount.value = d.data.length
  } catch { }
}

function selectStatute(s: Statute) { selected.value = s }

/**
 * 解析文本中引用的法条，生成可点击的链接。
 * 匹配模式: "第XX条"、"XXX法第XX条" 等
 */
function extractStatuteRefs(text: string): { ref: string; index: number; length: number }[] {
  const refs: { ref: string; index: number; length: number }[] = []
  const pattern = /((?:《[^》]+》)?(?:第[零一二三四五六七八九十百千\d]+条[之\d]*(?:第[一二三四五六七八九十\d]+款)?(?:第[一二三四五六七八九十\d]+项)?))/g
  let m
  while ((m = pattern.exec(text)) !== null) {
    refs.push({ ref: m[1], index: m.index, length: m[1].length })
  }
  return refs
}

function highlightKeyword(text: string) {
  if (!query.value.trim() || searchMode.value === "semantic") return text
  const kw = query.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.replace(new RegExp(`(${kw})`, 'gi'), '<mark class="bg-amber-200 dark:bg-amber-800/40 text-inherit rounded px-0.5">$1</mark>')
}

onMounted(() => { loadCategories(); loadCount() })
</script>

<template>
  <div class="p-4 md:p-6 max-w-5xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div>
        <h1 class="text-lg font-bold">法条检索</h1>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5 flex items-center gap-2">
          <span>法律法规 · 司法解释 · 语义搜索</span>
          <span v-if="vectorStats" class="tag tag-green text-[10px]">向量索引 {{ vectorStats.indexed }} 条</span>
        </p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <button @click="syncFromApi" :disabled="syncing" class="btn btn-sm btn-secondary">
          <svg v-if="!syncing" class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          <span v-else class="w-3 h-3 border-2 border-[var(--text-tertiary)] border-t-transparent rounded-full animate-spin inline-block mr-1" />
          {{ syncing ? '同步中...' : 'API 同步' }}
        </button>
        <button @click="indexVector" :disabled="indexing" class="btn btn-sm btn-secondary">
          {{ indexing ? '索引中...' : '向量索引' }}
        </button>
        <button @click="showBulk = !showBulk" class="btn btn-sm btn-secondary">+ 批量导入</button>
        <button @click="showInsert = !showInsert" class="btn btn-sm btn-primary">+ 录入法条</button>
      </div>
    </div>

    <!-- Sync Result Toast -->
    <div v-if="syncResult" class="mb-3 px-3 py-2 rounded-lg text-xs flex items-center gap-2" :class="syncResult.includes('失败') || syncResult.includes('不可用') ? 'bg-red-900/30 text-red-300' : 'bg-green-900/30 text-green-300'">
      <span>{{ syncResult }}</span>
      <button @click="syncResult = null" class="ml-auto text-[var(--text-tertiary)] hover:text-white">&times;</button>
    </div>

    <!-- Insert Panel -->
    <div v-if="showInsert" class="card p-4 mb-4 animate-scaleIn">
      <h3 class="text-sm font-semibold mb-3">录入法条</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <div>
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">法条编号</label>
          <input v-model="insertCode" type="text" class="input" placeholder="如: 民法典_第1条" />
        </div>
        <div>
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">法条名称</label>
          <input v-model="insertName" type="text" class="input" placeholder="如: 民法典 第1条" />
        </div>
        <div>
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">分类</label>
          <select v-model="insertCategory" class="select">
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-[var(--text-tertiary)] mb-1 block">来源</label>
          <input v-model="insertSource" type="text" class="input" placeholder="可选" />
        </div>
      </div>
      <div class="mb-3">
        <label class="text-xs text-[var(--text-tertiary)] mb-1 block">内容</label>
        <textarea v-model="insertContent" rows="4" class="input resize-none" placeholder="法条全文..."></textarea>
      </div>
      <div class="flex gap-2">
        <button @click="insertStatute" class="btn btn-sm btn-primary">保存</button>
        <button @click="showInsert = false" class="btn btn-sm btn-ghost">取消</button>
      </div>
    </div>

    <!-- Bulk Import Panel -->
    <div v-if="showBulk" class="card p-4 mb-4 animate-scaleIn">
      <h3 class="text-sm font-semibold mb-3">批量导入法条</h3>
      <p class="text-xs text-[var(--text-tertiary)] mb-3">从 KB 目录或指定路径的 .txt/.md 文件中自动解析法条。支持 <code>【法规名 第X条】内容</code> 格式。</p>
      <div class="flex gap-2">
        <input v-model="bulkPath" type="text" class="input" placeholder="留空扫描 KB 目录，或输入文件/目录路径" @keydown.enter="bulkImport" />
        <button @click="bulkImport" :disabled="importing" class="btn btn-sm btn-primary">{{ importing ? '导入中...' : '导入' }}</button>
      </div>
    </div>

    <!-- Search Bar -->
    <div class="card p-3 mb-4">
      <div class="flex gap-2 flex-wrap">
        <div class="relative flex-1 min-w-[200px]">
          <svg class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
          <input v-model="query" type="text" :placeholder="searchMode === 'semantic' ? '输入法律问题，AI 语义搜索法条...' : '搜索法条关键词...'" class="input pl-9" @keydown.enter="search" />
        </div>
        <select v-model="activeCategory" class="select w-auto text-xs">
          <option value="">全部分类</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <div class="flex rounded-lg bg-[var(--surface-tertiary)] p-0.5 gap-0.5">
          <button @click="searchMode = 'keyword'" class="btn btn-sm px-2.5 text-[11px]" :class="searchMode === 'keyword' ? 'btn-primary' : 'btn-ghost'">关键词</button>
          <button @click="searchMode = 'semantic'" class="btn btn-sm px-2.5 text-[11px]" :class="searchMode === 'semantic' ? 'btn-primary' : 'btn-ghost'">语义</button>
          <button @click="searchMode = 'hybrid'" class="btn btn-sm px-2.5 text-[11px]" :class="searchMode === 'hybrid' ? 'btn-primary' : 'btn-ghost'">混合</button>
        </div>
        <button @click="search" :disabled="searching" class="btn btn-sm btn-primary">
          <svg v-if="!searching" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
          <span v-else class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          <span>{{ searching ? "" : "检索" }}</span>
        </button>
      </div>
    </div>

    <!-- Results + Detail -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
      <!-- Results List -->
      <div class="md:col-span-3 space-y-2">
        <div v-if="results.length === 0" class="empty-state py-8">
          <div class="empty-state-icon"><span>⚖</span></div>
          <div class="empty-state-title">{{ searchMode === 'semantic' ? '语义搜索' : '搜索法条' }}</div>
          <div class="empty-state-desc">{{ searchMode === 'semantic' ? '输入法律问题描述进行语义匹配' : searchMode === 'hybrid' ? '混合搜索: 语义 + 关键词' : '输入关键词检索法律法规' }}</div>
        </div>
        <div v-for="s in results" :key="s.code" class="card card-interactive p-3 w-full text-left" @click="selectStatute(s)">
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold truncate" v-html="highlightKeyword(s.name)" />
              <div class="flex items-center gap-2 mt-0.5">
                <span class="tag tag-blue text-[10px]">{{ s.code }}</span>
                <span class="tag tag-zinc text-[10px]">{{ s.category }}</span>
                <span v-if="s.score" class="text-[10px] text-[var(--text-tertiary)] font-mono">{{ (s.score * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <svg class="w-4 h-4 text-[var(--text-quaternary)] shrink-0 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
          </div>
          <div class="text-xs text-[var(--text-secondary)] mt-1.5 truncate-2 leading-relaxed" v-html="highlightKeyword(s.content)" />
        </div>
      </div>

      <!-- Detail Sidebar -->
      <div class="md:col-span-2">
        <div v-if="selected" class="card p-4 sticky top-4 animate-scaleIn">
          <div class="flex items-start justify-between mb-1">
            <h3 class="text-sm font-semibold">{{ selected.name }}</h3>
            <button v-if="selected.content" @click="navigator.clipboard.writeText(selected.content)" class="btn btn-ghost btn-sm p-1 shrink-0 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]" title="复制">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75" /></svg>
            </button>
          </div>
          <div class="flex items-center gap-2 mb-2 flex-wrap">
            <span class="tag tag-blue text-[10px]">{{ selected.code }}</span>
            <span class="text-[11px] text-[var(--text-tertiary)]">{{ selected.category }}</span>
            <span class="text-[10px] text-[var(--text-tertiary)] ml-auto">来源: {{ selected.source || '内置' }}</span>
          </div>
          <!-- 引用法条检测 -->
          <div v-if="selected.content" class="mb-2">
            <div v-if="extractStatuteRefs(selected.content).length > 0" class="text-[10px] text-[var(--text-tertiary)] mb-1">引用法条:</div>
            <div class="flex flex-wrap gap-1">
              <span v-for="(ref, ri) in extractStatuteRefs(selected.content).slice(0, 8)" :key="ri"
                    class="px-1.5 py-0.5 bg-[var(--surface-tertiary)] rounded text-[10px] font-mono text-[var(--accent)] cursor-pointer hover:bg-amber-900/30"
                    @click.stop="query = ref.ref; search()">
                {{ ref.ref }}
              </span>
              <span v-if="extractStatuteRefs(selected.content).length > 8" class="text-[10px] text-[var(--text-tertiary)]">
                +{{ extractStatuteRefs(selected.content).length - 8 }}
              </span>
            </div>
          </div>
          <div class="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap max-h-[50vh] overflow-y-auto statute-content">{{ selected.content }}</div>
        </div>
        <div v-else class="empty-state">
          <div class="empty-state-icon"><span>📖</span></div>
          <div class="empty-state-title">选择法条</div>
          <div class="empty-state-desc">点击左侧结果查看详情</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.statute-content {
  scroll-behavior: smooth;
}
</style>
