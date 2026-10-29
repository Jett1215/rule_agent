<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from "vue"
import { useRoute, useRouter } from 'vue-router'
import { MdPreview } from "md-editor-v3"
import "md-editor-v3/lib/style.css"
import type { ChatMessage } from "../../../type"
import { sendMessage, type Chat } from "../../../apis/chat"
import { useHistoryChatStore } from "../../../store/history_chat_msg"
import { useUserStore } from "../../../store/user"
import { ElScrollbar, ElInput, ElButton, ElMessage, ElUpload, ElIcon } from "element-plus"
import { UploadFilled, Promotion, Loading, VideoPause, Check, Close } from '@element-plus/icons-vue'

// Import static assets
import defaultUserAvatar from '../../../assets/user.svg';
import defaultRobotAvatar from '../../../assets/robot.svg';

// 使用与ChatMessage接口中定义的eventInfo类型一致的接口
interface EventInfo {
  event_type: string
  show: boolean
  status: string
  message: string
}

interface EventStatus {
  id: string
  event_type: string
  message: string
  status: 'START' | 'END' | 'ERROR'
  timestamp: number
  loading: boolean
  success: boolean
  error: boolean
}

const searchInput = ref("")
const sendQuestion = ref(true)
const historyChatStore = useHistoryChatStore()
const userStore = useUserStore()
const scrollbar = ref<InstanceType<typeof ElScrollbar>>()
const route = useRoute()
const router = useRouter()
let pageActive = true
let streamVersion = 0
const newConfiguredConversation = () => router.push({
  name: 'workspaceDefaultPage',
  query: { mode: 'normal', ...(typeof route.query.agent_id === 'string' ? { agent_id: route.query.agent_id } : {}) },
})
const abortCtrl = ref<AbortController | null>(null)
const isCancelled = ref(false)
// 标记是否有正在进行的事件
const hasActiveEvents = ref(false)
// 保存上传文件的URL和文件名
const fileUrl = ref("")
const fileName = ref("")

// 事件状态管理
const eventStatusMap = ref<Map<string, EventStatus>>(new Map())
const eventDisplayOrder = ref<string[]>([])

// Get user avatar from store or use default
const userAvatar = computed(() => userStore.userInfo?.avatar || defaultUserAvatar)
// Get AI avatar from store or use default
const aiAvatar = computed(() => historyChatStore.logo || defaultRobotAvatar)

// 计算显示的事件列表
const displayEventList = computed(() => {
  return eventDisplayOrder.value.map(id => eventStatusMap.value.get(id)).filter(Boolean) as EventStatus[]
})

// 检查是否有活跃事件
const checkActiveEvents = (chatItem: any) => {
  if (!chatItem.eventInfo || chatItem.eventInfo.length === 0) {
    return false
  }
  return chatItem.eventInfo.some((event: EventInfo) => event.status === 'START')
}

const handleUploadSuccess = (response: any, file: any, fileList: any) => {
  ElMessage.success(`文件 ${file.name} 上传成功!`)
  console.log(response)
  // 保存上传成功返回的文件URL和文件名
  if (response && response.data) {
    fileUrl.value = response.data
    fileName.value = file.name
  }
}

const handleUploadError = (error: any, file: any, fileList: any) => {
  ElMessage.error(`文件 ${file.name} 上传失败.`)
  console.error(error)
}

// 取消上传的文件
const cancelUploadedFile = () => {
  fileUrl.value = ""
  fileName.value = ""
  ElMessage.info('已取消选择的文件')
}

// 判断是否为图片文件以便展示缩略图
const isImageFile = (name: string) => {
  return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(name)
}


// Function to scroll to the bottom of the chat
function scrollBottom() {
  nextTick(() => {
    scrollbar.value?.wrapRef?.scrollTo(0, scrollbar.value?.wrapRef.scrollHeight)
  })
}

// 清空事件状态
const clearEventStatus = () => {
  eventStatusMap.value.clear()
  eventDisplayOrder.value = []
}

