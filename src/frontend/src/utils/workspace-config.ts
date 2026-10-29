export interface ConversationConfig {
  model_id: string
  plugins: string[]
  mcp_servers: string[]
  agent_id: string | null
}

export interface AgentDefaults {
  agent_id: string
  llm_id: string
  tool_ids: string[]
  mcp_ids: string[]
}

export function configFromAgent(agent: AgentDefaults): ConversationConfig {
  return {
    agent_id: agent.agent_id,
    model_id: agent.llm_id,
    plugins: [...agent.tool_ids],
    mcp_servers: [...agent.mcp_ids],
  }
}

const stringList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

// Legacy contexts have no configuration. Preserve that distinction for the UI.
export function restoreConversationConfig(contexts: Array<{ config?: unknown }>): ConversationConfig | null {
  for (const context of [...contexts].reverse()) {
    if (!context.config || typeof context.config !== 'object') continue
    const config = context.config as Record<string, unknown>
    if (typeof config.model_id !== 'string') continue
    return {
      model_id: config.model_id,
      plugins: stringList(config.plugins),
      mcp_servers: stringList(config.mcp_servers),
      agent_id: typeof config.agent_id === 'string' ? config.agent_id : null,
    }
  }
  return null
}
