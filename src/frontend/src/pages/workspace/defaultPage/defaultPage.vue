<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { getWorkspacePluginsAPI, getWorkspaceSessionInfoAPI, workspaceSimpleChatStreamAPI, type McpToolEvent, type WorkSpaceSimpleTask } from '../../../apis/workspace'
import { getVisibleLLMsAPI, type LLMResponse } from '../../../apis/llm'
import { getMCPServersAPI, type MCPServer } from '../../../apis/mcp-server'
import { getAgentsAPI, type AgentResponse } from '../../../apis/agent'
import { generateSessionId } from '../../../utils/session-id'
import { configFromAgent, restoreConversationConfig, type ConversationConfig } from '../../../utils/workspace-config'
import type { AgentProgressEvent } from '../../../utils/workspace-stream'
import { useUserStore } from '../../../store/user'
import userAvatar from '../../../assets/user.svg'
import robotAvatar from '../../../assets/robot.svg'

const userStore = useUserStore()
const router = useRouter()
const route = useRoute()
const inputMessage = ref('')
const selectedMode = ref(route.query.mode === 'lingseek' ? 'lingseek' : 'normal')
const plugins = ref<any[]>([])
const modelOptions = ref<LLMResponse[]>([])
const agents = ref<AgentResponse[]>([])
const selectedAgentId = ref('')
const selectedModelId = ref('')
const selectedModel = computed(() => modelOptions.value.find(m => m.llm_id === selectedModelId.value)?.model || (selectedModelId.value ? '模型已不可用' : '选择模型'))
const selectedTools = ref<string[]>([])
const selectedMcpServers = ref<string[]>([])
const mcpServers = ref<MCPServer[]>([])
const showModelSelector = ref(false)
const showToolSelector = ref(false)
const showMcpSelector = ref(false)
const webSearchEnabled = ref(false)
const toolDropdownRef = ref<HTMLElement | null>(null)
const mcpDropdownRef = ref<HTMLElement | null>(null)
const modelDropdownRef = ref<HTMLElement | null>(null)
const currentSessionId = ref('')
const chatConversationRef = ref<HTMLElement | null>(null)
const isGenerating = ref(false)
const modelsLoading = ref(false)
const mcpServersLoading = ref(false)
const mcpServersError = ref(false)
const resourceError = ref('')
const historyLoading = ref(false)
const historyError = ref('')
const legacyConfig = ref(false)
let activeController: AbortController | null = null
let loadVersion = 0
let disposed = false
let historyLoaded = false

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  mcpToolCalls?: Array<McpToolEvent & { expanded?: boolean }>
  agentEvents?: Array<AgentProgressEvent & { expanded?: boolean }>
  reasoning?: string
  reasoningExpanded?: boolean
  status?: 'generating' | 'complete' | 'stopped' | 'error'
}
const messages = ref<ChatMessage[]>([])
const modes = [
  { id: 'normal', label: '日常对话', icon: '💬' },
  { id: 'lingseek', label: '灵寻 LingSeek', icon: '✨' }
]
const selectedAgent = computed(() => agents.value.find(a => a.agent_id === selectedAgentId.value))
const selectedAgentMissing = computed(() => !!selectedAgentId.value && !selectedAgent.value)
const configurationIssue = computed(() => {
  if (selectedMode.value !== 'normal') return ''
  if (selectedAgentMissing.value) return '所选智能体已不可用，请重新选择。'
  if (selectedModelId.value && !modelOptions.value.some(m => m.llm_id === selectedModelId.value)) return '所选模型已不可用，请重新选择。'
  if (selectedTools.value.some(id => !plugins.value.some(p => (p.id || p.tool_id) === id))) return '部分已选工具已不可用，请重新选择或清空。'
  if (selectedMcpServers.value.some(id => !mcpServers.value.some(m => m.mcp_server_id === id))) return '部分已选 MCP 已不可用，请重新选择或清空。'
  return ''
})
const controlsDisabled = computed(() => isGenerating.value || historyLoading.value || modelsLoading.value)
const sendDisabled = computed(() => controlsDisabled.value || !!historyError.value || !!resourceError.value || !!configurationIssue.value)

const handleAvatarError = (event: Event) => { (event.target as HTMLImageElement).src = userAvatar }
const scrollToBottom = async () => {
  await nextTick()
  if (chatConversationRef.value) chatConversationRef.value.scrollTop = chatConversationRef.value.scrollHeight
}
const formatMcpArguments = (arguments_: Record<string, unknown>) => Object.entries(arguments_)
  .map(([key, value]) => `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}`).join('、')

const applyConfig = (config: ConversationConfig) => {
  selectedAgentId.value = config.agent_id || ''
  selectedModelId.value = config.model_id
  selectedTools.value = [...config.plugins]
  selectedMcpServers.value = [...config.mcp_servers]
}
const resetConfig = () => applyConfig({ agent_id: null, model_id: modelOptions.value[0]?.llm_id || '', plugins: [], mcp_servers: [] })
const selectAgent = (event: Event) => {
  if (controlsDisabled.value) return
  const agentId = (event.target as HTMLSelectElement).value
  const agent = agents.value.find(a => a.agent_id === agentId)
  if (agent) applyConfig(configFromAgent(agent))
  else resetConfig()
  legacyConfig.value = false
}
const selectMode = (modeId: string) => {
  if (controlsDisabled.value || selectedMode.value === modeId) return
  if (messages.value.length || route.query.session_id) {
    router.push({ name: 'workspaceDefaultPage', query: { mode: modeId, new: generateSessionId() } })
  } else {
    selectedMode.value = modeId
    router.replace({ name: 'workspaceDefaultPage', query: { mode: modeId } })
  }
}
const selectModel = (llmId: string) => {
  if (!controlsDisabled.value) selectedModelId.value = llmId
  showModelSelector.value = false
}
const toggleTool = (toolId: string) => {
  if (controlsDisabled.value) return
  selectedTools.value = selectedTools.value.includes(toolId) ? selectedTools.value.filter(id => id !== toolId) : [...selectedTools.value, toolId]
}
const toggleMcp = (serverId: string) => {
  if (controlsDisabled.value) return
  selectedMcpServers.value = selectedMcpServers.value.includes(serverId) ? selectedMcpServers.value.filter(id => id !== serverId) : [...selectedMcpServers.value, serverId]
}
const toggleWebSearch = () => { if (!controlsDisabled.value) webSearchEnabled.value = !webSearchEnabled.value }
const toggleMcpSelector = () => { if (!controlsDisabled.value) showMcpSelector.value = !showMcpSelector.value }
const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as Node
  if (!toolDropdownRef.value?.contains(target)) showToolSelector.value = false
  if (!mcpDropdownRef.value?.contains(target)) showMcpSelector.value = false
  if (!modelDropdownRef.value?.contains(target)) showModelSelector.value = false
}