// 处理事件状态更新
const handleEventStatus = (parsedData: any, lastChat: ChatMessage) => {
  const { data } = parsedData
  
  // 确保事件有title字段，如果没有则使用event_type或默认值
  const eventId = data.title || data.event_type || "event"
  const { status, message } = data
  
  // 初始化eventInfo数组（如果不存在）
  if (!lastChat.eventInfo) {
    lastChat.eventInfo = []
  }
  
  // 查找是否已有相同事件类型的事件
  const existingEventIndex = lastChat.eventInfo.findIndex(
    (event) => event.event_type === eventId
  )
  
  if (status === 'START') {
    // 如果是新事件，添加到事件列表
    if (existingEventIndex === -1) {
      lastChat.eventInfo.push({
        event_type: eventId,
        message: message || "处理中...",
        status: status,
        show: false // 默认折叠
      })
    } else {
      // 更新已有事件
      lastChat.eventInfo[existingEventIndex].status = status
      lastChat.eventInfo[existingEventIndex].message = message || "处理中..."
    }
    // 设置有活跃事件
    hasActiveEvents.value = true
  } else if (status === 'END' || status === 'ERROR') {
    // 更新已有事件状态
    if (existingEventIndex !== -1) {
      lastChat.eventInfo[existingEventIndex].status = status
      if (message) {
        lastChat.eventInfo[existingEventIndex].message = message
      }
    } else {
      // 如果没有找到对应的事件，创建一个新事件
      lastChat.eventInfo.push({
        event_type: eventId,
        message: message || (status === 'END' ? "已完成" : "处理出错"),
        status: status,
        show: false // 默认折叠
      })
    }
    
    // 检查是否还有其他活跃事件
    hasActiveEvents.value = checkActiveEvents(lastChat)
  }
  
  scrollBottom()
}

// Function to handle sending a message
const personQuestion = async () => {
  if (!pageActive || historyChatStore.loading || historyChatStore.error) return
  if (!historyChatStore.dialogId) {
    ElMessage.error('未获取到会话 ID，请先选择或创建会话')
    return
  }
  if (searchInput.value.trim() && sendQuestion.value) {
    sendQuestion.value = false
    isCancelled.value = false
    hasActiveEvents.value = false
    const version = ++streamVersion
    const currentDialog = historyChatStore.dialogId
    const isCurrentStream = () => pageActive && version === streamVersion && historyChatStore.dialogId === currentDialog
    const currentInput = searchInput.value
    searchInput.value = ""

    historyChatStore.chatArr.push({
      personMessage: { content: currentInput },
      aiMessage: { content: "" }, // 设置初始空内容，后续会被chunks累加
      eventInfo: [] // 初始化事件信息数组
    })
    scrollBottom()

    const data: Chat = {
      dialogId: historyChatStore.dialogId,
      userInput: currentInput,
    }
    
    // 如果有上传的文件URL，添加到请求中
    if (fileUrl.value) {
      data.fileUrl = fileUrl.value
    }

    const currentMessage = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
    const finishStream = () => {
      if (!isCurrentStream()) return
      sendQuestion.value = true
      abortCtrl.value = null
      hasActiveEvents.value = false
      fileUrl.value = ""
      fileName.value = ""
    }
    const failStream = () => {
      if (!isCurrentStream()) return
      const controller = abortCtrl.value
      currentMessage.aiMessage.content += '\n\n[本轮回答未完成，请重试]'
      for (const event of currentMessage.eventInfo) {
        if (event.status === 'START') {
          event.status = 'ERROR'
          event.message = '连接中断'
        }
      }
      finishStream()
      ++streamVersion
      controller?.abort()
      ElMessage.error('发送失败或连接中断，请重试')
      scrollBottom()
    }

    try {
      abortCtrl.value = sendMessage(data, (message: any) => {
        if (!isCurrentStream() || isCancelled.value) return
        try {
          const event = JSON.parse(message.data)
          if (event.type === 'response_chunk' && typeof event.data?.chunk === 'string') {
            currentMessage.aiMessage.content += event.data.chunk
          } else if (event.type === 'event' && event.data) {
            handleEventStatus(event, currentMessage)
          } else if (event.type === 'knowledge') {
            historyChatStore.chatArr.push({
              personMessage: { content: '' },
              aiMessage: { content: '[知识库检索结果]\n' + (event.data?.message || ''), type: 'knowledge' },
              eventInfo: [],
            })
          } else if (event.type === 'error') {
            failStream()
          } else if (typeof event.data?.content === 'string') {
            currentMessage.aiMessage.content += event.data.content
          }
          scrollBottom()
        } catch {
          failStream()
        }
      }, () => {
        if (!isCurrentStream()) return
        finishStream()
        window.dispatchEvent(new CustomEvent('conversation-updated'))
      }, failStream)
    } catch {
      failStream()
    }
  }
}

