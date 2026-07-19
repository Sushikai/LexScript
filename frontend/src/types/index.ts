/** 聊天消息 */
export interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp: Date;
  tool_calls?: ToolCall[];
}

/** 工具调用 */
export interface ToolCall {
  name: string;
  args: string;
}

/** 工具调用结果 */
export interface ToolResult {
  tool_call_id: string;
  tool_name: string;
  result: unknown;
  success: boolean;
}

/** 会话 */
export interface Session {
  uuid: string;
  title: string;
  role: string;
  model: string;
  created_at: string;
}

/** 文件条目 */
export interface FileEntry {
  id: number;
  name: string;
  size: number;
  type: string;
  status: string;
  chunks: number;
  created: string;
}

/** 模板 */
export interface Template {
  id: number;
  name: string;
  category: string;
  description: string;
  variables: string[];
}

/** 法条 */
export interface Statute {
  code: string;
  name: string;
  category: string;
  content: string;
}

/** 系统信息 */
export interface SystemInfo {
  service: string;
  version: string;
  host: string;
  port: number;
  lan_ip: string | null;
  lan_url: string | null;
  local_url: string;
  tunnel_url: string | null;
}

/** SSE 事件 */
export interface SSEMessage {
  event: "chunk" | "tools" | "tool_results" | "error" | "done";
  data: string;
}