const fetchResources = async () => {
  modelsLoading.value = true
  mcpServersLoading.value = true
  resourceError.value = ''
  try {
    const responses = await Promise.all([getVisibleLLMsAPI(), getWorkspacePluginsAPI(), getMCPServersAPI(), getAgentsAPI()])
    if (disposed) return
    if (responses.some(response => response.data.status_code !== 200)) throw new Error('resources unavailable')
    const [modelsResponse, toolsResponse, mcpResponse, agentsResponse] = responses
    modelOptions.value = Object.values(modelsResponse.data.data || {}).flat().filter(m => (m.llm_type || '').toUpperCase() === 'LLM')
    plugins.value = toolsResponse.data.data || []
    mcpServers.value = mcpResponse.data.data || []
    agents.value = (agentsResponse.data.data || []).map(a => ({ ...a, agent_id: a.agent_id || (a as AgentResponse & { id?: string }).id || '' }))
    mcpServersError.value = false
    // Never replace a configuration restored from history, including an empty model.
    if (!selectedModelId.value && !historyLoaded) resetConfig()
  } catch {
    if (!disposed) resourceError.value = '加载模型、工具或智能体失败，请重试。'
  } finally {
    modelsLoading.value = false
    mcpServersLoading.value = false
  }
}
const fetchMcpServers = fetchResources

const markInterrupted = (message: ChatMessage, status: 'stopped' | 'error') => {
  message.status = status
  message.mcpToolCalls?.forEach(call => { if (call.status === 'START') call.status = 'ERROR' })
  message.agentEvents?.forEach(event => { if (event.status === 'START') event.status = 'ERROR' })
}
const stopGeneration = () => {
  activeController?.abort()
  activeController = null
  const message = messages.value[messages.value.length - 1]
  if (isGenerating.value && message?.role === 'assistant') markInterrupted(message, 'stopped')
  isGenerating.value = false
}
const updateMcpToolCall = (message: ChatMessage, event: McpToolEvent) => {
  const calls = message.mcpToolCalls || (message.mcpToolCalls = [])
  const existing = calls.find(call => call.id === event.id)
  if (existing) Object.assign(existing, event)
  else calls.push({ ...event, expanded: false })
  scrollToBottom()
}
const updateAgentEvent = (message: ChatMessage, event: AgentProgressEvent) => {
  const events = message.agentEvents || (message.agentEvents = [])
  const existing = events.find(item => item.title === event.title)
  if (existing) Object.assign(existing, event)
  else events.push({ ...event, expanded: false })
  scrollToBottom()
}

const handleSend = async () => {
  if (sendDisabled.value || isGenerating.value) return
  const query = inputMessage.value.trim()
  if (!query) { ElMessage.warning('请输入消息内容'); return }
  if (selectedMode.value === 'lingseek') {
    router.push({ name: 'taskGraphPage', query: {
      query, tools: JSON.stringify(selectedTools.value), webSearch: String(webSearchEnabled.value), mcp_servers: JSON.stringify(selectedMcpServers.value)
    } })
    return
  }
  if (!selectedModelId.value) { ElMessage.warning('请先选择模型'); return }
  const sessionId = currentSessionId.value || generateSessionId()
  currentSessionId.value = sessionId
  inputMessage.value = ''
  showModelSelector.value = showToolSelector.value = showMcpSelector.value = false
  isGenerating.value = true
  const controller = new AbortController()
  activeController = controller
  messages.value.push({ role: 'user', content: query })
  messages.value.push({ role: 'assistant', content: '', status: 'generating', mcpToolCalls: [], agentEvents: [], reasoning: '', reasoningExpanded: true })
  const message = messages.value[messages.value.length - 1]
  const isCurrent = () => !disposed && !controller.signal.aborted && activeController === controller && currentSessionId.value === sessionId
  scrollToBottom()
  const payload: WorkSpaceSimpleTask = {
    query, model_id: selectedModelId.value, plugins: [...selectedTools.value], mcp_servers: [...selectedMcpServers.value],
    agent_id: selectedAgentId.value || null, session_id: sessionId
  }
  try {
    await workspaceSimpleChatStreamAPI(payload,
      chunk => { if (isCurrent()) { message.content += chunk; scrollToBottom() } },
      undefined, undefined,
      event => { if (isCurrent()) updateMcpToolCall(message, event) },
      chunk => { if (isCurrent()) { message.reasoning = (message.reasoning || '') + chunk; scrollToBottom() } },
      { signal: controller.signal, onAgentEvent: event => { if (isCurrent()) updateAgentEvent(message, event) } }
    )
    if (isCurrent()) {
      message.status = 'complete'
      legacyConfig.value = false
      // Only successful, persisted sessions receive a bookmarkable URL.
      if (route.query.session_id !== sessionId) await router.replace({ name: 'workspaceDefaultPage', query: { session_id: sessionId, mode: 'normal' } })
      window.dispatchEvent(new CustomEvent('conversation-updated'))
    }
  } catch (error) {
    if (isCurrent()) {
      markInterrupted(message, 'error')
      ElMessage.error(error instanceof Error ? error.message : '对话失败，请稍后重试')
    }
  } finally {
    if (activeController === controller) { activeController = null; isGenerating.value = false }
  }
}
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); handleSend() }
}

