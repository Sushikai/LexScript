import { ref } from "vue"

const API = "/api/v1"

export interface StreamMsg {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

export interface AgentStep {
  icon: string
  label: string
  status: "active" | "done" | "idle"
}

const messages = ref<StreamMsg[]>([])
const streaming = ref(false)
const agentSteps = ref<AgentStep[]>([])

export function useChatMessages() {
  function clearMessages() {
    messages.value = []
    agentSteps.value = []
  }

  function addMessage(role: "user" | "assistant", content: string): string {
    const id = `${role.slice(0, 1)}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    messages.value.push({ id, role, content, timestamp: new Date() })
    return id
  }

  async function sendMessage(
    sessionUuid: string,
    text: string,
    role: string,
    model?: string,
    onChunk?: (chunk: string) => void,
    onDone?: () => void
  ): Promise<string | null> {
    streaming.value = true
    const aid = `a-${Date.now()}`
    messages.value.push({ id: aid, role: "assistant", content: "", timestamp: new Date() })

    agentSteps.value = [
      { icon: "🧠", label: "理解问题", status: "active" },
      { icon: "🔍", label: "检索知识", status: "idle" },
      { icon: "✍", label: "生成回答", status: "idle" },
    ]

    let gotContent = false

    try {
      const r = await fetch(`${API}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_uuid: sessionUuid,
          message: text,
          role,
          model: model || undefined,
        }),
      })

      if (!r.ok) {
        const errBody = await r.text().catch(() => "")
        const msg = messages.value.find((m) => m.id === aid)
        if (msg) msg.content = `**⚠ 请求失败 (${r.status})**: ${errBody.slice(0, 200)}`
        messages.value = [...messages.value]
        return aid
      }

      const reader = r.body?.getReader()
      if (!reader) throw new Error("No reader")

      const decoder = new TextDecoder()
      let buf = ""
      let sessionUuidFromServer: string | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })
        const lines = buf.split("\n")
        buf = lines.pop() || ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const chunk = line.slice(6).trim()
          if (!chunk) continue
          try {
            const p = JSON.parse(chunk)
            const msg = messages.value.find((m) => m.id === aid)
            if (!msg) continue

            if (p.text !== undefined) {
              if (!gotContent) {
                agentSteps.value = agentSteps.value.map((s) => ({
                  ...s,
                  status: s.label === "生成回答" ? "active" : "done",
                }))
              }
              msg.content += p.text
              if (p.text) gotContent = true
              if (onChunk) onChunk(p.text)
              messages.value = [...messages.value]
            } else if (p.session_uuid !== undefined) {
              sessionUuidFromServer = p.session_uuid
            } else if (p.tool_calls !== undefined) {
              agentSteps.value = [
                { icon: "🧠", label: "理解问题", status: "done" },
                { icon: "🔍", label: "检索知识", status: "active" },
                { icon: "✍", label: "生成回答", status: "idle" },
              ]
            } else if (p.message) {
              msg.content += `\n\n**⚠ ${p.message}**`
              messages.value = [...messages.value]
            }
          } catch {
            /* skip parse errors */
          }
        }
      }

      if (sessionUuidFromServer) {
        onDone?.()
        return sessionUuidFromServer
      }
    } catch (e: unknown) {
      const msg = messages.value.find((m) => m.id === aid)
      if (msg) {
        msg.content = `\n\n**⚠ 连接错误**: ${e instanceof Error ? e.message : String(e)}`
        messages.value = [...messages.value]
      }
    } finally {
      streaming.value = false
      agentSteps.value = []
      const msg = messages.value.find((m) => m.id === aid)
      if (msg && !msg.content) {
        msg.content = "抱歉，我暂时无法回答这个问题。请检查后端服务状态。"
        messages.value = [...messages.value]
      }
    }

    return aid
  }

  return {
    messages,
    streaming,
    agentSteps,
    clearMessages,
    addMessage,
    sendMessage,
  }
}
