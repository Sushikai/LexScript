/**
 * Agent Chat API 客户端 — SSE 流式对话 + 工具调用。
 * 使用 /api/v1/agent/chat 端点，支持 LLM 自动调用后端工具。
 */
import { ref, type Ref } from "vue";
import type { Message, ToolCall, Session } from "@/types";

const API_BASE = "/api/v1";

export function useAgent() {
  const messages: Ref<Message[]> = ref([]);
  const sessions: Ref<Session[]> = ref([]);
  const streaming = ref(false);
  const currentSession = ref<string | null>(null);

  /** 加载会话列表 */
  async function loadSessions() {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`);
      const data = await res.json();
      sessions.value = (data.data || []).map((s: Session) => ({
        ...s,
        title: s.title || "新对话",
      }));
    } catch (e) {
      console.error("加载会话失败:", e);
    }
  }

  /** 创建新会话 */
  async function newSession(title = "新对话", role = "litigator"): Promise<string | null> {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, role }),
      });
      const data = await res.json();
      if (data.ok && data.data?.uuid) {
        currentSession.value = data.data.uuid;
        messages.value = [];
        await loadSessions();
        return data.data.uuid;
      }
      return null;
    } catch (e) {
      console.error("创建会话失败:", e);
      return null;
    }
  }

  /** 选择会话 */
  async function selectSession(uuid: string) {
    currentSession.value = uuid;
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${uuid}`);
      const data = await res.json();
      if (data.ok && data.data) {
        messages.value = (data.data.messages || []).map((m: Message) => ({
          ...m,
          timestamp: new Date(),
        }));
      }
    } catch (e) {
      console.error("加载消息失败:", e);
    }
  }

  /** 发送消息（SSE 流式 + 工具调用）到 /agent/chat */
  async function sendMessage(text: string): Promise<void> {
    if (!text.trim() || streaming.value) return;

    // 添加用户消息到界面
    messages.value.push({
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date(),
    });

    streaming.value = true;

    // 空的 assistant 消息占位
    const assistantMsg: Message = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };
    messages.value.push(assistantMsg);

    try {
      const res = await fetch(`${API_BASE}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_uuid: currentSession.value,
          message: text,
          role: "litigator",
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No reader");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("event: ") && !line.startsWith("data: ")) continue;

          // Parse SSE event:data pairs
          // event: chunk/tools/tool_results/done/error
          // data: {...}
          if (line.startsWith("event: ")) {
            // event line — handled on next data line
            continue;
          }

          // data line
          const chunk = line.slice(6).trim();
          if (!chunk) continue;

          try {
            const parsed = JSON.parse(chunk);

            // The event type is embedded in the data JSON for our format
            // or we infer from content shape
            if (parsed.text !== undefined) {
              // Chunk event
              assistantMsg.content += parsed.text;
              messages.value = [...messages.value];
              // Update currentSession from done event
            } else if (parsed.session_uuid !== undefined) {
              // Done event — update session if new
              if (parsed.session_uuid && !currentSession.value) {
                currentSession.value = parsed.session_uuid;
                loadSessions();
              }
            } else if (parsed.tool_calls !== undefined) {
              // Tools event — show tool calls in message
              assistantMsg.tool_calls = parsed.tool_calls.map((tc: any) => ({
                name: tc.name,
                args: typeof tc.args === "string" ? tc.args : JSON.stringify(tc.args),
              }));
              messages.value = [...messages.value];
            } else if (parsed.message !== undefined && !parsed.text) {
              // Error event
              assistantMsg.content += `\n\n**错误**: ${parsed.message}`;
              messages.value = [...messages.value];
            }
          } catch {
            // skip unparseable lines
          }
        }
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      assistantMsg.content += `\n\n**连接错误**: ${errMsg}`;
      messages.value = [...messages.value];
    } finally {
      streaming.value = false;
      messages.value = [...messages.value];
    }
  }

  return {
    messages,
    sessions,
    streaming,
    currentSession,
    loadSessions,
    newSession,
    selectSession,
    sendMessage,
  };
}