const loadSessionHistory = async (sessionId: string) => {
  const version = ++loadVersion
  historyLoading.value = true
  historyError.value = ''
  legacyConfig.value = false
  try {
    const response = await getWorkspaceSessionInfoAPI(sessionId)
    if (disposed || version !== loadVersion) return
    const session = response.data.data
    if (response.data.status_code !== 200 || !session || session.agent !== 'simple') throw new Error('session unavailable')
    const contexts = Array.isArray(session.contexts) ? session.contexts : []
    messages.value = contexts.flatMap((context: any) => [
      { role: 'user', content: context.query || '' },
      { role: 'assistant', content: context.answer || '', status: 'complete', reasoning: context.reasoning || '', reasoningExpanded: false,
        mcpToolCalls: (context.mcp_tool_calls || []).map((call: McpToolEvent) => ({ ...call, expanded: false })),
        agentEvents: (context.agent_events || []).map((event: AgentProgressEvent) => ({ ...event, expanded: false })) }
    ])
    selectedMode.value = 'normal'
    const config = restoreConversationConfig(contexts)
    if (config) applyConfig(config)
    else { resetConfig(); legacyConfig.value = true }
    historyLoaded = !!config
    scrollToBottom()
  } catch {
    if (!disposed && version === loadVersion) historyError.value = '无法读取该会话，请重试或从列表重新选择。'
  } finally {
    if (version === loadVersion) historyLoading.value = false
  }
}
const resetConversation = async (sessionId?: string) => {
  stopGeneration()
  ++loadVersion
  currentSessionId.value = sessionId || generateSessionId()
  messages.value = []
  inputMessage.value = ''
  historyError.value = ''
  historyLoading.value = false
  historyLoaded = false
  legacyConfig.value = false
  selectedMode.value = sessionId ? 'normal' : route.query.mode === 'lingseek' ? 'lingseek' : 'normal'
  resetConfig()
  if (sessionId) await loadSessionHistory(sessionId)
  else if (typeof route.query.agent_id === 'string') {
    const agent = agents.value.find(item => item.agent_id === route.query.agent_id)
    if (agent) applyConfig(configFromAgent(agent))
    else selectedAgentId.value = route.query.agent_id
  }
}
onMounted(async () => {
  document.addEventListener('click', handleClickOutside)
  await fetchResources()
  if (!disposed) await resetConversation(typeof route.query.session_id === 'string' ? route.query.session_id : undefined)
})
onBeforeUnmount(() => {
  disposed = true
  ++loadVersion
  stopGeneration()
  document.removeEventListener('click', handleClickOutside)
})
watch(() => route.query.session_id, (newId, oldId) => {
  if (newId !== oldId && newId !== currentSessionId.value) resetConversation(typeof newId === 'string' ? newId : undefined)
})
watch(() => route.query.mode, mode => {
  if (!route.query.session_id && messages.value.length === 0) selectedMode.value = mode === 'lingseek' ? 'lingseek' : 'normal'
})
</script>

