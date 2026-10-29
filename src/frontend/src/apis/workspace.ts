import { request } from '../utils/request'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { parseWorkspaceStreamMessage, type AgentProgressEvent } from '../utils/workspace-stream'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 获取工作区插件列表
export const getWorkspacePluginsAPI = async () => {
  return request({
    url: '/api/v1/workspace/plugins',
    method: 'get'
  })
}

// 获取工作区会话列表
export const getWorkspaceSessionsAPI = async () => {
  return request({
    url: '/api/v1/workspace/session',
    method: 'get'
  })
}

// 创建工作区会话
export const createWorkspaceSessionAPI = async (data: { title?: string, contexts?: any }) => {
  return request({
    url: '/api/v1/workspace/session',
    method: 'post',
    data
  })
}

// 获取工作区会话信息
export const getWorkspaceSessionInfoAPI = async (sessionId: string) => {
  return request({
    url: `/api/v1/workspace/session/${sessionId}`,
    method: 'post'
  })
}

// 删除工作区会话  
export const deleteWorkspaceSessionAPI = async (sessionId: string) => {
  return request({
    url: `/api/v1/workspace/session`,
    method: 'delete',
    params: {
      session_id: sessionId
    }
  })
}

// 工作区日常对话接口
export interface WorkSpaceSimpleTask {
  query: string
  model_id: string
  plugins: string[]
  mcp_servers: string[]
  session_id?: string  // 会话ID，使用uuid4().hex格式
  agent_id?: string | null
}

export interface McpToolEvent {
  id: string
  server_name: string
  tool_name: string
  description?: string
  arguments?: Record<string, unknown>
  status: 'START' | 'END' | 'ERROR'
}

export const workspaceSimpleChatAPI = async (data: WorkSpaceSimpleTask) => {
  return request({
    url: '/api/v1/workspace/simple/chat',
    method: 'post',
    data,
    responseType: 'stream'
  })
}

// 工作区日常对话（SSE 流式）；HTTP/业务错误终止，不自动重试生成请求。
export const workspaceSimpleChatStreamAPI = async (
  data: WorkSpaceSimpleTask,
  onMessage: (chunk: string) => void,
  onError?: (err: unknown) => void,
  onClose?: () => void,
  onMcpToolEvent?: (event: McpToolEvent) => void,
  onReasoningChunk?: (chunk: string) => void,
  options: { signal?: AbortSignal; onAgentEvent?: (event: AgentProgressEvent) => void } = {}
) => {
  const token = localStorage.getItem('token')
  let completed = false
  try {
    await fetchEventSource(`${BASE_URL}/api/v1/workspace/simple/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify(data),
      signal: options.signal,
      openWhenHidden: true,
      async onopen(response) {
        if (!response.ok) {
          throw new Error(response.status === 403 ? '没有权限使用该会话或所选资源' : `对话请求失败（${response.status}）`)
        }
        if (!response.headers.get('content-type')?.includes('text/event-stream')) {
          throw new Error('对话服务未返回有效的数据流')
        }
      },
      onmessage(event) {
        const message = parseWorkspaceStreamMessage(event.data)
        switch (message.kind) {
          case 'text': onMessage(message.text); break
          case 'reasoning': onReasoningChunk?.(message.text); break
          case 'mcp': onMcpToolEvent?.(message.data as unknown as McpToolEvent); break
          case 'agent': options.onAgentEvent?.(message.data); break
          case 'done': completed = true; break
        }
      },
      onerror(error) {
        // Throwing prevents fetch-event-source from replaying a POST after failure.
        throw error
      },
      onclose() {
        if (!completed) throw new Error('连接已中断，本轮回复可能未保存，请重试')
        onClose?.()
      }
    })
  } catch (error) {
    if (!options.signal?.aborted) {
      onError?.(error)
      throw error
    }
  }
}
