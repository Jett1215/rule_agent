import { fetchEventSource } from '@microsoft/fetch-event-source'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function streamLingSeek(
  path: string,
  data: object,
  onEvent: (event: any) => void,
  onError?: (error: unknown) => void,
  onClose?: () => void,
  signal?: AbortSignal,
) {
  if (signal?.aborted) return
  const ctrl = new AbortController()
  const requestSignal = signal || ctrl.signal
  const token = localStorage.getItem('token')
  try {
    await fetchEventSource(`${BASE_URL}/api/v1/workspace/lingseek/${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify(data),
      signal: requestSignal,
      openWhenHidden: true,
      async onopen(response) {
        if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream')) {
          throw new Error(`灵寻请求失败（HTTP ${response.status}）`)
        }
      },
      onmessage(event) {
        if (requestSignal.aborted || !event.data) return
        const parsed = JSON.parse(event.data)
        if (parsed.event === 'error') throw new Error('灵寻执行失败')
        onEvent(parsed)
      },
      onerror(error) {
        // 工具任务不可自动重放，出错后交给用户决定是否重试。
        throw error
      },
      onclose() {
        if (!requestSignal.aborted) onClose?.()
      },
    })
  } catch (error) {
    if (!requestSignal.aborted) onError?.(error)
  }
}

const messageHandler = (onMessage: (data: any) => void) => (event: any) => {
  if (typeof event.data?.chunk === 'string') onMessage(event.data.chunk)
}

export const generateLingSeekGuidePromptAPI = async (
  data: { query: string; tools?: string[]; web_search?: boolean; mcp_servers?: string[] },
  onMessage: (data: any) => void,
  onError?: (error: any) => void,
  onClose?: () => void,
  signal?: AbortSignal,
) => streamLingSeek('guide_prompt', data, messageHandler(onMessage), onError, onClose, signal)

export const regenerateLingSeekGuidePromptAPI = async (
  data: { query: string; guide_prompt: string; feedback: string; web_search?: boolean; plugins?: string[]; mcp_servers?: string[] },
  onMessage: (data: any) => void,
  onError?: (error: any) => void,
  onClose?: () => void,
  signal?: AbortSignal,
) => streamLingSeek('guide_prompt/feedback', data, messageHandler(onMessage), onError, onClose, signal)

export const generateLingSeekTasksAPI = async (
  data: { guide_prompt: string },
  onMessage: (data: any) => void,
  onError?: (error: any) => void,
  onClose?: () => void,
  signal?: AbortSignal,
) => streamLingSeek('task', data, messageHandler(onMessage), onError, onClose, signal)

export const startLingSeekTaskAPI = async (
  data: { query: string; guide_prompt: string; web_search?: boolean; plugins?: string[]; mcp_servers?: string[] },
  onMessage: (data: any) => void,
  onTaskGraph?: (graph: any) => void,
  onStepResult?: (stepData: { title: string; message: string }) => void,
  onTaskResult?: (message: string) => void,
  onError?: (error: any) => void,
  onClose?: () => void,
  signal?: AbortSignal,
) => streamLingSeek('task_start', data, (event) => {
  if (event.event === 'generate_tasks' && Array.isArray(event.data?.graph)) {
    onTaskGraph?.(event.data.graph)
  } else if (event.event === 'step_result' && event.data?.title && event.data?.message) {
    onStepResult?.({ title: event.data.title, message: event.data.message })
  } else if (event.event === 'task_result' && typeof event.data?.message === 'string') {
    onTaskResult?.(event.data.message)
  } else if (typeof event.data?.chunk === 'string') {
    onMessage(event.data.chunk)
  } else {
    onMessage(event)
  }
}, onError, onClose, signal)
