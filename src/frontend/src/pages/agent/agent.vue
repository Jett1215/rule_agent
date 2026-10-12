<script setup lang="ts">
import SidebarIcon from '../../components/SidebarIcon.vue'
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Delete, View, Search, Refresh, Tools } from '@element-plus/icons-vue'
import robotIcon from '../../assets/robot.svg'
import pluginIcon from '../../assets/plugin.svg'
import knowledgeIcon from '../../assets/knowledge.svg'
import mcpIcon from '../../assets/mcp.svg'
import skillIcon from '../../assets/skill.svg'
import { 
  getAgentsAPI, 
  deleteAgentAPI, 
  searchAgentsAPI,
  type AgentResponse 
} from '../../apis/agent'
import { Agent } from '../../type'


const router = useRouter()
const agents = ref<Agent[]>([])
const loading = ref(false)
const searchLoading = ref(false)
const editingAgent = ref<Agent | null>(null)
const searchKeyword = ref('')
const showConfirmDialog = ref(false)
const agentToDelete = ref<Agent | null>(null)


// 转换API响应为本地Agent类型
const convertToAgent = (apiAgent: any): Agent => ({
  agent_id: apiAgent.id || apiAgent.agent_id, // 兼容后端返回id字段
  name: apiAgent.name,
  description: apiAgent.description,
  logo_url: apiAgent.logo_url,
  tool_ids: apiAgent.tool_ids || [],
  llm_id: apiAgent.llm_id,
  mcp_ids: apiAgent.mcp_ids || [],
  system_prompt: apiAgent.system_prompt,
  knowledge_ids: apiAgent.knowledge_ids || [],
  enable_memory: apiAgent.enable_memory,
  created_time: apiAgent.create_time || apiAgent.created_time,
  is_custom: apiAgent.is_custom // 新增is_custom字段
})

// 获取智能体列表
const fetchAgents = async () => {
  loading.value = true
  try {
    // 删除包含敏感信息的日志
    // console.log('开始调用智能体API...')
    // console.log('请求URL: /api/v1/agent')
    // console.log('Token:', localStorage.getItem('token'))
    
    const response = await getAgentsAPI()
    // console.log('API响应:', response)
    // console.log('响应数据:', response.data)
    
    // 兼容不同的后端响应格式
    const responseCode = response.data.status_code || response.data.status_code
    const responseMessage = response.data.status_message || response.data.status_message
    const responseData = response.data.data
    
    if (responseCode === 200 || response.data.status_code === 200) {
      // console.log('API调用成功，智能体数据:', responseData)
      if (responseData && Array.isArray(responseData)) {
        agents.value = responseData.map(convertToAgent)
        // console.log('转换后的智能体列表:', agents.value)
      } else {
        console.warn('响应数据格式异常:', responseData)
        agents.value = []
      }
    } else {
      console.error('API返回错误:', responseMessage)
      ElMessage.error(responseMessage || '获取智能体列表失败')
    }
  } catch (error: any) {
    console.error('获取智能体列表失败 - 详细错误:', error)
    console.error('错误类型:', typeof error)
    console.error('错误信息:', error.message)
    console.error('错误响应:', error.response)
    
    if (error.response) {
      console.error('响应状态码:', error.response.status)
      console.error('响应数据:', error.response.data)
      ElMessage.error(`请求失败: ${error.response.status} - ${error.response.data?.message || '未知错误'}`)
    } else if (error.request) {
      console.error('请求对象:', error.request)
      ElMessage.error('网络错误：无法连接到服务器')
    } else {
      ElMessage.error('获取智能体列表失败：' + error.message)
    }
  } finally {
    loading.value = false
  }
}