<template>
  <div class="chat-page" :class="{ 'chat-active': messages.length > 0 }">
    <div class="chat-container">
      <div class="conversation-mode-header">
        <span>会话模块</span>
        <span v-if="messages.length" class="current-mode">日常对话</span>
      </div>
      <div v-if="resourceError" class="conversation-notice" role="alert">
        {{ resourceError }} <button @click="fetchResources">重试</button>
      </div>
      <div v-if="historyError" class="conversation-notice" role="alert">
        {{ historyError }} <button @click="loadSessionHistory(currentSessionId)">重试</button>
      </div>
      <div v-if="historyLoading" class="conversation-notice" role="status">正在恢复会话…</div>
      <div v-if="legacyConfig" class="conversation-notice">这条旧记录未保存模型和工具配置，继续前请确认当前选择。</div>
      <!-- 欢迎区域（有对话时隐藏） -->
      <div v-if="messages.length === 0" class="welcome-section">
        <div class="avatar-wrapper">
          <img src="../../../assets/robot.svg" alt="智治" class="avatar" />
        </div>
        <h1 class="welcome-title">今天想做些什么？</h1>
        <p class="welcome-subtitle">{{ selectedMode === 'normal' ? '选择通用助手或已有智能体，开始日常对话。' : '描述目标，生成指导手册并查看任务执行流程。' }}</p>
      </div>

      <!-- 模式选择（有对话时隐藏） -->
      <div v-if="messages.length === 0 && !route.query.session_id" class="mode-selector" aria-label="会话模式">
        <button
          v-for="mode in modes"
          :key="mode.id"
          :class="['mode-btn', { active: selectedMode === mode.id }]"
          :disabled="controlsDisabled"
          @click="selectMode(mode.id)"
        >
          <span class="mode-icon">{{ mode.icon }}</span>
          <span class="mode-label">{{ mode.label }}</span>
        </button>
      </div>

      <!-- 对话历史（有对话时显示在上方） -->
      <div v-if="messages.length > 0" class="chat-conversation" ref="chatConversationRef">
        <div v-for="(msg, idx) in messages" :key="idx" class="message-group">
          <!-- User Message -->
          <div v-if="msg.role === 'user'" class="user-message">
            <div class="message-content">
              <span>{{ msg.content }}</span>
            </div>
            <img :src="userStore.userInfo?.avatar || userAvatar" alt="User Avatar" class="avatar" @error="handleAvatarError" />
          </div>
          
          <!-- AI Message -->
          <div v-if="msg.role === 'assistant'" class="ai-message">
            <img :src="robotAvatar" alt="AI Avatar" class="avatar" />
            <div class="message-content">
              <div v-if="msg.reasoning" class="reasoning-panel">
                <button type="button" class="reasoning-header" @click="msg.reasoningExpanded = !msg.reasoningExpanded">
                  <span class="reasoning-icon">✦</span>
                  <span class="reasoning-title">思考过程</span>
                  <span class="reasoning-status">{{ msg.status === 'stopped' ? '已停止' : msg.status === 'error' ? '生成失败' : isGenerating && idx === messages.length - 1 && !msg.content ? '思考中' : '已完成' }}</span>
                  <span class="reasoning-toggle">{{ msg.reasoningExpanded ? '收起' : '展开' }}</span>
                </button>
                <div v-if="msg.reasoningExpanded" class="reasoning-content">{{ msg.reasoning }}</div>
              </div>
              <div v-if="msg.agentEvents?.length" class="agent-progress-events">
                <details v-for="(event, eventIndex) in msg.agentEvents" :key="eventIndex" class="agent-progress-event">
                  <summary>{{ event.title }} · {{ event.status === 'START' ? '执行中' : event.status === 'END' ? '已完成' : '已中断或失败' }}</summary>
                  <p>{{ event.message }}</p>
                </details>
              </div>
              <div v-if="msg.mcpToolCalls?.length" class="mcp-tool-events">
                <div v-for="call in msg.mcpToolCalls" :key="call.id" class="mcp-tool-event" :class="call.status.toLowerCase()">
                  <button type="button" class="mcp-tool-event-header" @click="call.expanded = !call.expanded">
                    <span class="mcp-tool-event-icon">{{ call.status === 'START' ? '◌' : call.status === 'END' ? '✓' : '!' }}</span>
                    <span class="mcp-tool-event-name">MCP 工具：{{ call.tool_name }}</span>
                    <span class="mcp-tool-event-status">{{ call.status === 'START' ? '调用中' : call.status === 'END' ? '已完成' : '失败' }}</span>
                    <span class="mcp-tool-event-toggle">{{ call.expanded ? '收起' : '展开' }}</span>
                  </button>
                  <div v-if="call.arguments && Object.keys(call.arguments).length" class="mcp-tool-event-arguments">
                    调用参数：{{ formatMcpArguments(call.arguments) }}
                  </div>
                  <div v-if="call.expanded" class="mcp-tool-event-detail">
                    <div>MCP 服务器：{{ call.server_name }}</div>
                    <div>工具描述：{{ call.description || '暂无描述' }}</div>
                  </div>
                </div>
              </div>
              <!-- 加载转圈器 - 仅在内容为空且正在生成时显示 -->
              <div v-if="!msg.content && isGenerating && idx === messages.length - 1" class="loading-spinner-container">
                <div class="loading-spinner"></div>
                <span class="loading-text">AI正在思考中...</span>
              </div>
              <!-- 实际内容 - 有内容时显示 -->
              <MdPreview v-if="msg.content" :editorId="'workspace-ai-' + idx" :modelValue="msg.content" />
              <p v-if="msg.status === 'stopped' || msg.status === 'error'" class="message-status" role="status">
                {{ msg.status === 'stopped' ? '已停止生成，本轮可能未保存。' : '本轮生成失败，请重试。' }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域（固定在底部） -->
      <div class="input-section" :class="{ 'input-fixed': messages.length > 0 }">
        <div v-if="selectedMode === 'normal'" class="agent-config-row">
          <label for="conversation-agent">智能体</label>
          <select id="conversation-agent" :value="selectedAgentId" :disabled="controlsDisabled || !!historyError" @change="selectAgent">
            <option value="">通用助手</option>
            <option v-if="selectedAgentMissing" :value="selectedAgentId" disabled>原智能体已不可用</option>
            <option v-for="agent in agents" :key="agent.agent_id" :value="agent.agent_id">{{ agent.name }}</option>
          </select>
          <span class="agent-config-hint">{{ selectedAgentId ? '已带入智能体配置，调整仅用于当前会话' : '自由选择模型、工具和 MCP' }}</span>
        </div>
        <p v-if="configurationIssue" class="conversation-notice" role="alert">{{ configurationIssue }}</p>
        <div class="input-wrapper" :class="{ 'lingseek-glow': selectedMode === 'lingseek' }">
          <textarea
            v-model="inputMessage"
            placeholder="描述你想完成的任务…"
            class="message-input"
            rows="4"
            :disabled="historyLoading || !!historyError"
            @keydown="handleKeydown"
          ></textarea>
          
          <!-- 底部控制栏 -->
          <div class="input-footer">
            <div class="footer-left" :class="{ 'controls-disabled': controlsDisabled || !!historyError }" :aria-disabled="controlsDisabled || !!historyError">
              <!-- 模型选择（仅日常模式显示） -->
              <div v-if="selectedMode === 'normal'" class="selector-dropdown" ref="modelDropdownRef">
                <div 
                  :class="['selector-item', { open: showModelSelector }]"
                  @click="showModelSelector = !showModelSelector"
                >
                  <img src="../../../assets/model.svg" alt="模型" class="selector-icon-img" />
                  <span class="selector-text">{{ selectedModel || (modelsLoading ? '加载中...' : '选择模型') }}</span>
                  <span class="selector-arrow">▲</span>
                </div>
                
                <!-- 模型下拉菜单 -->
                <transition name="dropdown">
                  <div v-if="showModelSelector" class="dropdown-menu model-menu">
                    <div v-if="modelsLoading" class="dropdown-empty">
                      <span class="empty-icon">⏳</span>
                      <span class="empty-text">正在加载模型...</span>
                    </div>
                    <div v-else-if="modelOptions.length === 0" class="dropdown-empty">
                      <img src="../../../assets/model.svg" alt="模型" class="empty-icon-img" />
                      <span class="empty-text">暂无可用模型</span>
                    </div>
                    <div
                      v-for="m in modelOptions"
                      :key="m.llm_id"
                      :class="['dropdown-item', { selected: selectedModelId === m.llm_id }]"
                      @click="selectModel(m.llm_id)"
                    >
                      <div class="item-left">
                        <div class="item-icon-wrapper">
                          <img src="../../../assets/model.svg" alt="模型" class="item-icon-img" />
                        </div>
                        <div class="item-content">
                          <div class="item-text">{{ m.model }}</div>
                        </div>
                      </div>
                      <div v-if="selectedModelId === m.llm_id" class="item-check-wrapper">
                        <span class="item-check">✓</span>
                      </div>
                    </div>
                  </div>
                </transition>
              </div>

              <!-- 联网搜索（仅灵寻模式显示） -->
              <div v-if="selectedMode === 'lingseek'" class="selector-dropdown">
                <div 
                  :class="['selector-item', { active: webSearchEnabled }]"
                  @click="toggleWebSearch"
                >
                  <img src="../../../assets/web-search.svg" alt="联网搜索" class="selector-icon-img" />
                  <span class="selector-text">联网搜索</span>
                  <span v-if="webSearchEnabled" class="selector-check">✓</span>
                </div>
              </div>
              
              <!-- 工具选择 -->
              <div class="selector-dropdown" ref="toolDropdownRef">
                <div 
                  class="selector-item"
                  @click="showToolSelector = !showToolSelector"
                >
                  <img src="../../../assets/plugin.svg" alt="工具" class="selector-icon-img" />
                  <span class="selector-text">
                    {{ selectedTools.length > 0 ? `已选 ${selectedTools.length} 个` : '选择工具' }}
                  </span>
                  <span class="selector-arrow">▲</span>
                </div>
                
                <!-- 工具下拉菜单 -->
                <transition name="dropdown">
                  <div v-if="showToolSelector" class="dropdown-menu tool-menu">
                    <!-- 标题 -->
                    <div class="dropdown-header">
                      <span class="header-title">选择工具</span>
                      <span class="header-count">{{ plugins.length }} 个可用</span>
                    </div>

                    <!-- 工具列表 -->
                    <div class="dropdown-list">
                      <div v-if="plugins.length === 0" class="dropdown-empty">
                        <img src="../../../assets/plugin.svg" alt="工具" class="empty-icon-img" />
                        <span class="empty-text">暂无可用工具</span>
                      </div>
                      <div
                        v-for="plugin in plugins"
                        :key="plugin.id || plugin.tool_id"
                        :class="['dropdown-item', { selected: selectedTools.includes(plugin.id || plugin.tool_id) }]"
                        @click="toggleTool(plugin.id || plugin.tool_id)"
                      >
                        <div class="item-left">
                          <div class="item-icon-wrapper">
                            <img 
                              v-if="plugin.logo_url" 
                              :src="plugin.logo_url" 
                              :alt="plugin.display_name"
                              class="item-icon-img"
                            />
                            <img v-else src="../../../assets/plugin.svg" alt="工具" class="item-icon-img" />
                          </div>
                          <div class="item-content">
                            <div class="item-text">{{ plugin.display_name }}</div>
                            <div class="item-desc">{{ plugin.description || '暂无描述' }}</div>
                          </div>
                        </div>
                        <div 
                          v-if="selectedTools.includes(plugin.id || plugin.tool_id)" 
                          class="item-check-wrapper"
                        >
                          <span class="item-check">✓</span>
                        </div>
                      </div>
                    </div>

                    <!-- 底部操作栏 -->
                    <div v-if="selectedTools.length > 0" class="dropdown-footer">
                      <button 
                        class="clear-btn"
                        @click.stop="selectedTools = []"
                      >
                        <span>清空</span>
                      </button>
                      <div class="selected-info">
                        <span class="selected-count">已选 {{ selectedTools.length }} 个工具</span>
                      </div>
                    </div>
                  </div>
                </transition>
              </div>

              <!-- MCP 服务器选择（紧跟工具选择后） -->
              <div class="selector-dropdown" ref="mcpDropdownRef">
                <div 
                  class="selector-item"
                  @click="toggleMcpSelector"
                >
                  <img src="../../../assets/mcp.svg" alt="MCP" class="selector-icon-img" />
                  <span class="selector-text">
                    {{ selectedMcpServers.length > 0 ? `已选 ${selectedMcpServers.length} 个MCP` : '选择MCP' }}
                  </span>
                  <span class="selector-arrow">▲</span>
                </div>
                
                <!-- MCP 下拉菜单 -->
                <transition name="dropdown">
                  <div v-if="showMcpSelector" class="dropdown-menu tool-menu">
                    <!-- 标题 -->
                    <div class="dropdown-header">
                      <span class="header-title">选择MCP服务器</span>
                      <span class="header-count">{{ mcpServersLoading ? '加载中…' : `${mcpServers.length} 个可用` }}</span>
                    </div>

                    <!-- 列表 -->
                    <div class="dropdown-list">
                      <div v-if="mcpServersLoading" class="dropdown-empty">
                        <span class="empty-text">正在加载MCP服务器…</span>
                      </div>
                      <div v-else-if="mcpServersError" class="dropdown-empty">
                        <span class="empty-text">加载MCP服务器失败</span>
                        <button class="clear-btn" @click.stop="fetchMcpServers">重试</button>
                      </div>
                      <template v-else>
                      <div v-if="mcpServers.length === 0" class="dropdown-empty">
                        <img src="../../../assets/mcp.svg" alt="MCP" class="empty-icon-img" />
                        <span class="empty-text">暂无可用MCP服务器</span>
                      </div>
                      <div
                        v-for="mcp in mcpServers"
                        :key="mcp.mcp_server_id"
                        :class="['dropdown-item', { selected: selectedMcpServers.includes(mcp.mcp_server_id) }]"
                        @click="toggleMcp(mcp.mcp_server_id)"
                      >
                        <div class="item-left">
                          <div class="item-icon-wrapper">
                            <img 
                              v-if="mcp.logo_url" 
                              :src="mcp.logo_url" 
                              :alt="mcp.server_name"
                              class="item-icon-img"
                            />
                            <img v-else src="../../../assets/mcp.svg" alt="MCP" class="item-icon-img" />
                          </div>
                          <div class="item-content">
                            <div class="item-text">{{ mcp.server_name }}</div>
                          </div>
                        </div>
                        <div 
                          v-if="selectedMcpServers.includes(mcp.mcp_server_id)" 
                          class="item-check-wrapper"
                        >
                          <span class="item-check">✓</span>
                        </div>
                      </div>
                      </template>
                    </div>

                    <!-- 底部操作栏 -->
                    <div v-if="selectedMcpServers.length > 0" class="dropdown-footer">
                      <button 
                        class="clear-btn"
                        @click.stop="selectedMcpServers = []"
                      >
                        <span>清空</span>
                      </button>
                      <div class="selected-info">
                        <span class="selected-count">已选 {{ selectedMcpServers.length }} 个MCP</span>
                      </div>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
            
            <div class="footer-right">
              <!-- 发送按钮 -->
              <button v-if="isGenerating" class="send-btn stop-btn" aria-label="停止生成" title="停止生成" @click="stopGeneration">■</button>
              <button v-else class="send-btn" :class="{ 'btn-disabled': sendDisabled }" :disabled="sendDisabled" aria-label="发送消息" title="发送消息" @click="handleSend">
                <span>➤</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.conversation-mode-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 16px 20px;
  color: #475569;
  font-size: 14px;
  flex-shrink: 0;
  .current-mode { color: #6366f1; }
}
.conversation-notice {
  color: #92400e;
  background: #fffbeb;
  border-radius: 8px;
  padding: 10px 14px;
  margin: 8px 0;
  font-size: 13px;
  button { border: 0; background: none; color: #4338ca; cursor: pointer; }
}
.agent-config-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0 auto 10px;
  max-width: 900px;
  font-size: 13px;
  color: #475569;
  select { max-width: 260px; padding: 7px 12px; border: 1px solid #dbe1ea; border-radius: 8px; background: white; color: #334155; }
  .agent-config-hint { color: #64748b; font-size: 12px; }
}
.controls-disabled { pointer-events: none; opacity: .6; }
.agent-progress-event { padding: 9px 12px; margin: 6px 0; border-radius: 8px; background: #eef2ff; color: #475569; font-size: 13px; summary { cursor: pointer; } }
.message-status { font-size: 13px; color: #92400e; }
.chat-page {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  background: linear-gradient(180deg, #fafbfc 0%, #ffffff 100%);
  padding: 0;
  overflow-y: auto;

  &.chat-active {
    padding: 0;
    overflow: hidden;
    background-color: #f7f8fa;
  }
}

.chat-container {
  max-width: 820px;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px 40px;

  .chat-active & {
    max-width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 0;
  }
}

.welcome-section {
  text-align: center;
  margin-bottom: 40px;
  animation: fadeInUp 0.6s ease;

  .avatar-wrapper {
    margin-bottom: 20px;
    display: flex;
    justify-content: center;
    position: relative;

    .avatar {
      width: 120px;
      height: 120px;
      object-fit: contain;
      transition: all 0.3s ease;
      filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.08));

      &:hover {
        transform: scale(1.05);
        filter: drop-shadow(0 6px 16px rgba(0, 0, 0, 0.12));
      }
    }
  }

  .welcome-title {
    font-size: 32px;
    font-weight: 700;
    background: linear-gradient(135deg, #1f2937 0%, #4b5563 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 12px 0;
    letter-spacing: -0.5px;
  }

  .welcome-subtitle {
    font-size: 15px;
    color: #6b7280;
    margin: 0;
    line-height: 1.7;
    max-width: 500px;
    margin: 0 auto;
  }
}

.mode-selector {
  display: flex;
  gap: 14px;
  margin-bottom: 36px;
  animation: fadeInUp 0.6s ease 0.1s both;

  .mode-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 24px;
    border: 2px solid #e5e7eb;
    border-radius: 24px;
    background: white;
    color: #6b7280;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);

    .mode-icon {
      font-size: 18px;
      transition: transform 0.3s ease;
    }

    .mode-label {
      font-weight: 600;
    }

    &:hover {
      border-color: #667eea;
      background: #f8f9ff;
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);

      .mode-icon {
        transform: scale(1.1);
      }
    }

    &.active {
      border-color: #667eea;
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      color: #667eea;
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
      transform: translateY(-2px);

      .mode-icon {
        transform: scale(1.15);
      }
    }
  }
}

// 动画
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes rotate {
  from {
    transform: translate(-50%, -50%) rotate(0deg);
  }
  to {
    transform: translate(-50%, -50%) rotate(360deg);
  }
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0) translateY(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1.2) translateY(-8px);
    opacity: 1;
  }
}

// 灵寻模式输入框外发光“呼吸”动画（淡蓝色，颜色不变，仅强弱变化）
@keyframes lingseek-breath {
  0%, 100% {
    box-shadow:
      0 0 0 2px rgba(102, 126, 234, 0.12),
      0 0 24px 10px rgba(102, 126, 234, 0.14);
  }
  50% {
    box-shadow:
      0 0 0 3px rgba(102, 126, 234, 0.22),
      0 0 44px 18px rgba(102, 126, 234, 0.22);
  }
}

@keyframes lingseek-breath-strong {
  0%, 100% {
    box-shadow:
      0 0 0 3px rgba(102, 126, 234, 0.20),
      0 0 36px 14px rgba(102, 126, 234, 0.24);
  }
  50% {
    box-shadow:
      0 0 0 4px rgba(102, 126, 234, 0.30),
      0 0 60px 24px rgba(102, 126, 234, 0.30);
  }
}

// 移除彩虹动画（不再需要）

.input-section {
  width: 100%;
  max-width: 800px;
  animation: fadeInUp 0.6s ease 0.2s both;

  &.input-fixed {
    max-width: 100%;
    padding: 10px 20px 20px 20px;
    background: #f7f8fa;
    animation: none;

    .input-wrapper {
      max-width: 900px;
      margin: 0 auto;
    }
  }

  .input-wrapper {
    background: #ffffff;
    border: 2px solid #e5e7eb;
    border-radius: 20px;
    padding: 16px 20px;
    transition: all 0.3s ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
    position: relative;
    z-index: 1;

    &.lingseek-glow {
      border-color: rgba(102, 126, 234, 0.35);
      box-shadow:
        0 0 0 2px rgba(102, 126, 234, 0.12),
        0 0 16px 6px rgba(102, 126, 234, 0.14);
      animation: lingseek-breath 2.8s ease-in-out infinite;

      &:focus-within {
        border-color: rgba(102, 126, 234, 0.55);
        animation: lingseek-breath-strong 2.2s ease-in-out infinite;
        transform: translateY(-2px);
      }
    }

    &:focus-within {
      border-color: #667eea;
      box-shadow: 0 6px 24px rgba(102, 126, 234, 0.15);
      transform: translateY(-2px);
    }

    .message-input {
      width: 100%;
      border: none;
      background: transparent;
      font-size: 15px;
      line-height: 1.6;
      color: #1f2937;
      resize: none;
      outline: none;
      font-family: inherit;
      min-height: 45px;
      margin-bottom: 12px;

      &::placeholder {
        color: #9ca3af;
      }
    }

    .input-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .footer-left {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;

          .selector-dropdown {
          position: relative;

          .selector-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 14px;
            background: #f8f9fa;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            font-size: 13px;
            color: #4b5563;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;

            .selector-icon-img {
              width: 20px;
              height: 20px;
              object-fit: contain;
              display: inline-block;
            }

            .selector-text {
              font-weight: 500;
            }

            .selector-arrow {
              font-size: 10px;
              opacity: 0.5;
              transition: transform 0.2s ease;
            }

            &.open {
              .selector-arrow {
                transform: rotate(180deg);
              }
            }

            .selector-check {
              font-size: 14px;
              color: #667eea;
              font-weight: 600;
            }

            &:hover {
              border-color: #667eea;
              background: #f0f4ff;
              color: #667eea;
            }

            &.active {
              background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
              border-color: #667eea;
              color: #667eea;
              box-shadow: 0 2px 6px rgba(102, 126, 234, 0.15);
            }

            &:active {
              transform: scale(0.98);
            }
          }

          .dropdown-menu {
            position: absolute;
            bottom: calc(100% + 8px);
            left: 0;
            min-width: 200px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.15);
            z-index: 1000;
            max-height: 320px;
            overflow: hidden;
            display: flex;
            flex-direction: column;

            &.tool-menu {
              min-width: 360px;
              max-height: 450px;
            }

            // 模型下拉尺寸与工具列表保持一致
            &.model-menu {
              min-width: 180px;
              max-height: 450px;

              .dropdown-item {
                .item-content {
                  .item-text {
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                  }
                }
              }
            }

            .dropdown-header {
              display: flex;
              justify-content: space-between;
              align-items: center;
              padding: 12px 16px;
              background: linear-gradient(135deg, #f8f9fa 0%, #f0f2f5 100%);
              border-bottom: 1px solid #e5e7eb;

              .header-title {
                font-size: 14px;
                font-weight: 600;
                color: #1f2937;
              }

              .header-count {
                font-size: 12px;
                color: #6b7280;
                background: white;
                padding: 2px 8px;
                border-radius: 10px;
                border: 1px solid #e5e7eb;
              }
            }

            .dropdown-list {
              flex: 1;
              overflow-y: auto;
              padding: 8px;

              &::-webkit-scrollbar {
                width: 8px;
              }

              &::-webkit-scrollbar-track {
                background: transparent;
              }

              &::-webkit-scrollbar-thumb {
                background: #e0e0e0;
                border-radius: 4px;

                &:hover {
                  background: #bdbdbd;
                }
              }
            }

            .dropdown-empty {
              padding: 48px 20px;
              text-align: center;
              color: #9ca3af;
              display: flex;
              flex-direction: column;
              align-items: center;
              gap: 12px;

              .empty-icon {
                font-size: 48px;
                opacity: 0.3;
              }

              .empty-icon-img {
                width: 48px;
                height: 48px;
                opacity: 0.35;
                object-fit: contain;
              }

              .empty-text {
                font-size: 14px;
                color: #6b7280;
              }
            }

            .dropdown-item {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 12px;
              padding: 14px 12px;
              border-radius: 10px;
              cursor: pointer;
              transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
              margin-bottom: 4px;
              border: 2px solid transparent;
              background: #fafafa;

              .item-left {
                display: flex;
                align-items: center;
                gap: 12px;
                flex: 1;
                min-width: 0;
              }

              .item-icon-wrapper {
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
                border-radius: 10px;
                flex-shrink: 0;
                transition: all 0.3s ease;
                overflow: hidden;

                .item-icon-img {
                  width: 100%;
                  height: 100%;
                  object-fit: cover;
                }

                .item-icon {
                  font-size: 20px;
                }
              }

              .item-content {
                flex: 1;
                min-width: 0;

                .item-text {
                  font-size: 15px;
                  font-weight: 600;
                  color: #1f2937;
                  margin-bottom: 4px;
                  line-height: 1.3;
                }

                .item-desc {
                  font-size: 12px;
                  color: #6b7280;
                  overflow: hidden;
                  text-overflow: ellipsis;
                  display: -webkit-box;
                  -webkit-line-clamp: 2;
                  line-clamp: 2;
                  -webkit-box-orient: vertical;
                  line-height: 1.5;
                }
              }

              .item-check-wrapper {
                width: 28px;
                height: 28px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 50%;
                flex-shrink: 0;
                box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);

                .item-check {
                  font-size: 16px;
                  color: white;
                  font-weight: 700;
                }
              }

              &:hover {
                background: #f5f7fa;
                transform: translateX(2px);
                border-color: #e5e7eb;

                .item-icon-wrapper {
                  background: linear-gradient(135deg, #e5e7eb 0%, #d1d5db 100%);
                  transform: scale(1.05);
                }
              }

              &.selected {
                background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
                border-color: #667eea;
                box-shadow: 0 2px 8px rgba(102, 126, 234, 0.12);

                .item-icon-wrapper {
                  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
                  
                  .item-icon-img {
                    filter: brightness(1.2);
                  }

                  .item-icon {
                    filter: brightness(0) invert(1);
                  }
                }

                .item-text {
                  color: #667eea;
                }
              }

              &:active {
                transform: scale(0.98) translateX(2px);
              }
            }

            .dropdown-footer {
              display: flex;
              justify-content: space-between;
              align-items: center;
              padding: 12px 16px;
              border-top: 2px solid #f0f0f0;
              background: linear-gradient(135deg, #fafbfc 0%, #f5f7fa 100%);

              .clear-btn {
                padding: 8px 16px;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                font-size: 13px;
                color: #6b7280;
                cursor: pointer;
                transition: all 0.25s ease;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 6px;

                &:hover {
                  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
                  border-color: #ef4444;
                  color: #dc2626;
                  transform: translateY(-1px);
                  box-shadow: 0 2px 6px rgba(239, 68, 68, 0.2);
                }

                &:active {
                  transform: translateY(0);
                }
              }

              .selected-info {
                display: flex;
                align-items: center;
                gap: 8px;

                .selected-count {
                  font-size: 13px;
                  color: #667eea;
                  font-weight: 600;
                  padding: 4px 12px;
                  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
                  border-radius: 12px;
                  border: 1px solid #667eea;
                }
              }
            }
          }
        }
      }

      .footer-right {
        display: flex;
        gap: 10px;
        align-items: center;

        .icon-btn {
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #f8f9fa;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 18px;

          &:hover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: translateY(-1px);
          }

          &:active {
            transform: translateY(0);
          }
        }

        .hidden-file-input {
          display: none;
        }

        .upload-icon {
          width: 18px;
          height: 18px;
          object-fit: contain;
          display: block;
        }

        .send-btn {
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
          border: none;
          border-radius: 8px;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 16px;
          box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);

          &:hover:not(.btn-disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(59, 130, 246, 0.35);
          }

          &:active:not(.btn-disabled) {
            transform: translateY(0);
          }

          &.btn-disabled {
            background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
            cursor: not-allowed;
            opacity: 0.6;
          }

          .loading-spinner {
            animation: spin 1s linear infinite;
          }
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      }
    }
  }
}

