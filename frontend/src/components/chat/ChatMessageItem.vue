<script setup lang="ts">
import { ref } from "vue"
import { marked } from "marked"
import DOMPurify from "dompurify"
import { useToast } from "@/composables/useToast"
import type { Message } from "@/types"

const { show: showToast } = useToast()

const props = defineProps<{
  message: Message
  isStreaming: boolean
  isLast: boolean
}>()

const emit = defineEmits<{
  copy: [text: string]
  like: [id: string]
  dislike: [id: string]
  regenerate: []
}>()

const liked = ref<boolean | null>(null)

function renderMarkdown(text: string): string {
  if (!text) return ""
  try {
    const html = marked.parse(text, { breaks: true }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return DOMPurify.sanitize(text)
  }
}

function handleCopy() {
  navigator.clipboard.writeText(props.message.content)
  showToast("已复制到剪贴板", "success")
  emit("copy", props.message.content)
}

function formatTime(d: Date): string {
  const date = new Date(d)
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}
</script>

<template>
  <div class="mb-5 animate-message-enter">
    <!-- User Message -->
    <div v-if="message.role === 'user'" class="flex justify-end">
      <div class="chat-bubble-user max-w-[78%] md:max-w-[65%]">
        <div class="text-sm leading-relaxed whitespace-pre-wrap break-words">{{ message.content }}</div>
        <div class="text-[10px] mt-1.5 opacity-60 text-right leading-none">{{ formatTime(message.timestamp) }}</div>
      </div>
    </div>

    <!-- AI Message -->
    <div v-else class="flex gap-3 group relative">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)] flex items-center justify-center text-white text-[10px] font-bold shrink-0 mt-0.5 shadow-sm">&#9878;</div>
      <div class="flex-1 min-w-0">
        <div class="chat-bubble-ai">
          <div class="chat-message">
            <!-- Content -->
            <div v-if="message.content" class="text-sm leading-relaxed" v-html="renderMarkdown(message.content)" />
            <!-- Streaming cursor (has content, still streaming) -->
            <span v-if="isStreaming && message.content" class="streaming-cursor" />
            <!-- Typing dots (no content yet, streaming or last) -->
            <div v-else-if="!message.content && (isStreaming || isLast)" class="flex items-center gap-2.5 text-[var(--text-tertiary)]">
              <div class="typing-dots"><span /><span /><span /></div>
              <span class="text-xs">思考中</span>
            </div>
          </div>
        </div>

        <!-- Actions bar -->
        <div
          v-if="message.content && !isStreaming"
          class="flex items-center gap-0.5 mt-1.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        >
          <span class="text-[10px] text-[var(--text-tertiary)] font-mono mr-1.5">{{ formatTime(message.timestamp) }}</span>
          <button @click="handleCopy" class="btn btn-ghost btn-sm p-1.5 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]" title="复制">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" /></svg>
          </button>
          <button
            @click="liked === true ? (liked = null) : (liked = true)"
            class="btn btn-ghost btn-sm p-1.5"
            :class="liked === true ? 'text-[var(--brand-500)]' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'"
            title="有用"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6.633 10.5c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3a.75.75 0 01.75-.75A2.25 2.25 0 0116.5 4.5c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 01-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 00-1.423-.23H5.904M14.25 9h2.25M5.904 18.75c.083.205.173.405.27.602.197.4-.078.898-.523.898h-.908c-.889 0-1.713-.518-1.972-1.368a12 12 0 01-.521-3.507c0-1.553.295-3.036.831-4.398C3.387 10.203 4.167 9.75 5 9.75h1.053c.472 0 .745.556.5.96a8.958 8.958 0 00-1.302 4.665c0 1.194.232 2.333.654 3.375z" /></svg>
          </button>
          <button
            @click="liked === false ? (liked = null) : (liked = false)"
            class="btn btn-ghost btn-sm p-1.5"
            :class="liked === false ? 'text-red-500' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'"
            title="没用"
          >
            <svg class="w-3.5 h-3.5 scale-y-[-1]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6.633 10.5c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3a.75.75 0 01.75-.75A2.25 2.25 0 0116.5 4.5c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 01-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 00-1.423-.23H5.904M14.25 9h2.25M5.904 18.75c.083.205.173.405.27.602.197.4-.078.898-.523.898h-.908c-.889 0-1.713-.518-1.972-1.368a12 12 0 01-.521-3.507c0-1.553.295-3.036.831-4.398C3.387 10.203 4.167 9.75 5 9.75h1.053c.472 0 .745.556.5.96a8.958 8.958 0 00-1.302 4.665c0 1.194.232 2.333.654 3.375z" /></svg>
          </button>
          <button v-if="isLast" @click="emit('regenerate')" class="btn btn-ghost btn-sm p-1.5 text-[var(--text-tertiary)] hover:text-amber-500" title="重新生成">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
