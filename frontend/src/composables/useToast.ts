import { ref, type Ref } from "vue"

interface Toast {
  id: number
  message: string
  type: "success" | "error" | "info" | "warning"
}

const toasts: Ref<Toast[]> = ref([])
let nextId = 0

export function useToast() {
  function show(message: string, type: Toast["type"] = "info", duration = 4000) {
    const id = nextId++
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, duration)
  }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return { toasts, show, dismiss }
}
