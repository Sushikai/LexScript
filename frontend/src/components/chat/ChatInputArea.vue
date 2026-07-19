<script setup lang="ts">
import { ref } from "vue"

interface FileChip {
  name: string
  size: number
  file: File
}

const props = defineProps<{
  disabled: boolean
  streaming: boolean
  attachedFiles: FileChip[]
  currentRole: string
  currentModel: string
  activeSkill: string | null
  roleLabels: Record<string, string>
}>()

const emit = defineEmits<{
  send: [text: string]
  attachFiles: [files: File[]]
  removeFile: [index: number]
}>()

const inputText = ref("")
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const chatFileInput = ref<HTMLInputElement | null>(null)

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = "auto"
  el.style.height = Math.min(el.scrollHeight, 160) + "px"
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.disabled) return
  inputText.value = ""
  if (textareaRef.value) {
    textareaRef.value.style.height = "auto"
  }
  emit("send", text)
}

function handleFileInput(e: Event) {
  const el = e.target as HTMLInputElement
  if (el.files?.length) {
    emit("attachFiles", Array.from(el.files))
    el.value = ""
  }
}
</script>

<template>
  <div class="px-4 md:px-6 py-3 bg-[var(--surface-primary)] border-t border-[var(--border-light)] shrink-0">
    <div class="max-w-3xl mx-auto">
      <!-- Attached Files -->
      <div v-if="attachedFiles.length" class="flex flex-wrap gap-1.5 mb-2">
        <div
          v-for="(f, fi) in attachedFiles"
          :key="fi"
          class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border-light)] text-xs"
        >
          <span class="text-[var(--text-secondary)]">📎</span>
          <span class="text-[var(--text-secondary)] truncate max-w-[120px]">{{ f.name }}</span>
          <span class="text-[10px] text-[var(--text-tertiary)]">{{ (f.size / 1024).toFixed(0) }}KB</span>
          <button @click="emit('removeFile', fi)" class="text-[var(--text-tertiary)] hover:text-red-500 transition-colors ml-0.5">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>

      <!-- Input Row -->
      <div class="flex gap-2.5 items-end">
        <div class="flex-1 relative">
          <textarea
            ref="textareaRef"
            v-model="inputText"
            placeholder="输入你的法律问题..."
            :disabled="streaming"
            class="input resize-none min-h-[44px] max-h-[160px] pr-10 leading-relaxed"
            rows="1"
            @keydown="handleKeydown"
            @input="autoResize"
          />
          <button
            @click="chatFileInput?.click()"
            class="absolute right-2 bottom-2.5 p-1 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
            title="上传文件"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32a.75.75 0 01-1.06-1.06L16.5 8.25" /></svg>
          </button>
        </div>
        <button
          :disabled="(!inputText.trim() && !attachedFiles.length) || streaming"
          class="btn btn-primary btn-lg px-5 !rounded-xl min-w-[44px]"
          @click="handleSend"
        >
          <svg v-if="!streaming" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" /></svg>
          <span v-else class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin block" />
        </button>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between mt-1.5">
        <div class="flex items-center gap-2">
          <span class="text-[10px] tag tag-zinc">{{ roleLabels[currentRole] || currentRole }}</span>
          <span v-if="currentModel" class="text-[10px] tag tag-blue hidden sm:inline-flex">{{ currentModel }}</span>
          <span v-if="activeSkill" class="text-[10px] tag tag-amber">✦ {{ activeSkill }}</span>
        </div>
        <div class="text-[10px] text-[var(--text-tertiary)] hidden sm:block">Enter 发送 · Shift+Enter 换行 · 📎 附件</div>
      </div>
    </div>
    <input ref="chatFileInput" type="file" multiple class="hidden" @change="handleFileInput" />
  </div>
</template>
