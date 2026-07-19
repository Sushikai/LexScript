<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useToast } from "@/composables/useToast"
import { useAuthStore } from "@/stores/auth"

const API = "/api/v1"
const auth = useAuthStore()
const { show: showToast } = useToast()

interface ProviderInfo {
  name: string
  base_url: string
  models: string[]
  default_model?: string
}

const config = ref<Record<string, any>>({})
const providers = ref<Record<string, ProviderInfo>>({})
const loading = ref(true)
const saving = ref<Record<string, boolean>>({})
const testResult = ref("")

const activeProvider = ref("")
const keyInputs = ref<Record<string, string>>({})
const keyHints = ref<Record<string, string>>({})

async function loadConfig() {
  loading.value = true
  try {
    const [cR, pR] = await Promise.all([
      fetch(`${API}/config`, { headers: auth.setTokenHeader() }),
      fetch(`${API}/config/providers`, { headers: auth.setTokenHeader() }),
    ])
    const c = await cR.json()
    const p = await pR.json()
    if (c.ok) {
      config.value = c.data
      activeProvider.value = c.data.llm_provider || ""
      if (c.data.llm_api_key) {
        keyHints.value[c.data.llm_provider || ""] = "已配置"
      }
    }
    if (p.ok) providers.value = p.data || {}
  } catch { }
  loading.value = false
}

