<script setup lang="ts">
const emit = defineEmits<{
  select: [text: string]
}>()

const suggestions = [
  { label: "📊 分析案情", text: "分析这个案件的胜诉概率" },
  { label: "📝 起草文书", text: "起草一份起诉状模板" },
  { label: "⚖ 检索法条", text: "查找关于合同违约的法律规定" },
  { label: "📄 总结文件", text: "总结这份文件的关键点" },
]
</script>

<template>
  <div class="px-4 md:px-6 pt-2 pb-0 bg-[var(--surface-primary)] shrink-0">
    <div class="max-w-3xl mx-auto flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
      <button
        v-for="s in suggestions"
        :key="s.text"
        @click="emit('select', s.text)"
        class="btn btn-sm btn-ghost text-[11px] whitespace-nowrap border border-[var(--border-light)] hover:border-[var(--brand-300)] transition-colors"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>
