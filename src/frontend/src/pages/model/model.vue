<script setup lang="ts">
import SidebarIcon from '../../components/SidebarIcon.vue'
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Connection, Cpu, Search, Refresh, Calendar, ChatDotRound, RefreshRight, Star, Link, Timer, View, Hide } from '@element-plus/icons-vue'
import modelIcon from '../../assets/model.svg'
import { 
  getVisibleLLMsAPI, 
  createLLMAPI, 
  updateLLMAPI,
  deleteLLMAPI,
  searchLLMsAPI,
  type LLMResponse,
  type CreateLLMRequest
} from '../../apis/llm'

const router = useRouter()

// 响应式数据
const models = ref<LLMResponse[]>([])
const loading = ref(false)
const searchKeyword = ref('')
const llmTypes = ref<string[]>(['LLM', 'Embedding', 'Rerank'])

// 防抖定时器
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 创建/编辑对话框控制
const createDialogVisible = ref(false)
const createLoading = ref(false)
const isEditMode = ref(false)
const editingModelId = ref('')
const showApiKey = ref(false)

// 删除确认对话框控制
const deleteDialogVisible = ref(false)
const deleteLoading = ref(false)
const modelToDelete = ref<LLMResponse | null>(null)

// 表单相关
const createForm = ref<CreateLLMRequest>({
  model: '',
  api_key: '',
  base_url: '',
  provider: '',
  llm_type: 'LLM'
})