async function setupProvider(key: string) {
  const p = providers.value[key]
  if (!p) return

  let apiKey = keyInputs.value[key]?.trim() || ""
  if (!apiKey && key === activeProvider.value && config.value.llm_api_key) {
    apiKey = config.value.llm_api_key
  }
  if (!apiKey) {
    testResult.value = `请输入 ${p.name} 的 API Key`
    return
  }

  saving.value[key] = true
  testResult.value = ""
  try {
    const saveR = await fetch(`${API}/config`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...auth.setTokenHeader() },
      body: JSON.stringify({
        provider: key,
        api_key: apiKey,
        base_url: p.base_url || "",
        model: p.default_model || (p.models?.[0]) || "",
      }),
    })
    const saveD = await saveR.json()
    if (!saveD.ok) throw new Error(saveD.message || "保存失败")

    await loadConfig()

    const testR = await fetch(`${API}/config/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...auth.setTokenHeader() },
      body: JSON.stringify({
        api_key: apiKey,
        base_url: p.base_url || "",
        model: p.default_model || (p.models?.[0]) || "",
      }),
    })
    const testD = await testR.json()
    if (testD.ok) {
      const x = testD.data
      testResult.value = `✅ ${p.name} 配置成功 · 延迟 ${x.latency_ms}ms · 模型 ${x.model}`
      keyInputs.value[key] = ""
      keyHints.value[key] = "已配置 ✓"
      showToast(`${p.name} 配置成功`, "success")
    } else {
      testResult.value = `❌ ${p.name} 连接失败: ${testD.message || testD.code || "未知错误"}`
      showToast(`${p.name} 连接失败`, "error")
    }
  } catch (e: any) {
    testResult.value = `❌ 错误: ${e.message}`
    showToast(`配置错误: ${e.message}`, "error")
  }
  saving.value[key] = false
}

const PROVIDER_ICONS: Record<string, string> = {
  minimax: "🌀", deepseek: "🔮", moonshot: "🌙", qwen: "🌊", zhipu: "🧠",
  baichuan: "🌊", yi: "☯️", spark: "🔥", doubao: "🫘", hunyuan: "☁️",
  siliconflow: "💎", openai: "🌐", claude: "🤖",
}

function maskedKey(key: string): string {
  if (!key || key.length < 8) return key
  return key.slice(0, 4) + "••••" + key.slice(-4)
}

onMounted(loadConfig)
</script>

<template>
  <div class="p-4 md:p-6 max-w-4xl mx-auto animate-fadeIn">
    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <div class="flex items-center gap-2.5">
          <h1 class="text-lg font-bold">系统配置</h1>
          <span v-if="activeProvider" class="tag tag-green">{{ activeProvider }}</span>
        </div>
        <p class="text-xs text-[var(--text-secondary)] mt-0.5">配置 AI 模型服务商 · API Key 仅保存在本机</p>
      </div>
    </div>

    <div v-if="loading" class="empty-state">
      <div class="empty-state-icon"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg></div>
      <div class="empty-state-title">加载中...</div>
      <div class="empty-state-desc">正在获取模型列表</div>
    </div>

    <template v-else>
      <!-- Test Result Alert -->
      <div
        v-if="testResult"
        class="mb-4 px-4 py-3 rounded-xl text-sm font-medium animate-scaleIn"
        :class="testResult.startsWith('✅') ? 'tag-green !bg-green-50 dark:!bg-green-900/20 !text-green-700 dark:!text-green-300 !rounded-xl !px-4 !py-3' : 'tag-red !bg-red-50 dark:!bg-red-900/20 !text-red-600 dark:!text-red-400 !rounded-xl !px-4 !py-3'"
      >
        {{ testResult }}
      </div>

      <!-- Provider Cards -->
      <div class="space-y-2.5">
        <div
          v-for="(p, key) in providers"
          :key="key"
          class="card"
          :class="key === activeProvider ? 'ring-1 ring-[var(--brand-300)] dark:ring-[var(--brand-600)]' : ''"
        >
          <div class="p-4">
            <!-- Header -->
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-xl bg-[var(--surface-tertiary)] flex items-center justify-center text-lg">
                  {{ PROVIDER_ICONS[key] || '🤖' }}
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold">{{ p.name || key }}</span>
                    <span v-if="key === activeProvider" class="tag tag-blue">当前</span>
                  </div>
                  <div v-if="p.base_url" class="text-[11px] text-[var(--text-tertiary)] font-mono mt-0.5">{{ p.base_url }}</div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <span class="status-dot" :class="key === activeProvider ? 'status-dot-green' : 'status-dot' " :style="key !== activeProvider ? 'background: var(--text-quaternary); box-shadow: none;' : ''" />
                <button
                  @click="setupProvider(key)"
                  :disabled="saving[key]"
                  class="btn btn-sm"
                  :class="key === activeProvider ? 'btn-primary' : 'btn-secondary'"
                >
                  {{ saving[key] ? '配置中...' : (key === activeProvider ? '重新配置' : '配置') }}
                </button>
              </div>
            </div>

            <!-- Models -->
            <div class="flex flex-wrap gap-1.5 mb-3">
              <span
                v-for="m in (p.models || []).slice(0, 6)"
                :key="m"
                class="tag tag-zinc text-[10px] font-mono"
              >{{ m }}</span>
              <span v-if="(p.models || []).length > 6" class="tag tag-zinc text-[10px]">
                +{{ (p.models || []).length - 6 }}
              </span>
            </div>

            <!-- API Key Input -->
            <div class="flex items-center gap-2">
              <div class="relative flex-1">
                <input
                  v-model="keyInputs[key]"
                  type="password"
                  :placeholder="key === activeProvider && config.llm_api_key ? '已配置, 留空不变' : '输入 API Key'"
                  class="input text-xs font-mono pr-8"
                />
                <span v-if="keyHints[key]" class="absolute right-3 top-1/2 -translate-y-1/2 tag tag-green text-[9px]">{{ keyHints[key] }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- System Info -->
      <div class="card mt-4">
        <div class="p-4">
          <h2 class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-3">系统信息</h2>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
            <div v-for="(val, key) in config" :key="key" class="bg-[var(--surface-secondary)] rounded-lg px-3 py-2">
              <div class="text-[10px] text-[var(--text-tertiary)] font-medium mb-0.5 truncate">{{ key }}</div>
              <div class="text-xs font-mono text-[var(--text-primary)] truncate">
                {{ typeof val === 'string' && val.length > 40 ? val.slice(0, 40) + '…' : val }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
