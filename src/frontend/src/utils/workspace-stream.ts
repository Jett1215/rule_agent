export interface AgentProgressEvent {
  title: string
  message?: string
  status: 'START' | 'END' | 'ERROR'
}

export type WorkspaceStreamMessage =
  | { kind: 'text' | 'reasoning'; text: string }
  | { kind: 'mcp'; data: Record<string, unknown> }
  | { kind: 'agent'; data: AgentProgressEvent }
  | { kind: 'done' }
  | { kind: 'ignore' }

export function parseWorkspaceStreamMessage(raw: string): WorkspaceStreamMessage {
  if (!raw || raw === '[DONE]') return { kind: 'ignore' }
  const parsed = JSON.parse(raw)
  if (parsed.event === 'error' || parsed.type === 'error') {
    throw new Error(parsed.data?.message || '对话生成失败，请稍后重试')
  }
  if (parsed.event === 'done') return { kind: 'done' }
  if (parsed.event === 'mcp_tool') return { kind: 'mcp', data: parsed.data }
  if (parsed.event === 'agent_event') return { kind: 'agent', data: parsed.data }
  if (parsed.event === 'reasoning_chunk') {
    return { kind: 'reasoning', text: parsed.data?.chunk || '' }
  }
  const text = parsed.data?.message ?? parsed.data?.chunk
  return typeof text === 'string' && text ? { kind: 'text', text } : { kind: 'ignore' }
}
