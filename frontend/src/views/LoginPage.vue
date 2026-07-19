<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const auth = useAuthStore()

const username = ref("")
const password = ref("")
const loading = ref(false)
const error = ref("")

async function login() {
  if (!username.value.trim() || !password.value.trim()) {
    error.value = "请输入用户名和密码"
    return
  }
  loading.value = true
  error.value = ""
  try {
    const ok = await auth.login(username.value, password.value)
    if (ok) {
      router.push("/")
    } else {
      error.value = "用户名或密码错误"
    }
  } catch {
    error.value = "网络错误，请检查后端服务"
  }
  loading.value = false
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter") login()
}
</script>

<template>
  <div class="h-screen flex bg-gradient-to-br from-[var(--brand-50)] to-[var(--surface-secondary)] dark:from-[var(--dark-surface-primary)] dark:to-[var(--dark-surface-secondary)]">
    <!-- Left: decorative panel -->
    <div class="hidden lg:flex flex-1 items-center justify-center relative overflow-hidden">
      <!-- Ambient decoration -->
      <div class="absolute -top-32 -right-32 w-96 h-96 bg-gradient-to-br from-[var(--brand-200)]/40 to-transparent dark:from-[var(--brand-600)]/10 rounded-full blur-3xl pointer-events-none" />
      <div class="absolute -bottom-32 -left-32 w-80 h-80 bg-gradient-to-tr from-[var(--brand-300)]/30 to-transparent dark:from-[var(--brand-500)]/8 rounded-full blur-3xl pointer-events-none" />
      <div class="absolute top-1/3 left-1/4 w-48 h-48 bg-gradient-to-bl from-[var(--brand-100)]/30 to-transparent dark:from-[var(--brand-400)]/5 rounded-full blur-3xl pointer-events-none" />

      <div class="text-center max-w-md relative">
        <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)] flex items-center justify-center text-white text-3xl font-bold mx-auto mb-6 shadow-xl shadow-[var(--brand-500)]/20 ring-4 ring-[var(--brand-200)] dark:ring-[var(--brand-800)]">&#9878;</div>
        <h1 class="text-3xl font-bold tracking-tight mb-3">LexScript</h1>
        <p class="text-[var(--text-secondary)] text-sm leading-relaxed">本地私有化法律 AI 智能文书生成平台<br />MiniMax 驱动 · 百 MB 卷宗检索 · 全离线运行</p>

        <!-- Feature highlights -->
        <div class="mt-8 space-y-3 text-left max-w-xs mx-auto">
          <div class="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-[var(--dark-surface-elevated)]/40 backdrop-blur-sm border border-white/30 dark:border-white/5">
            <span class="w-8 h-8 rounded-lg bg-[var(--brand-100)] dark:bg-[var(--brand-900)]/40 flex items-center justify-center text-sm shrink-0">&#128274;</span>
            <div>
              <div class="text-xs font-medium text-[var(--text-primary)]">数据不出本机</div>
              <div class="text-[10px] text-[var(--text-tertiary)] mt-0.5">全离线运行 · 安全可控</div>
            </div>
          </div>
          <div class="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-[var(--dark-surface-elevated)]/40 backdrop-blur-sm border border-white/30 dark:border-white/5">
            <span class="w-8 h-8 rounded-lg bg-[var(--brand-100)] dark:bg-[var(--brand-900)]/40 flex items-center justify-center text-sm shrink-0">&#9881;</span>
            <div>
              <div class="text-xs font-medium text-[var(--text-primary)]">多模型支持</div>
              <div class="text-[10px] text-[var(--text-tertiary)] mt-0.5">MiniMax / DeepSeek / Qwen 等</div>
            </div>
          </div>
          <div class="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-[var(--dark-surface-elevated)]/40 backdrop-blur-sm border border-white/30 dark:border-white/5">
            <span class="w-8 h-8 rounded-lg bg-[var(--brand-100)] dark:bg-[var(--brand-900)]/40 flex items-center justify-center text-sm shrink-0">&#128196;</span>
            <div>
              <div class="text-xs font-medium text-[var(--text-primary)]">智能文书引擎</div>
              <div class="text-[10px] text-[var(--text-tertiary)] mt-0.5">百 MB 卷宗 · 秒级检索</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: login form -->
    <div class="flex-1 flex items-center justify-center p-6">
      <div class="w-full max-w-sm">
        <!-- Mobile brand -->
        <div class="lg:hidden text-center mb-8">
          <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)] flex items-center justify-center text-white text-xl font-bold mx-auto mb-3 shadow-lg ring-2 ring-[var(--brand-200)] dark:ring-[var(--brand-800)]">&#9878;</div>
          <h1 class="text-xl font-bold">LexScript</h1>
          <p class="text-xs text-[var(--text-secondary)] mt-1">法律 AI 智能工作台</p>
          <p class="text-[10px] text-[var(--text-tertiary)] mt-0.5">数据不出本机 · 安全可控</p>
        </div>

        <div class="card-elevated p-6 animate-fadeIn">
          <div class="flex items-center gap-2.5 mb-1">
            <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)] flex items-center justify-center text-white text-[10px] font-bold shrink-0">&#9878;</div>
            <div>
              <h2 class="text-base font-semibold">登录</h2>
            </div>
          </div>
          <p class="text-xs text-[var(--text-tertiary)] mb-5 ml-0.5">输入管理员账户信息</p>

          <div class="space-y-4">
            <div>
              <label class="text-xs font-medium text-[var(--text-secondary)] block mb-1.5">用户名</label>
              <input
                v-model="username"
                type="text"
                placeholder="admin"
                class="input"
                :class="{ 'input-error': error }"
                @keydown="handleKeydown"
                autocomplete="username"
              />
            </div>
            <div>
              <label class="text-xs font-medium text-[var(--text-secondary)] block mb-1.5">密码</label>
              <input
                v-model="password"
                type="password"
                placeholder="••••••"
                class="input"
                :class="{ 'input-error': error }"
                @keydown="handleKeydown"
                autocomplete="current-password"
              />
            </div>

            <div v-if="error" class="flex items-center gap-1.5 text-xs text-red-500 bg-red-50 dark:bg-red-900/10 rounded-lg px-3 py-2">
              <svg class="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" /></svg>
              <span>{{ error }}</span>
            </div>

            <button
              @click="login"
              :disabled="loading || !username.trim() || !password.trim()"
              class="btn btn-primary btn-lg w-full justify-center"
            >
              <template v-if="loading">
                <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                登录中...
              </template>
              <template v-else>登录</template>
            </button>
          </div>

          <div class="mt-5 pt-4 border-t border-[var(--border-light)]">
            <p class="text-[10px] text-[var(--text-tertiary)] text-center">默认账户：<span class="font-mono font-medium text-[var(--brand-600)] dark:text-[var(--brand-400)]">root</span> / <span class="font-mono font-medium text-[var(--brand-600)] dark:text-[var(--brand-400)]">123456</span> ｜<span class="font-mono font-medium text-[var(--brand-600)] dark:text-[var(--brand-400)]"> root2</span> / <span class="font-mono font-medium text-[var(--brand-600)] dark:text-[var(--brand-400)]">123456</span></p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
