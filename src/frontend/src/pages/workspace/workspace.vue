<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getWorkspaceSessionsAPI, deleteWorkspaceSessionAPI } from '../../apis/workspace'
import { getDialogListAPI, deleteDialogAPI } from '../../apis/history'
import {
  normalizeConversationHistory, mergeConversationHistory, conversationLocation, selectedConversationKey,
  type ConversationEntry, type ConversationMode, type ConversationSource,
} from '../../utils/conversation-history'

const router = useRouter()
const route = useRoute()
const workspaceSessions = ref<ConversationEntry[]>([])
const agentDialogs = ref<ConversationEntry[]>([])
const sourceErrors = ref<ConversationSource[]>([])
const loading = ref(false)
const filter = ref<'all' | ConversationMode>('all')
const openSessionActions = ref('')
const deletingKeys = ref<string[]>([])
const selectedSession = computed(() => selectedConversationKey(route.query))
const sessions = computed(() => mergeConversationHistory(workspaceSessions.value, agentDialogs.value))
const filteredSessions = computed(() => sessions.value.filter(session => filter.value === 'all' || session.mode === filter.value))
const filters = [{ id: 'all', label: '全部' }, { id: 'normal', label: '日常' }, { id: 'lingseek', label: '灵寻' }] as const
let requestVersion = 0
let newConversation = Date.now()

const fetchSessions = async () => {
  const version = ++requestVersion
  loading.value = true
  const results = await Promise.allSettled([getWorkspaceSessionsAPI(), getDialogListAPI()])
  if (version !== requestVersion) return
  const errors: ConversationSource[] = []
  results.forEach((result, index) => {
    const source = index === 0 ? 'workspace' : 'dialog'
    if (result.status === 'fulfilled' && result.value.data.status_code === 200 && Array.isArray(result.value.data.data)) {
      const entries = normalizeConversationHistory(result.value.data.data, source)
      if (source === 'workspace') workspaceSessions.value = entries
      else agentDialogs.value = entries
    } else {
      errors.push(source)
    }
  })
  sourceErrors.value = errors
  loading.value = false
}

const startConversation = () => {
  const mode = route.query.mode === 'lingseek' ? 'lingseek' : 'normal'
  router.push({ name: 'workspaceDefaultPage', query: { mode, new: String(++newConversation) } })
}

const deleteSession = async (session: ConversationEntry) => {
  if (deletingKeys.value.includes(session.key)) return
  deletingKeys.value.push(session.key)
  try {
    const response = session.source === 'dialog'
      ? await deleteDialogAPI(session.id)
      : await deleteWorkspaceSessionAPI(session.id)
    if (response.data.status_code !== 200) throw new Error('Delete failed')
    workspaceSessions.value = workspaceSessions.value.filter(item => item.key !== session.key)
    agentDialogs.value = agentDialogs.value.filter(item => item.key !== session.key)
    if (selectedSession.value === session.key) startConversation()
    ElMessage.success('会话删除成功')
    await fetchSessions()
  } catch {
    ElMessage.error('删除会话失败，请重试')
  } finally {
    deletingKeys.value = deletingKeys.value.filter(key => key !== session.key)
  }
}

const selectSession = (session: ConversationEntry) => router.push(conversationLocation(session))

// 旧智能体对话切换时重新挂载，隔离它的共享消息状态与流连接。
// 日常页自行处理 session_id 变化；首次生成的 ID 写回 URL 时不能中断流。
const pageKey = computed(() => route.name === 'chatPage'
  ? `dialog:${String(route.query.dialog_id || '')}`
  : `${String(route.name)}:${String(route.query.mode || 'normal')}:${String(route.query.new || '')}`)

watch(() => route.fullPath, () => { openSessionActions.value = '' })
onMounted(() => {
  fetchSessions()
  window.addEventListener('conversation-updated', fetchSessions)
})
onBeforeUnmount(() => {
  ++requestVersion
  window.removeEventListener('conversation-updated', fetchSessions)
})
</script>