// 搜索智能体
const searchAgents = async () => {
  if (!searchKeyword.value.trim()) {
    await fetchAgents()
    return
  }
  
  searchLoading.value = true
  try {
    const response = await searchAgentsAPI({ name: searchKeyword.value.trim() })
    if (response.data.status_code === 200) {
      // 搜索结果转换为Agent格式
      agents.value = response.data.data.map(item => ({
        agent_id: item.agent_id,
        name: item.name,
        description: item.description,
        logo_url: item.logo_url,
        tool_ids: [],
        llm_id: '',
        mcp_ids: [],
        system_prompt: '',
        knowledge_ids: [],
        enable_memory: false,
        is_custom: false // 搜索结果默认为系统智能体
      }))
    } else {
      ElMessage.error(response.data.status_message || '搜索失败')
    }
  } catch (error: any) {
    console.error('搜索智能体失败:', error)
    ElMessage.error('搜索智能体失败')
  } finally {
    searchLoading.value = false
  }
}

// 清空搜索
const clearSearch = () => {
  searchKeyword.value = ''
  fetchAgents()
}

// 创建智能体
const createAgent = () => {
  router.push('/agent/editor')
}

// 编辑智能体
const editAgent = (agent: Agent) => {
  // 确保只能编辑自定义智能体
  if (agent.is_custom === false) {
    ElMessage.warning(`"${agent.name}" 是官方智能体，无法编辑。`)
    return
  }
  
  router.push({
    path: '/agent/editor',
    query: { id: agent.agent_id }
  })
}

// 显示系统智能体提示
const showSystemAgentMessage = (agent: Agent) => {
  ElMessage.warning(`"${agent.name}" 是官方智能体，无法编辑。`)
}


// 处理智能体更新
const handleAgentUpdate = () => {
  fetchAgents()
}

// 删除智能体
const deleteAgent = (agent: Agent) => {
  // 确保只能删除自定义智能体
  if (agent.is_custom === false) {
    ElMessage.error('官方智能体不能删除')
    return
  }
  
  // 显示确认对话框
  agentToDelete.value = agent
  showConfirmDialog.value = true
}

// 确认删除
const confirmDelete = async () => {
  if (!agentToDelete.value) return
  
  try {
    //ElMessage.info('正在删除智能体...')
    
    const response = await deleteAgentAPI({ agent_id: agentToDelete.value.agent_id })
    if (response.data.status_code === 200) {
      ElMessage.success('删除成功')
      await fetchAgents() // 刷新列表
    } else {
      ElMessage.error(response.data.status_message || '删除失败')
    }
  } catch (error: any) {
    console.error('删除智能体失败:', error)
    ElMessage.error('删除失败，请稍后重试')
  } finally {
    // 关闭确认对话框
    showConfirmDialog.value = false
    agentToDelete.value = null
  }
}

// 取消删除
const cancelDelete = () => {
  showConfirmDialog.value = false
  agentToDelete.value = null
}

// 查看智能体详情
const viewAgent = (agent: Agent) => {
  // TODO: 实现智能体详情查看功能
  ElMessage.info('智能体详情功能开发中...')
  console.log('查看智能体:', agent)
}

// 刷新智能体列表
const refreshAgents = async () => {
  await fetchAgents()
}

// 处理图片加载错误
const handleImageError = (event: Event) => {
  const target = event.target as HTMLImageElement
  if (target) {
    target.src = '/src/assets/robot.svg'
  }
}

onMounted(() => {
  fetchAgents()
})
</script>

