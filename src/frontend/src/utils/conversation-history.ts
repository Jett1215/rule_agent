export type ConversationMode = 'normal' | 'lingseek'
export type ConversationSource = 'workspace' | 'dialog'

export interface ConversationEntry {
  key: string
  id: string
  source: ConversationSource
  mode: ConversationMode
  title: string
  updatedAt: string
  agentId?: string
}

type HistoryRecord = Record<string, unknown>

const stringValue = (value: unknown): string => typeof value === 'string' ? value : ''

export function normalizeConversationHistory(records: unknown, source: ConversationSource): ConversationEntry[] {
  if (!Array.isArray(records)) return []
  const entries = new Map<string, ConversationEntry>()
  for (const record of records) {
    if (!record || typeof record !== 'object') continue
    const item = record as HistoryRecord
    const id = stringValue(source === 'dialog' ? item.dialog_id : (item.session_id || item.id))
    if (!id) continue
    const key = `${source}:${id}`
    entries.set(key, {
      key,
      id,
      ...(source === 'dialog' && stringValue(item.agent_id) ? { agentId: stringValue(item.agent_id) } : {}),
      source,
      mode: source === 'dialog' || item.agent === 'simple' ? 'normal' : 'lingseek',
      title: stringValue(source === 'dialog' ? item.name : item.title) || '未命名会话',
      updatedAt: stringValue(item.update_time || item.updated_at || item.create_time || item.created_at),
    })
  }
  return [...entries.values()]
}

export function mergeConversationHistory(...sources: ConversationEntry[][]): ConversationEntry[] {
  const timestamp = (entry: ConversationEntry) => Date.parse(entry.updatedAt) || 0
  return sources.flat().sort((a, b) => timestamp(b) - timestamp(a) || a.key.localeCompare(b.key))
}

export function conversationLocation(entry: ConversationEntry) {
  if (entry.source === 'dialog') {
    return { name: 'chatPage', query: { dialog_id: entry.id, ...(entry.agentId ? { agent_id: entry.agentId } : {}) } }
  }
  if (entry.mode === 'lingseek') {
    return { name: 'taskGraphPage', query: { session_id: entry.id } }
  }
  return { name: 'workspaceDefaultPage', query: { session_id: entry.id, mode: 'normal' } }
}

export function selectedConversationKey(query: Record<string, unknown>): string {
  if (typeof query.dialog_id === 'string' && query.dialog_id) return `dialog:${query.dialog_id}`
  if (typeof query.session_id === 'string' && query.session_id) return `workspace:${query.session_id}`
  return ''
}