<template>
  <div class="workspace-container">
    <div class="workspace-main">
      <aside class="sidebar" aria-label="会话历史">
        <div class="create-section">
          <div class="module-title">会话模块</div>
          <button @click="startConversation" class="create-btn-native">
            <span class="btn-content"><span class="icon">＋</span><span>新会话</span></span>
          </button>
        </div>
        <div class="history-filters" aria-label="筛选会话">
          <button v-for="item in filters" :key="item.id" :class="{ active: filter === item.id }"
            :aria-pressed="filter === item.id" @click="filter = item.id">{{ item.label }}</button>
        </div>
        <div v-if="sourceErrors.length" class="history-error" role="status">
          <span>{{ sourceErrors.length === 2 ? '会话记录加载失败' : '部分会话记录加载失败' }}</span>
          <button @click="fetchSessions" :disabled="loading">重试</button>
        </div>
        <div class="session-list" :aria-busy="loading">
          <div class="session-list-label">最近会话</div>
          <div v-if="loading && !sessions.length" class="empty-state">正在加载会话列表…</div>
          <div v-else-if="!filteredSessions.length && !sourceErrors.length" class="empty-state">
            {{ sessions.length ? '该模式暂无会话' : '暂无会话记录' }}
          </div>
          <div v-for="session in filteredSessions" :key="session.key"
            :class="['session-card', { active: selectedSession === session.key }]"
            role="button" tabindex="0" :aria-current="selectedSession === session.key ? 'true' : undefined"
            @click="selectSession(session)" @keydown.enter.self="selectSession(session)"
            @keydown.space.self.prevent="selectSession(session)">
            <div class="session-info">
              <div class="session-title" :title="session.title">{{ session.title }}</div>
              <span class="session-mode" :class="session.mode">{{ session.mode === 'lingseek' ? '灵寻' : '日常' }}</span>
            </div>
            <div class="session-actions" :class="{ 'is-open': openSessionActions === session.key }" @click.stop @keydown.stop>
              <el-dropdown trigger="click" popper-class="workspace-session-menu" @command="deleteSession(session)"
                @visible-change="openSessionActions = $event ? session.key : ''">
                <button class="session-more-btn" :disabled="deletingKeys.includes(session.key)"
                  :aria-label="`会话操作：${session.title}`" title="会话操作">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>
                  </svg>
                </button>
                <template #dropdown><el-dropdown-menu><el-dropdown-item command="delete">删除会话</el-dropdown-item></el-dropdown-menu></template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </aside>
      <div class="content">
        <router-view v-slot="{ Component }"><component :is="Component" :key="pageKey" /></router-view>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.workspace-container { width: 100%; height: 100%; min-height: 0; display: flex; flex-direction: column; background: #fff; }
.workspace-main { display: flex; flex: 1; min-height: 0; }
.sidebar { width: 260px; flex-shrink: 0; min-height: 0; display: flex; flex-direction: column; border-right: 1px solid #e9ecef; }
.create-section { padding: 20px 16px 16px; }
.module-title { margin-bottom: 14px; font-size: 16px; font-weight: 600; color: #202124; }
.create-btn-native { width: 100%; height: 44px; border: 1px solid #d8e3f5; border-radius: 10px; background: #edf4ff; color: #315f9c; cursor: pointer; }
.btn-content { display: flex; align-items: center; justify-content: center; gap: 8px; }
.icon { font-size: 20px; }
.history-filters { display: flex; gap: 4px; padding: 12px 12px 4px; }
.history-filters button { flex: 1; border: 0; border-radius: 7px; padding: 7px 0; background: transparent; color: #777; cursor: pointer; }
.history-filters button.active { background: #edf2fa; color: #315f9c; font-weight: 600; }
.history-error { padding: 12px; color: #985b2e; font-size: 12px; display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.history-error button { border: 0; padding: 3px 6px; background: transparent; color: #315f9c; cursor: pointer; white-space: nowrap; }
.session-list { flex: 1; min-height: 0; padding: 12px 8px; overflow-y: auto; }
.session-list-label { padding: 2px 10px 10px; font-size: 12px; color: #9a9a9f; }
.empty-state { padding: 40px 8px; text-align: center; font-size: 13px; color: #8c8c96; }
.session-card { display: flex; align-items: center; gap: 8px; padding: 12px; margin-bottom: 5px; border: 1px solid transparent; border-radius: 10px; cursor: pointer; }
.session-card:hover { background: #f6f7f9; }
.session-card.active { background: #edf2fa; border-color: #dce6f6; }
.session-info { flex: 1; min-width: 0; }
.session-title { color: #33343a; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: 5px; }
.session-mode { font-size: 11px; color: #788496; }
.session-mode.lingseek { color: #8069a7; }
.session-more-btn { display: flex; align-items: center; justify-content: center; width: 24px; height: 26px; border: 0; border-radius: 5px; background: transparent; color: #777; cursor: pointer; }
.session-more-btn:hover { background: #e6e8ed; }
.content { flex: 1; min-width: 0; min-height: 0; overflow: hidden; }
@media (max-width: 640px) {
  .module-title, .history-filters, .session-list-label { display: none; }
  .history-error { display: block; padding: 4px; font-size: 10px; }
}
</style>