<template>
  <div class="agent-page">
    <div class="page-header">
      <div class="header-title">
        <SidebarIcon name="agent" class="title-icon" />
        <h2>智能体管理</h2>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <div class="search-input-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="🔍 搜索智能体名称..."
              @keyup.enter="searchAgents"
              @clear="clearSearch"
              clearable
              size="large"
              style="width: 320px"
            />
            <el-button 
              type="primary" 
              :icon="Search" 
              @click="searchAgents"
              :loading="searchLoading"
              size="large"
              style="margin-left: 12px; border-radius: 12px;"
            >
              搜索
            </el-button>
          </div>
        </div>
        <div class="action-buttons">
          <el-button 
            :icon="Refresh" 
            @click="refreshAgents"
            :loading="loading"
            title="刷新列表"
            size="large"
            circle
            style="border-radius: 12px;"
          />
          <el-button 
            type="primary" 
            :icon="Plus" 
            @click="createAgent"
            size="large"
            style="border-radius: 12px; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); border: none;"
          >
            创建智能体
          </el-button>
        </div>
      </div>
    </div>

    <div class="agent-list" v-loading="loading">
      <div class="agent-grid" v-if="agents.length > 0">
        <div 
          v-for="agent in agents" 
          :key="agent.agent_id" 
          class="agent-card"
          :class="{'official-agent': agent.is_custom === false}"
          @click="agent.is_custom !== false ? editAgent(agent) : showSystemAgentMessage(agent)"
        >
          <!-- 删除按钮 - 仅对自定义智能体显示 -->
          <div 
            v-if="agent.is_custom !== false" 
            class="delete-icon" 
            @click.stop="deleteAgent(agent)" 
            title="删除"
          >×</div>
          
          <!-- 官方智能体标识 -->
          <div v-if="agent.is_custom === false" class="official-badge">官方</div>
          
          <div class="agent-avatar">
            <img 
              :src="agent.logo_url || '/src/assets/robot.svg'" 
              :alt="agent.name"
              @error="handleImageError"
            />
          </div>
          
          <div class="agent-info">
            <h3 class="agent-name" :title="agent.name">{{ agent.name }}</h3>
            <p class="agent-description" :title="agent.description">
              {{ agent.description }}
            </p>
            
            <div class="agent-meta">
              <span class="meta-item" title="可用工具数量">
                <img :src="pluginIcon" class="meta-icon-img" alt="工具" />
                <span class="meta-count">{{ agent.tool_ids?.length || 0 }}</span>
              </span>
              <span class="meta-item" title="关联知识库数量">
                <img :src="knowledgeIcon" class="meta-icon-img" alt="知识库" />
                <span class="meta-count">{{ agent.knowledge_ids?.length || 0 }}</span>
              </span>
              <span class="meta-item" title="MCP服务数量">
                <img :src="mcpIcon" class="meta-icon-img" alt="MCP" />
                <span class="meta-count">{{ agent.mcp_ids?.length || 0 }}</span>
              </span>
              <span class="meta-item" title="Skill数量">
                <img :src="skillIcon" class="meta-icon-img" alt="Skill" />
                <span class="meta-count">{{ agent.agent_skill_ids?.length || 0 }}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else-if="!loading" class="empty-state">
        <div class="empty-icon">
          <SidebarIcon name="agent" />
        </div>
        <h3 v-if="searchKeyword">未找到智能体</h3>
        <h3 v-else>暂无智能体</h3>
        <p v-if="searchKeyword">
          未找到包含 "{{ searchKeyword }}" 的智能体
        </p>
        <p v-else>
          创建您的第一个智能体，开始智能对话体验
        </p>
        <div class="empty-actions">
          <el-button 
            v-if="searchKeyword" 
            type="primary" 
            @click="clearSearch"
          >
            查看所有智能体
          </el-button>
          <el-button 
            v-else
            type="primary"
            @click="createAgent"
          >
            创建智能体
          </el-button>
        </div>
      </div>
    </div>

    <!-- 确认删除对话框 -->
    <div v-if="showConfirmDialog" class="custom-confirm-dialog">
      <div class="confirm-dialog-content">
        <h3 class="dialog-title">确认删除</h3>
        <div class="dialog-body">
          确定要删除智能体 "{{ agentToDelete?.name }}" 吗？
        </div>
        <div class="dialog-footer">
          <button class="btn-cancel" @click="cancelDelete">取消</button>
          <button class="btn-confirm" @click="confirmDelete">确定</button>
        </div>
      </div>
    </div>

  </div>
</template>