// 获取模型列表
const fetchModels = async () => {
  loading.value = true
  try {
    const response = await getVisibleLLMsAPI()
    
    if (response.data.status_code === 200) {
      const data = response.data.data || {}
      const allModels: LLMResponse[] = []
      
      Object.values(data).forEach((typeModels: any) => {
        if (Array.isArray(typeModels)) {
          allModels.push(...typeModels)
        }
      })
      
      models.value = allModels
    } else {
      ElMessage.error(response.data.status_message || '获取模型列表失败')
    }
  } catch (error) {
    ElMessage.error('获取模型列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索模型
const searchModels = async () => {
  if (!searchKeyword.value.trim()) {
    // 如果搜索关键词为空，则获取所有模型
    fetchModels()
    return
  }
  
  loading.value = true
  try {
    const response = await searchLLMsAPI({ llm_name: searchKeyword.value.trim() })
    
    if (response.data.status_code === 200) {
      const data = response.data.data || {}
      const allModels: LLMResponse[] = []
      
      Object.values(data).forEach((typeModels: any) => {
        if (Array.isArray(typeModels)) {
          allModels.push(...typeModels)
        }
      })
      
      models.value = allModels
    } else {
      ElMessage.error(response.data.status_message || '搜索模型失败')
    }
  } catch (error) {
    ElMessage.error('搜索模型失败')
  } finally {
    loading.value = false
  }
}

// 清空搜索
const clearSearch = () => {
  searchKeyword.value = ''
  fetchModels()
}

// 打开创建对话框
const openCreateDialog = () => {
  isEditMode.value = false
  editingModelId.value = ''
  showApiKey.value = false
  createDialogVisible.value = true
  // 重置表单
  Object.assign(createForm.value, {
    model: '',
    api_key: '',
    base_url: '',
    provider: '',
    llm_type: 'LLM'
  })
}

// 打开编辑对话框
const openEditDialog = (model: LLMResponse) => {
  isEditMode.value = true
  editingModelId.value = model.llm_id
  showApiKey.value = false
  createDialogVisible.value = true
  // 填充表单
  Object.assign(createForm.value, {
    model: model.model,
    api_key: model.api_key,
    base_url: model.base_url,
    provider: model.provider,
    llm_type: model.llm_type
  })
}

// 创建或更新模型
const handleCreate = async () => {
  // 检查必填字段
  if (!createForm.value.model || !createForm.value.api_key || !createForm.value.base_url || !createForm.value.provider) {
    ElMessage.error('请填写所有必填字段')
    return
  }
  
  createLoading.value = true
  try {
    if (isEditMode.value) {
      // 编辑模式 - 调用更新接口
      const response = await updateLLMAPI({
        llm_id: editingModelId.value,
        model: createForm.value.model,
        api_key: createForm.value.api_key,
        base_url: createForm.value.base_url,
        provider: createForm.value.provider,
        llm_type: createForm.value.llm_type
      })
      
      if (response.data.status_code === 200) {
        ElMessage.success('更新成功')
        createDialogVisible.value = false
        fetchModels()
      } else {
        ElMessage.error('更新失败: ' + (response.data.status_message || '未知错误'))
      }
    } else {
      // 创建模式
      const response = await createLLMAPI(createForm.value)
      
      if (response.data.status_code === 200) {
        ElMessage.success('创建成功')
        createDialogVisible.value = false
        fetchModels()
      } else {
        ElMessage.error('创建失败: ' + (response.data.status_message || '未知错误'))
      }
    }
  } catch (error) {
    ElMessage.error((isEditMode.value ? '更新' : '创建') + '失败，请检查输入并稍后重试')
  } finally {
    createLoading.value = false
  }
}

// 跳转到模型编辑器
const goToModelEditor = (model: LLMResponse) => {
  router.push({
    name: 'model-editor',
    query: { id: model.llm_id }
  })
}

// 删除模型
const deleteModel = async (model: LLMResponse) => {
  // 检查是否为官方模型
  if (isOfficialModel(model)) {
    ElMessage.warning('官方模型不可删除')
    return
  }
  
  // 显示删除确认对话框
  modelToDelete.value = model
  deleteDialogVisible.value = true
}

// 确认删除模型
const confirmDelete = async () => {
  if (!modelToDelete.value) return
  
  deleteLoading.value = true
  try {
    const response = await deleteLLMAPI({ llm_id: modelToDelete.value.llm_id })
    
    if (response.data.status_code === 200) {
      ElMessage.success('删除成功')
      deleteDialogVisible.value = false
      fetchModels()
    } else {
      ElMessage.error('删除失败: ' + (response.data.status_message || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('删除失败，请稍后重试')
  } finally {
    deleteLoading.value = false
  }
}

// 取消删除
const cancelDelete = () => {
  deleteDialogVisible.value = false
  modelToDelete.value = null
}

// 检查是否为官方模型
const isOfficialModel = (model: LLMResponse): boolean => {
  return model.user_id === '0'
}

// 测试模型连接
const testModel = async (model: LLMResponse) => {
  ElMessage.info(`正在测试 ${model.model} 连接...`)
  // 这里可以添加实际的测试逻辑
  setTimeout(() => {
    ElMessage.success(`${model.model} 连接测试完成`)
  }, 2000)
}

// 获取提供商颜色
const getProviderColor = (provider: string) => {
  const colors: Record<string, string> = {
    'OpenAI': 'primary',
    'Anthropic': 'success',
    '阿里云': 'warning',
    '百度': 'info',
    'Google': 'danger'
  }
  return colors[provider] || 'info'
}

// 获取模型类型颜色
const getTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    'LLM': 'primary',
    'Embedding': 'success',
    'Rerank': 'warning'
  }
  return colors[type] || 'info'
}

// 格式化时间
const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleDateString('zh-CN')
}

// 截断URL函数
const truncateUrl = (url: string, maxLength: number): string => {
  if (!url) return '';
  if (url.length <= maxLength) return url;
  
  const protocol = url.includes('://') ? url.split('://')[0] + '://' : '';
  const domainPath = url.replace(protocol, '');
  
  // 如果协议+3个点+最后15个字符超过了最大长度，就只显示开头和结尾
  if (protocol.length + 3 + 15 >= maxLength) {
    const start = protocol + domainPath.substring(0, Math.floor((maxLength - protocol.length - 3) / 2));
    const end = domainPath.substring(domainPath.length - Math.floor((maxLength - protocol.length - 3) / 2));
    return start + '...' + end;
  }
  
  // 否则显示协议+域名开头+...+路径结尾
  const visibleLength = maxLength - protocol.length - 3;
  const start = domainPath.substring(0, Math.floor(visibleLength / 2));
  const end = domainPath.substring(domainPath.length - Math.floor(visibleLength / 2));
  
  return protocol + start + '...' + end;
};

// 改进格式化时间函数，使其更友好
const formatTimeFriendly = (timeStr: string) => {
  if (!timeStr) return '-';
  
  try {
    const date = new Date(timeStr);
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    
    return `${year}/${month}/${day}`;
  } catch(e) {
    return timeStr;
  }
}

// 监听搜索关键词变化，实时搜索（带防抖）
watch(searchKeyword, (newValue) => {
  // 清除之前的定时器
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  
  // 设置新的定时器，300ms后执行搜索
  searchTimer = setTimeout(() => {
    searchModels()
  }, 300)
})

onMounted(() => {
  fetchModels()
})
</script>

<template>
  <div class="model-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title">
        <SidebarIcon name="model" class="title-icon" />
        <h2>模型管理</h2>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <el-input
            v-model="searchKeyword"
            placeholder=" 搜索模型名称..."
            :prefix-icon="Search"
            clearable
            @clear="clearSearch"
            style="width: 300px"
          />
        </div>
        
        <div class="action-buttons">
          <el-button 
            :icon="Refresh" 
            @click="fetchModels"
            :loading="loading"
            class="refresh-btn"
          >
             刷新
          </el-button>
          <el-button 
            type="primary" 
            :icon="Plus"
            @click="openCreateDialog"
            class="add-btn"
          >
             添加模型
          </el-button>
        </div>
      </div>
    </div>

    <!-- 模型列表 -->
    <div class="model-container" v-loading="loading">
      <!-- 列表头部 -->
      <div class="list-header" v-if="models.length > 0">
        <div class="col-name">模型名称</div>
        <div class="col-provider">提供商</div>
        <div class="col-type">模型类型</div>
        <div class="col-url">Base URL</div>
        <div class="col-actions">操作</div>
      </div>

      <!-- 列表内容 -->
      <div class="model-list" v-if="models.length > 0">
        <div 
          v-for="model in models" 
          :key="model.llm_id" 
          class="model-row"
        >
          <div class="col-name">
            <div class="name-info">
              <div class="provider-avatar" :class="model.llm_type.toLowerCase()">
                <span>{{ model.model?.[0] || '?' }}</span>
              </div>
              <span class="model-name">{{ model.model }}</span>
              <span class="official-tag" v-if="isOfficialModel(model)">官方</span>
            </div>
          </div>
          <div class="col-provider">
            <span class="provider-name">{{ model.provider }}</span>
          </div>
          <div class="col-type">
            <span class="type-badge" :class="model.llm_type.toLowerCase()">
              {{ model.llm_type }}
            </span>
          </div>
          <div class="col-url">
            <el-tooltip 
              :content="model.base_url" 
              placement="top" 
              :show-after="500"
              effect="light"
              popper-class="url-tooltip"
            >
              <span class="url-text">{{ truncateUrl(model.base_url, 40) }}</span>
            </el-tooltip>
          </div>
          <div class="col-actions" @click.stop>
            <el-tooltip content="编辑" placement="top">
              <button 
                class="action-btn edit-btn" 
                @click="openEditDialog(model)"
                :disabled="isOfficialModel(model)"
                :class="{ 'disabled': isOfficialModel(model) }"
              >
                <el-icon><Edit /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip content="删除" placement="top">
              <button 
                class="action-btn delete-btn" 
                @click="deleteModel(model)"
                :disabled="isOfficialModel(model)"
                :class="{ 'disabled': isOfficialModel(model) }"
              >
                <el-icon><Delete /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="models.length === 0 && !loading" class="empty-state">
        <div class="empty-icon">
          <SidebarIcon name="model" />
        </div>
        <h3>暂无模型</h3>
        <p>点击上方按钮添加您的第一个AI模型</p>
        <el-button 
          type="primary" 
          :icon="Plus"
          @click="openCreateDialog"
          size="large"
        >
          添加模型
        </el-button>
      </div>
    </div>

    <!-- 创建模型对话框 -->
    <div v-if="createDialogVisible" class="dialog-overlay" @click="createDialogVisible = false">
      <div class="dialog-container" @click.stop>
        <!-- 对话框主体 -->
        <div class="dialog-body">
          <div class="form-row">
            <div class="form-item">
              <label class="form-label">
                <span class="label-text">模型名称</span>
                <span class="required-mark">*</span>
              </label>
              <div class="input-wrapper">
                <input 
                  v-model="createForm.model"
                  type="text" 
                  placeholder="例如：qwen-max"
                  maxlength="50"
                  class="form-input"
                />
              </div>
            </div>

            <div class="form-item">
              <label class="form-label">
                <span class="label-text">提供商</span>
                <span class="required-mark">*</span>
              </label>
              <div class="input-wrapper">
                <input 
                  v-model="createForm.provider"
                  type="text" 
                  placeholder="例如：通义千问"
                  maxlength="50"
                  class="form-input"
                />
              </div>
            </div>

            <div class="form-item">
              <label class="form-label">
                <span class="label-text">基础URL</span>
                <span class="required-mark">*</span>
              </label>
              <div class="input-wrapper">
                <input 
                  v-model="createForm.base_url"
                  type="text" 
                  placeholder="例如：https://api.openai.com/v1"
                  maxlength="200"
                  class="form-input"
                />
              </div>
            </div>

            <div class="form-item">
              <label class="form-label">
                <span class="label-text">API密钥</span>
                <span class="required-mark">*</span>
              </label>
              <div class="input-wrapper api-key-wrapper">
                <input 
                  v-model="createForm.api_key"
                  :type="showApiKey ? 'text' : 'password'" 
                  placeholder="请输入您的API密钥"
                  maxlength="200"
                  class="form-input api-key-input"
                />
                <span class="toggle-password" @click="showApiKey = !showApiKey">
                  <el-icon v-if="showApiKey"><View /></el-icon>
                  <el-icon v-else><Hide /></el-icon>
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 对话框底部 -->
        <div class="dialog-footer">
          <button 
            class="dialog-btn cancel-btn" 
            @click.stop="createDialogVisible = false"
          >
            <span class="btn-icon">❌</span>
            <span class="btn-text">取消</span>
          </button>
          <button 
            class="dialog-btn confirm-btn" 
            :class="{ 'disabled': !createForm.model || !createForm.api_key || !createForm.base_url || !createForm.provider }"
            :disabled="!createForm.model || !createForm.api_key || !createForm.base_url || !createForm.provider || createLoading"
            @click.stop="handleCreate"
          >
            <span v-if="createLoading" class="btn-icon loading">⏳</span>
            <span v-else class="btn-icon">✅</span>
            <span class="btn-text">{{ createLoading ? '创建中...' : '确定创建' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认对话框 -->
    <div v-if="deleteDialogVisible" class="dialog-overlay" @click="cancelDelete">
      <div class="delete-dialog-container" @click.stop>
        <!-- 对话框主体 -->
        <div class="delete-dialog-body">
          <p v-if="modelToDelete">
            确定要删除模型 <strong>"{{ modelToDelete.model }}"</strong> 吗？
          </p>
        </div>
        
        <!-- 对话框底部 -->
        <div class="delete-dialog-footer">
          <button 
            class="delete-dialog-btn cancel-btn" 
            @click="cancelDelete"
            :disabled="deleteLoading"
          >
            取消
          </button>
          <button 
            class="delete-dialog-btn confirm-btn" 
            :disabled="deleteLoading"
            @click="confirmDelete"
          >
            {{ deleteLoading ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.model-page {
  padding: 32px;
  min-height: 100vh;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
    padding: 20px 28px;
    border-radius: 16px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.06);
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
        background: linear-gradient(90deg, #409eff, #3a7be2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
    }
    
    .header-actions {
      display: flex;
      align-items: center;
      gap: 16px;
      
      .search-box {
        margin-right: 12px;
        
        :deep(.el-input__wrapper) {
          border-radius: 8px;
          transition: all 0.3s;
          border: 1px solid #dcdfe6;
          
          &:hover {
            border-color: #409eff;
            box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.2);
          }
        }
      }
      
      .action-buttons {
        display: flex;
        gap: 12px;
        
        .el-button {
          border-radius: 8px;
          padding: 12px 20px;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.3s;
          
          &:hover {
            transform: translateY(-2px);
          }
          
          &.refresh-btn {
            &:hover {
              background-color: #67c23a;
              border-color: #67c23a;
              color: white;
            }
          }
          
          &.add-btn {
            background: linear-gradient(135deg, #409eff 0%, #3a7be2 100%);
            border: none;
            box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
            
            &:hover {
              background: linear-gradient(135deg, #66b1ff 0%, #409eff 100%);
              box-shadow: 0 6px 16px rgba(64, 158, 255, 0.3);
            }
          }
        }
      }
    }
  }
  
  // 列表容器
  .model-container {
    background: #ffffff;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
    min-height: 300px;

    // 列表头部
    .list-header {
      display: flex;
      align-items: center;
      padding: 14px 24px;
      background: #f8fafc;
      border-bottom: 1px solid #e5e7eb;
      font-size: 12px;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.5px;

      .col-name { flex: 0 0 240px; }
      .col-provider { flex: 0 0 120px; }
      .col-type { flex: 0 0 120px; text-align: center; padding-right: 64px; }
      .col-url { flex: 1; min-width: 200px; padding-left: 32px; }
      .col-actions { flex: 0 0 100px; text-align: right; }
    }

    // 列表内容
    .model-list {
      .model-row {
        display: flex;
        align-items: center;
        padding: 16px 24px;
        border-bottom: 1px solid #f1f5f9;
        transition: all 0.2s ease;

        &:last-child {
          border-bottom: none;
        }

        &:hover {
          background: #f8fafc;

          .col-name .name-info .provider-avatar {
            transform: scale(1.05);
            box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
          }

          .col-actions .action-btn {
            opacity: 1;
          }
        }

        .col-name {
          flex: 0 0 240px;

          .name-info {
            display: flex;
            align-items: center;
            gap: 12px;

            .provider-avatar {
              width: 36px;
              height: 36px;
              border-radius: 10px;
              display: flex;
              align-items: center;
              justify-content: center;
              flex-shrink: 0;
              transition: all 0.2s ease;
              color: white;
              font-size: 16px;
              font-weight: 700;

              &.llm {
                background: linear-gradient(135deg, #409eff 0%, #3a7be2 100%);
              }
              &.embedding {
                background: linear-gradient(135deg, #67c23a 0%, #529b2e 100%);
              }
              &.rerank {
                background: linear-gradient(135deg, #e6a23c 0%, #d9b55b 100%);
              }
            }

            .model-name {
              font-size: 15px;
              font-weight: 600;
              color: #1e293b;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }

            .official-tag {
              font-size: 11px;
              font-weight: 600;
              color: #e6a23c;
              background: #fef6e4;
              border: 1px solid #f8d4a5;
              border-radius: 20px;
              padding: 2px 8px;
              flex-shrink: 0;
            }
          }
        }

        .col-provider {
          flex: 0 0 120px;
          padding-right: 8px;

          .provider-name {
            font-size: 14px;
            font-weight: 500;
            color: #64748b;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }

        .col-type {
          flex: 0 0 120px;
          text-align: center;
          padding-right: 64px;

          .type-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;

            .el-icon {
              font-size: 14px;
            }

            &.llm {
              background: rgba(64, 158, 255, 0.1);
              color: #409eff;
            }
            &.embedding {
              background: rgba(103, 194, 58, 0.1);
              color: #67c23a;
            }
            &.rerank {
              background: rgba(230, 162, 60, 0.1);
              color: #e6a23c;
            }
          }
        }

        .col-url {
          flex: 1;
          min-width: 200px;
          padding-left: 32px;
          padding-right: 16px;

          .url-text {
            font-size: 13px;
            color: #64748b;
            font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
          }
        }

        .col-actions {
          flex: 0 0 100px;
          display: flex;
          justify-content: flex-end;
          gap: 8px;

          .action-btn {
            width: 32px;
            height: 32px;
            border: 1px solid transparent;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            opacity: 0.6;
            background: transparent;

            .el-icon {
              font-size: 16px;
            }

            &.edit-btn {
              color: #409eff;

              &:hover:not(.disabled) {
                background: rgba(64, 158, 255, 0.1);
                border-color: rgba(64, 158, 255, 0.3);
                opacity: 1;
              }
            }

            &.delete-btn {
              color: #f56c6c;

              &:hover:not(.disabled) {
                background: rgba(245, 108, 108, 0.1);
                border-color: rgba(245, 108, 108, 0.3);
                opacity: 1;
              }
            }

            &.disabled {
              opacity: 0.3;
              cursor: not-allowed;
            }
          }
        }
      }
    }

    // 空状态
    .empty-state {
      text-align: center;
      padding: 80px 30px;

      .empty-icon {
        margin-bottom: 16px;

        .empty-emoji {
          font-size: 56px;
          opacity: 0.6;
        }
      }

      h3 {
        font-size: 18px;
        font-weight: 600;
        color: #475569;
        margin-bottom: 8px;
      }

      p {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 24px;
      }

      .el-button {
        border-radius: 8px;
        background: linear-gradient(135deg, #409eff 0%, #3a7be2 100%);
        border: none;
        box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
        transition: all 0.3s;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(64, 158, 255, 0.3);
          background: linear-gradient(135deg, #66b1ff 0%, #409eff 100%);
        }
      }
    }
  }
}

/* 添加URL工具提示样式 */
:deep(.url-tooltip) {
  max-width: 400px;
  word-break: break-all;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  padding: 10px 14px;
}

// 响应式调整
@media (max-width: 768px) {
  .model-page {
    padding: 20px;

    .page-header {
      flex-direction: column;
      align-items: stretch;
      gap: 16px;
      padding: 20px;

      h2 {
        text-align: center;
        justify-content: center;
      }

      .header-actions {
        flex-direction: column;
        align-items: stretch;

        .search-box {
          margin-right: 0;
          margin-bottom: 12px;
        }

        .action-buttons {
          justify-content: center;
        }
      }
    }

    .model-container {
      .list-header {
        display: none;
      }

      .model-list .model-row {
        flex-wrap: wrap;
        gap: 8px;

        .col-name { flex: 1 1 100%; }
        .col-provider { flex: 1 1 50%; }
        .col-type { flex: 1 1 50%; text-align: left; }
        .col-url { flex: 1 1 100%; }
        .col-actions { flex: 1 1 100%; justify-content: flex-start; }
      }
    }
  }
}

/* 添加模型对话框样式 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.9) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1) translateY(0);
  }
}

.dialog-container {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: white;
  border-radius: 20px;
  box-shadow: 
    0 20px 60px rgba(0, 0, 0, 0.3),
    0 8px 32px rgba(0, 0, 0, 0.15);
  width: 92%;
  max-width: 500px;
  max-height: 88vh;
  overflow: hidden;
  animation: slideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  border: 1px solid rgba(255, 255, 255, 0.2);
}



/* 对话框主体 */
.dialog-body {
  padding: 36px;
  max-height: 65vh;
  overflow-y: auto;
  background: #fafbfc;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-item {
  flex: 1;
  min-width: 0;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #2d3748;
}

.label-text {
  color: #374151;
}

.required-mark {
  color: #ef4444;
  font-weight: 700;
  font-size: 16px;
}

.input-wrapper,
.select-wrapper {
  position: relative;
}

.api-key-wrapper {
  display: flex;
  align-items: center;
}

.api-key-input {
  padding-right: 44px !important;
}

.toggle-password {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  cursor: pointer;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s ease;

  .el-icon {
    font-size: 18px;
  }

  &:hover {
    color: #4f46e5;
  }
}

.form-input {
  width: 100%;
  padding: 16px 20px;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
  background: white;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: #4f46e5;
  box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
  transform: translateY(-1px);
}

.form-input::placeholder {
  color: #9ca3af;
  font-weight: 400;
}

.char-count {
  position: absolute;
  right: 16px;
  bottom: -24px;
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

/* 对话框底部 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  padding: 20px 36px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 28px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 120px;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.dialog-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.dialog-btn:hover::before {
  left: 100%;
}

.cancel-btn {
  background: #f1f5f9;
  color: #64748b;
  border: 2px solid #e2e8f0;
}

.cancel-btn:hover {
  background: #e2e8f0;
  color: #475569;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
}

.confirm-btn {
  background: #f1f5f9;
  color: #64748b;
  border: 2px solid #e2e8f0;
}

.confirm-btn:hover:not(.disabled) {
  background: #e2e8f0;
  color: #475569;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
}

.confirm-btn.disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background: #9ca3af;
}

.btn-icon {
  font-size: 16px;
  display: flex;
  align-items: center;
}

.btn-icon.loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.btn-text {
  font-weight: 600;
}

/* 对话框响应式设计 */
@media (max-width: 768px) {
  .dialog-container {
    width: 95%;
    margin: 10px;
    max-height: 95vh;
  }
  
  .dialog-body {
    padding: 24px 20px;
  }
  
  .form-row {
    flex-direction: column;
    gap: 16px;
  }
  
  .dialog-footer {
    padding: 16px;
    flex-direction: column;
  }
  
  .dialog-btn {
    width: 100%;
  }
}

/* 删除确认对话框样式 */
.delete-dialog-container {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  width: 90%;
  max-width: 400px;
  overflow: hidden;
  animation: slideIn 0.3s ease-out;
  border: 1px solid #e5e7eb;
}

.delete-dialog-body {
  padding: 32px 28px 24px;
  text-align: center;
  
  p {
    margin: 0;
    font-size: 16px;
    color: #374151;
    line-height: 1.5;
    
    strong {
      color: #1f2937;
      font-weight: 600;
    }
  }
}

.delete-dialog-footer {
  display: flex;
  gap: 12px;
  padding: 0 28px 28px;
}

.delete-dialog-btn {
  flex: 1;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.delete-dialog-btn.cancel-btn {
  background: #f9fafb;
  color: #6b7280;
  border: 1px solid #d1d5db;
}

.delete-dialog-btn.cancel-btn:hover:not(:disabled) {
  background: #f3f4f6;
  color: #374151;
}

.delete-dialog-btn.confirm-btn {
  background: #3b82f6;
  color: white;
  border: 1px solid #3b82f6;
}

.delete-dialog-btn.confirm-btn:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.delete-dialog-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 删除对话框响应式设计 */
@media (max-width: 768px) {
  .delete-dialog-container {
    width: 95%;
    margin: 10px;
  }
  
  .delete-dialog-body {
    padding: 24px 20px 20px;
    
    p {
      font-size: 15px;
    }
  }
  
  .delete-dialog-footer {
    padding: 0 20px 24px;
  }
}
</style>