const stopGeneration = () => {
  if (abortCtrl.value) {
    // console.log('[stopGeneration] 用户点击暂停, abort 请求')
    isCancelled.value = true
    ++streamVersion
    abortCtrl.value.abort()
    const lastMessage = historyChatStore.chatArr[historyChatStore.chatArr.length - 1]
    if (lastMessage) {
      //lastMessage.aiMessage.content = '已取消本次AI生成！'
      sendQuestion.value = true
      abortCtrl.value = null
      hasActiveEvents.value = false
      ElMessage.info('已取消本次AI生成！')
    }
  }
}

// 切换事件信息的展开/折叠状态
const toggleEventInfo = (event: EventInfo) => {
  event.show = !event.show
}

onBeforeUnmount(() => {
  pageActive = false
  ++streamVersion
  abortCtrl.value?.abort()
  abortCtrl.value = null
})

// Load history on mount
onMounted(() => {
  const dialog_id = route.query.dialog_id
  const message = route.query.message
  
  if (dialog_id) {
    historyChatStore.dialogId = dialog_id as string
    historyChatStore.HistoryChat(dialog_id as string).then(() => {
        if (!pageActive || historyChatStore.dialogId !== dialog_id) return
        scrollBottom()
        
        // 如果有来自首页的搜索消息，自动发送
        if (message && typeof message === 'string') {
          searchInput.value = message
          nextTick(() => {
            personQuestion()
          })
        }
    })
  } else if (message && typeof message === 'string') {
    // 新会话，直接发送首页的搜索消息
    searchInput.value = message
    nextTick(() => {
      personQuestion()
    })
  }
})

// Watch for route changes to load new chat history
watch(
  () => route.query.dialog_id,
  (newVal, oldVal) => {
    if (newVal && newVal !== oldVal) {
      ++streamVersion
      abortCtrl.value?.abort()
      abortCtrl.value = null
      sendQuestion.value = true
      historyChatStore.dialogId = newVal as string
      historyChatStore.HistoryChat(newVal as string).then(() => {
        if (!pageActive || historyChatStore.dialogId !== newVal) return
        scrollBottom()
        
        // 如果有来自首页的搜索消息，自动发送
        const message = route.query.message
        if (message && typeof message === 'string') {
          searchInput.value = message
          nextTick(() => {
            personQuestion()
          })
        }
      })
    }
  }
)

// Watch for new messages to scroll down
watch(
  () => historyChatStore.chatArr,
  (newVal) => {
    // console.log('【消息更新】历史消息数组更新:', JSON.stringify(newVal))
    scrollBottom()
  },
  { deep: true }
)
</script>