<style lang="scss" scoped>
.agent-page {
  padding: 32px;
  min-height: 100vh;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px; // 减小了margin-bottom
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
    padding: 20px 28px; // 减小了padding
    border-radius: 16px; // 减小了border-radius
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.06); // 减小了阴影
    border: 1px solid rgba(226, 232, 240, 0.6);
    
    .header-title {
      display: flex;
      align-items: center;
      gap: 14px;
      
      .title-icon {
        width: 36px;
        height: 36px;
      }
      
      h2 {
        margin: 0;
        font-size: 24px;
        font-weight: 600;
        background: linear-gradient(90deg, #1B7CE4, #409eff); // 与robot.svg图标颜色匹配
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
    }
    
    .header-actions {
      display: flex;
      align-items: center;
      gap: 32px;
      
      .search-box {
        .search-input-wrapper {
          display: flex;
          align-items: center;
          background: rgba(255, 255, 255, 0.8);
          padding: 8px;
          border-radius: 16px;
          border: 1px solid rgba(59, 130, 246, 0.2);
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
          
          :deep(.el-input) {
            .el-input__wrapper {
              background: transparent;
              border: none;
              box-shadow: none;
              border-radius: 12px;
              
              .el-input__inner {
                font-size: 15px;
                font-weight: 500;
                color: #1e293b;
                
                &::placeholder {
                  color: #64748b;
                  font-weight: 400;
                }
              }
            }
          }
        }
      }
      
      .action-buttons {
        display: flex;
        gap: 16px;
        
        :deep(.el-button) {
          font-weight: 600;
          font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          
          &:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(59, 130, 246, 0.3);
          }
        }
      }
    }
  }
  
  .agent-list {
    height: calc(100vh - 140px);
    overflow-y: auto;
    
    .agent-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
      
      .agent-card {
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 20px;
        padding: 16px;
        height: 200px;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(226, 232, 240, 0.8);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        display: flex;
        flex-direction: column;
        cursor: pointer; /* Add cursor pointer for clickability */
        
        &:hover {
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
          transform: translateY(-4px);
          
          .delete-icon {
            opacity: 1;
            transform: scale(1);
          }
        }
        
        // 系统智能体样式
        &.official-agent {
          background: linear-gradient(145deg, #fffaf0 0%, #fff8e5 100%);
          border: 1px solid rgba(255, 152, 0, 0.3);
          
          &:hover {
            box-shadow: 0 8px 24px rgba(255, 152, 0, 0.15);
          }
          
          .agent-name {
            color: #d87300 !important;
          }
          
          .agent-meta {
            .meta-item {
              background: rgba(255, 243, 224, 0.5);
              border: 1px solid rgba(255, 152, 0, 0.1);
            }
          }
        }
        
        .delete-icon {
          position: absolute;
          top: 10px;
          right: 10px;
          background-color: #f56c6c;
          color: white;
          border-radius: 50%;
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          font-weight: bold;
          cursor: pointer;
          z-index: 1;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
          transition: all 0.3s ease;
          opacity: 0;
          transform: scale(0.8);

          &:hover {
            background-color: #ff7a7a;
          }
        }

        .official-badge {
          position: absolute;
          top: 10px;
          right: 10px;
          background-color: #ff9800;
          color: white;
          padding: 4px 8px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: bold;
          z-index: 1;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
        
        
        .agent-avatar {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          overflow: hidden;
          margin-bottom: 12px;
          border: 2px solid #f0f0f0;
          
          img {
            width: 100%;
            height: 100%;
            object-fit: cover;
          }
        }
        
        .agent-info {
          flex: 1;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          
          .agent-name {
            font-size: 16px;
            font-weight: 600;
            color: #2c3e50;
            margin: 0 0 6px 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          
          .agent-description {
            color: #64748b;
            font-size: 14px;
            line-height: 1.4;
            margin: 0 0 10px 0;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            min-height: 32px;
            flex: 1;
          }
          
          .agent-meta {
            display: flex;
            justify-content: flex-start;
            gap: 3px;
            margin-top: auto;
            padding-top: 8px;
            
            .meta-item {
              font-size: 11px;
              color: #64748b;
              display: flex;
              align-items: center;
              justify-content: center;
              gap: 2px;
              background: rgba(255, 255, 255, 0.3); /* 半透明背景 */
              padding: 4px 5px;
              border-radius: 6px;
              min-width: 38px;
              text-align: center;
              box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
              backdrop-filter: blur(2px); /* 轻微模糊效果 */
              
              .meta-icon-img {
                width: 14px;
                height: 14px;
                object-fit: contain;
              }
              
              .meta-count {
                font-size: 13px;
                font-weight: 600;
              }
            }
          }
          
          .agent-status {
            margin-top: 12px;
          }
        }
        
        .agent-actions {
          display: flex;
          gap: 8px;
          margin-top: 8px;
          justify-content: space-between;
          
          .el-button, .custom-delete-btn {
            flex: 1;
            text-align: center;
            padding: 6px 0;
            font-size: 12px;
          }
        }
      }
    }
    
    .empty-state {
      text-align: center;
      padding: 80px 20px;
      color: #64748b;
      background: white;
      border-radius: 16px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      
      p {
        margin-top: 24px;
        font-size: 16px;
        line-height: 1.5;
      }
    }
  }
}

.custom-confirm-dialog {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;

  .confirm-dialog-content {
    background-color: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    text-align: center;
    width: 350px;
    max-width: 90%;

    .dialog-title {
      font-size: 20px;
      font-weight: 700;
      color: #333;
      margin-bottom: 16px;
    }

    .dialog-body {
      font-size: 16px;
      color: #555;
      margin-bottom: 24px;
      line-height: 1.6;
    }

    .dialog-footer {
      display: flex;
      justify-content: center;
      gap: 20px;

      .btn-cancel, .btn-confirm {
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
      }

      .btn-cancel {
        background-color: #f5f5f5;
        color: #333;
        border: 1px solid #ddd;
        
        &:hover {
          background-color: #e5e5e5;
        }
      }

      .btn-confirm {
        background-color: #f56c6c;
        color: white;
        border: none;
        
        &:hover {
          background-color: #ff8080;
          transform: scale(1.05);
        }
        
        &:active {
          transform: scale(0.95);
        }
      }
    }
  }
}


// 响应式设计
@media (min-width: 1400px) {
  .agent-list .agent-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}

@media (min-width: 1200px) and (max-width: 1399px) {
  .agent-list .agent-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}

@media (min-width: 1000px) and (max-width: 1199px) {
  .agent-list .agent-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (min-width: 768px) and (max-width: 999px) {
  .agent-list .agent-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
  }
}

@media (max-width: 767px) {
  .agent-page {
    padding: 16px;
    
    .page-header {
      flex-direction: column;
      gap: 16px;
      align-items: stretch;
      padding: 16px; // 减小了padding
      
      .header-title {
        .title-icon {
          width: 28px;
          height: 28px;
        }
        
        h2 {
          font-size: 24px;
        }
      }
      
      .header-actions {
        flex-direction: column;
        gap: 16px;
        
        .search-box {
          .search-input-wrapper {
            flex-direction: column;
            gap: 12px;
            padding: 12px;
            
            .el-input {
              width: 100% !important;
            }
          }
        }
        
        .action-buttons {
          justify-content: center;
        }
      }
    }
    
    .agent-list .agent-grid {
      grid-template-columns: 1fr;
      gap: 16px;
    }
  }
}

/* 空状态样式 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  margin: 20px auto;
  max-width: 600px;
  
  .empty-icon {
    width: 120px;
    height: 120px;
    display: flex;
    justify-content: center;
    align-items: center;
    background: rgba(64, 158, 255, 0.1);
    border-radius: 50%;
    margin-bottom: 20px;
    
    .empty-icon-symbol {
      font-size: 60px;
    }
  }
  
  h3 {
    font-size: 20px;
    color: #303133;
    margin: 0 0 16px;
  }
  
  p {
    margin: 0 0 20px;
    font-size: 16px;
    color: #909399;
    max-width: 300px;
  }
  
  .empty-actions {
    display: flex;
    gap: 12px;
  }
}
</style> 