<script setup lang="ts">
import { computed } from "vue"
import { marked } from "marked"
import DOMPurify from "dompurify"
import type { Message } from "@/types"

const props = defineProps<{
  message: Message
}>()

const html = computed(() => {
  try {
    const raw = marked.parse(props.message.content, { breaks: true }) as string
    return DOMPurify.sanitize(raw)
  } catch {
    return props.message.content
  }
})

const isUser = computed(() => props.message.role === "user")
const isTool = computed(() => props.message.role === "tool")
</script>

<template>
  <div
    class="flex gap-3 mb-4 animate-fadeInUp"
    :class="{
      'flex-row-reverse': isUser,
      'opacity-70': isTool,
    }"
  >
    <!-- Avatar -->
    <div
      class="w-8 h-8 rounded-xl flex items-center justify-center text-sm shrink-0 shadow-sm"
      :class="isUser
        ? 'bg-[var(--brand-600)]'
        : isTool
          ? 'bg-amber-600'
          : 'bg-gradient-to-br from-[var(--brand-500)] to-[var(--brand-700)]'"
    >
      <span class="text-white text-xs">{{ isUser ? "👤" : isTool ? "🔧" : "⚖" }}</span>
    </div>

    <!-- Content -->
    <div
      class="max-w-[80%] md:max-w-[70%] rounded-xl px-4 py-3 text-sm leading-relaxed"
      :class="isUser
        ? 'bg-[var(--brand-600)] text-white rounded-tr-md'
        : 'card rounded-tl-md'"
    >
      <!-- Tool calls indicator -->
      <div
        v-if="message.tool_calls && message.tool_calls.length > 0"
        class="flex items-center gap-1.5 mb-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-lg px-2.5 py-1.5"
      >
        <span>🔧</span>
        <span class="font-medium">正在调用: {{ message.tool_calls.map((t) => t.name).join(", ") }}</span>
      </div>

      <!-- Render markdown or raw text -->
      <div v-if="message.content" v-html="html" class="break-words" :class="isUser ? 'text-white' : 'chat-message'" />
      <div v-else class="flex items-center gap-2 text-[var(--text-tertiary)]">
        <div class="typing-dots"><span /><span /><span /></div>
        <span class="text-xs">思考中...</span>
      </div>
    </div>
  </div>
</template>