<template>
  <div class="chat-container">
    <div class="legacy-conversation-header">
      <div><strong>日常对话</strong><span>此历史会话沿用原智能体配置</span></div>
      <button @click="newConfiguredConversation">新建可配置会话</button>
    </div>
    <div class="chat-conversation">
      <el-scrollbar ref="scrollbar">
        <!-- 聊天消息区 -->
        <div v-for="(item, index) in historyChatStore.chatArr" :key="index" class="message-group">
          <!-- User Message -->
          <div v-if="item.personMessage.content" class="user-message">
            <div class="message-content">
              <span>{{ item.personMessage.content }}</span>
            </div>
            <img :src="userAvatar" alt="User Avatar" class="avatar" />
          </div>
          
          <!-- AI Message -->
          <div v-if="item.aiMessage.content || (!sendQuestion && index === historyChatStore.chatArr.length - 1)" class="ai-message" :class="item.aiMessage.type ? 'ai-message-' + item.aiMessage.type : ''">
            <img :src="aiAvatar" alt="AI Avatar" class="avatar" />
            <div class="message-content">
              <!-- 事件进度信息，每个事件一行，可折叠 -->
              <div v-if="item.eventInfo && item.eventInfo.length" class="event-info-list">
                <div v-for="(event, evIdx) in item.eventInfo" :key="evIdx" class="event-info-row" :class="event.status">
                  <div class="event-info-header" @click="toggleEventInfo(event)">
                    <el-icon v-if="event.status === 'START'" class="rotating"><Loading /></el-icon>
                    <el-icon v-else-if="event.status === 'END'" class="success-icon"><Check /></el-icon>
                    <el-icon v-else-if="event.status === 'ERROR'" class="error-icon"><Close /></el-icon>
                    <span class="event-info-title">{{ event.event_type }}</span>
                    <span class="event-info-status">
                      {{ event.status === 'START' ? '进行中' : event.status === 'END' ? '已完成' : '失败' }}
                    </span>
                    <span class="event-info-toggle">{{ event.show ? '收起' : '展开' }}</span>
                  </div>
                  <div v-if="event.show" class="event-info-message">
                    {{ event.message }}
                  </div>
                </div>
              </div>
              
              <!-- Loading Indicator - 只在没有活跃事件时显示 -->
              <div v-if="!item.aiMessage.content && !sendQuestion && index === historyChatStore.chatArr.length - 1 && !hasActiveEvents" class="loading-spinner">
                  <el-icon class="is-loading" :size="20"><Loading /></el-icon>
              </div>
              <template v-else>
                <div v-if="item.aiMessage.type === 'knowledge'" style="color: #409eff;">
                  <MdPreview :editorId="'ai-knowledge-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <div v-else-if="item.aiMessage.type === 'event'" style="color: #67c23a;">
                  <MdPreview :editorId="'ai-event-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <div v-else-if="item.aiMessage.type === 'error'" style="color: #f56c6c;">
                  <MdPreview :editorId="'ai-error-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <div v-else-if="item.aiMessage.type === 'system'" style="color: #e6a23c;">
                  <MdPreview :editorId="'ai-system-' + index" :modelValue="item.aiMessage.content" />
                </div>
                <MdPreview v-else :editorId="'ai-' + index" :modelValue="item.aiMessage.content" />
              </template>
            </div>
          </div>
        </div>
      </el-scrollbar>
    </div>

    <div class="input-area">
      <el-upload
        action="/api/v1/upload"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :show-file-list="false"
        :disabled="!!fileUrl"
      >
        <el-button circle class="action-btn" :class="{ 'file-uploaded': fileUrl }">
          <el-icon><UploadFilled /></el-icon>
        </el-button>
      </el-upload>
      <div class="input-wrapper">
        <!-- 已上传文件显示 -->
        <div v-if="fileUrl" class="uploaded-file-tag">
          <span class="file-avatar" aria-hidden="true">
            <img v-if="isImageFile(fileName)" :src="fileUrl" alt="" />
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M21.44 11.05l-7.07 7.07a5 5 0 01-7.07-7.07l7.07-7.07a3 3 0 114.24 4.24l-7.07 7.07a1 1 0 01-1.41-1.41l6.36-6.36" stroke="#409eff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <a class="file-name" :href="fileUrl" target="_blank" rel="noopener" :title="fileName">{{ fileName }}</a>
          <el-button size="small" type="danger" text @click="cancelUploadedFile" class="cancel-btn" title="移除">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <el-input
          v-model="searchInput"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="请输入您的问题..."
          @keydown.enter.exact.prevent="personQuestion"
          class="message-input"
        />
      </div>
      <el-button
        @click="sendQuestion ? personQuestion() : stopGeneration()"
        type="primary"
        circle
        class="send-btn"
        :class="{ 'pause-mode': !sendQuestion }"
        :disabled="sendQuestion ? !searchInput.trim() : false"
      >
        <el-icon v-if="sendQuestion"><Promotion /></el-icon>
        <el-icon v-else><VideoPause /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.legacy-conversation-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 20px; border-bottom: 1px solid #ececf0; background: white;
  strong { font-size: 14px; color: #303039; }
  span { margin-left: 12px; font-size: 12px; color: #909098; }
  button { border: 1px solid #dce3ef; background: #f5f8fd; color: #45658d; border-radius: 8px; padding: 8px 12px; cursor: pointer; white-space: nowrap; }
}
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f7f8fa;
}

.chat-conversation {
  flex: 1;
  padding: 20px;
  overflow-y: hidden;
  
  .message-group {
    margin-bottom: 20px;
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

/* 事件进度信息样式 */
.event-info-list {
  margin-bottom: 12px;
}

.event-info-row {
  margin-bottom: 8px;
  border-radius: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  cursor: pointer;
  transition: background 0.3s ease;
  display: flex;
  flex-direction: column;
  
  &.START { 
    border-left: 4px solid #409eff; 
    background: #f0f7ff;
  }
  
  &.END { 
    border-left: 4px solid #67c23a; 
    background: #f0fff4;
  }
  
  &.ERROR { 
    border-left: 4px solid #f56c6c; 
    background: #fff0f0;
  }
  
  &:hover {
    transform: translateX(2px);
  }
}

.event-info-header { 
  display: flex; 
  align-items: center; 
}

.event-info-title { 
  margin-left: 8px; 
  font-weight: 600;
  color: #333;
}

.event-info-status {
  margin-left: 8px;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #eee;
  
  .START & {
    background: #e6f1ff;
    color: #409eff;
  }
  
  .END & {
    background: #e7f9eb;
    color: #67c23a;
  }
  
  .ERROR & {
    background: #ffeded;
    color: #f56c6c;
  }
}

.event-info-toggle { 
  margin-left: auto; 
  color: #aaa; 
  font-size: 12px;
  
  &:hover {
    color: #666;
  }
}

.event-info-message { 
  margin-top: 8px; 
  color: #333;
  padding: 8px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.5;
}

.rotating { 
  animation: spin 1.2s linear infinite;
  color: #409eff;
}

.success-icon {
  color: #67c23a;
}

.error-icon {
  color: #f56c6c;
}

@keyframes spin { 
  from { transform: rotate(0deg); } 
  to { transform: rotate(360deg); } 
}

.loading-spinner {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 28px;
  color: #6e8efb;
}

.input-area {
  display: flex;
  align-items: flex-end;
  padding: 15px 20px;
  border-top: 1px solid #e0e0e0;
  background-color: #ffffff;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.05);

  .action-btn {
    margin-right: 10px;
    background-color: #f0f2f5;
    border: none;
    width: 48px;
    height: 48px;
    font-size: 24px;
    transition: all 0.3s ease;
    &:hover {
      background-color: #e6e8eb;
    }
    &.file-uploaded {
      background-color: #67c23a;
      color: white;
      &:hover {
        background-color: #5daf34;
      }
    }
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }

  .input-wrapper {
    flex-grow: 1;
    position: relative;
  }

  .uploaded-file-tag {
    position: absolute;
    top: -28px;
    left: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: linear-gradient(135deg, #f5fbff 0%, #ecf5ff 100%);
    border: 1px solid #b3d8ff;
    border-radius: 16px;
    font-size: 12px;
    z-index: 10;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);

    .file-avatar {
      width: 22px;
      height: 22px;
      border-radius: 6px;
      overflow: hidden;
      background: rgba(64, 158, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      border: 1px solid rgba(64, 158, 255, 0.2);
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
    }

    .file-name {
      color: #1f6fd6;
      text-decoration: none;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 180px;
      font-weight: 500;
    }

    .cancel-btn {
      padding: 0;
      width: 20px;
      height: 20px;
      min-height: 20px;
      font-size: 12px;
      margin-left: 4px;
      
      &:hover {
        background-color: rgba(245, 108, 108, 0.1);
      }
      :deep(.el-icon) {
        font-size: 16px;
      }
    }
  }

  .message-input {
    width: 100%;
    :deep(.el-textarea__inner) {
      border-radius: 20px;
      background-color: #f0f2f5;
      box-shadow: none;
      border: 1px solid transparent;
      padding: 12px 18px;
      &:focus {
        border-color: #6e8efb;
      }
    }
  }

  .send-btn {
    margin-left: 10px;
    background-color: #6e8efb;
    border: none;
    width: 48px;
    height: 48px;
    font-size: 24px;
    &:hover {
      background-color: #5a78e6;
    }
    &.pause-mode {
      background-color: #f56c6c;
      &:hover {
        background-color: #dd6161;
      }
    }
  }
}


// Override MdPreview background
:deep(.md-editor-preview-wrapper) {
    background-color: transparent !important;
}

:deep(.el-scrollbar__view) {
  padding: 10px;
}
</style>