.chat-conversation {
  flex: 1;
  padding: 0;
  overflow-y: auto;
  width: 100%;
  background-color: #f7f8fa;
  scroll-behavior: smooth;  // 平滑滚动
  
  .message-group {
    margin-bottom: 20px;
    padding: 0 20px;
    
    &:first-child {
      padding-top: 20px;
    }
  }

  .ai-message {
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;

    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin-right: 15px;
      flex-shrink: 0;
      border: 1px solid #eee;
    }

    .message-content {
      background-color: #ffffff;
      border-radius: 18px;
      padding: 12px 18px;
      max-width: 70%;
      color: #333;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
      word-break: break-word;

      .reasoning-panel {
        margin-bottom: 10px;
        border: 1px solid #dbeafe;
        border-radius: 10px;
        background: #f8fbff;
      }

      .reasoning-header {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        padding: 9px 11px;
        border: 0;
        background: transparent;
        color: #334155;
        text-align: left;
        cursor: pointer;
        font-size: 13px;
      }

      .reasoning-icon { color: #6366f1; }
      .reasoning-title { flex: 1; font-weight: 600; }
      .reasoning-status { color: #64748b; white-space: nowrap; }
      .reasoning-toggle { color: #3b82f6; white-space: nowrap; }
      .reasoning-content {
        max-height: 240px;
        overflow-y: auto;
        padding: 0 11px 10px;
        color: #475569;
        font-size: 13px;
        line-height: 1.6;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }

      .mcp-tool-events {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 10px;
      }

      .mcp-tool-event {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #f8fafc;
        font-size: 13px;

        &.end .mcp-tool-event-icon { color: #16a34a; }
        &.error .mcp-tool-event-icon { color: #dc2626; }
        &.start .mcp-tool-event-icon { color: #3b82f6; }
      }

      .mcp-tool-event-header {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        padding: 9px 11px;
        border: 0;
        background: transparent;
        color: #334155;
        text-align: left;
        cursor: pointer;
      }

      .mcp-tool-event-name {
        flex: 1;
        min-width: 0;
        overflow-wrap: anywhere;
        font-weight: 600;
      }

      .mcp-tool-event-status { color: #64748b; white-space: nowrap; }
      .mcp-tool-event-toggle { color: #3b82f6; white-space: nowrap; }
      .mcp-tool-event-arguments {
        padding: 0 11px 9px 30px;
        color: #475569;
        overflow-wrap: anywhere;
      }
      .mcp-tool-event-detail {
        padding: 0 11px 10px 30px;
        color: #64748b;
        overflow-wrap: anywhere;
      }

      // 加载转圈器样式
      .loading-spinner-container {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 4px 0;
        color: #6b7280;
        font-size: 14px;

        .loading-spinner {
          width: 16px;
          height: 16px;
          border: 2px solid #d1d5db;
          border-top: 2px solid transparent;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        .loading-text {
          font-weight: 500;
          color: #9ca3af;
        }
      }
    }
  }

  .user-message {
    display: flex;
    justify-content: flex-end;
    align-items: flex-start;

    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin-left: 12px;
      flex-shrink: 0;
      border: 1px solid #eee;
    }

    .message-content {
      display: flex;
      align-items: center;
      background: linear-gradient(135deg, #6e8efb, #a777e3);
      color: white;
      border-radius: 18px;
      padding: 12px 18px;
      max-width: 70%;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
  }
}

// 下拉菜单动画（向上展开）
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.dropdown-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

// Override MdPreview background
:deep(.md-editor-preview-wrapper) {
    background-color: transparent !important;
}

@media (max-width: 768px) {
  .chat-page {
    padding: 40px 16px 20px;
  }

  .welcome-section {
    margin-bottom: 32px;

    .avatar-wrapper {
      .avatar {
        width: 80px;
        height: 80px;
      }
    }

    .welcome-title {
      font-size: 26px;
    }

    .welcome-subtitle {
      font-size: 14px;
    }
  }

  .mode-selector {
    margin-bottom: 28px;
    
    .mode-btn {
      padding: 10px 18px;
      font-size: 13px;
    }
  }

  .input-section {
    .input-wrapper {
      padding: 18px;

      .input-footer {
        .footer-left {
          flex-wrap: wrap;
        }
      }
    }
  }
}
</style>
