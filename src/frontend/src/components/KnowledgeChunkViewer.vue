<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElDialog, ElEmpty, ElInput, ElMessage, ElPagination, ElTag } from 'element-plus'
import {
  exportFileChunksAPI, getChunkVectorAPI, getFileChunksAPI,
  type KnowledgeFileResponse, type StoredChunk
} from '../apis/knowledge-file'

const props = defineProps<{ file: KnowledgeFileResponse; modelValue: boolean }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: boolean): void }>()
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const items = ref<StoredChunk[]>([])
const page = ref(1)
const pageSize = ref(10)
const search = ref('')
const appliedSearch = ref('')
const total = ref(0)
const contentCount = ref(0)
const summaryCount = ref(0)
const loading = ref(false)
const error = ref('')
const exporting = ref(false)
const vectors = ref<Record<string, number[]>>({})
const vectorLoading = ref<Record<string, boolean>>({})
const vectorOpen = ref<Record<string, boolean>>({})
let requestId = 0
let active = true

async function fetchChunks() {
  const currentRequest = ++requestId
  loading.value = true
  error.value = ''
  items.value = []
  try {
    const response = await getFileChunksAPI(props.file.id, page.value, pageSize.value, appliedSearch.value)
    if (!active || currentRequest !== requestId) return
    if (response.data.status_code !== 200 || !response.data.data) {
      throw new Error(response.data.status_message || '获取 Chunk 失败')
    }
    const result = response.data.data
    items.value = result.items
    total.value = result.total
    contentCount.value = result.content_count
    summaryCount.value = result.summary_count
  } catch (err: any) {
    if (active && currentRequest === requestId) {
      error.value = err.response?.data?.detail || err.message || '获取 Chunk 失败'
    }
  } finally {
    if (active && currentRequest === requestId) loading.value = false
  }
}

function applySearch() {
  appliedSearch.value = search.value.trim()
  page.value = 1
  fetchChunks()
}

async function toggleVector(chunk: StoredChunk) {
  vectorOpen.value[chunk.id] = !vectorOpen.value[chunk.id]
  if (!vectorOpen.value[chunk.id] || vectors.value[chunk.id] || vectorLoading.value[chunk.id]) return
  vectorLoading.value[chunk.id] = true
  try {
    const response = await getChunkVectorAPI(props.file.id, chunk.id)
    if (!active) return
    if (response.data.status_code !== 200 || !response.data.data) throw new Error('获取向量失败')
    vectors.value[chunk.id] = response.data.data.embedding
  } catch (err: any) {
    if (active) {
      vectorOpen.value[chunk.id] = false
      ElMessage.error(err.response?.data?.detail || '获取向量失败，请重试')
    }
  } finally {
    vectorLoading.value[chunk.id] = false
  }
}

async function exportChunks(format: 'txt' | 'json') {
  exporting.value = true
  try {
    const response = await exportFileChunksAPI(props.file.id, format)
    if (!active) return
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `${props.file.file_name.replace(/[\\/:*?"<>|]/g, '_')}_chunks.${format}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    if (active) ElMessage.error('导出失败，请重试')
  } finally {
    exporting.value = false
  }
}

onMounted(fetchChunks)
onUnmounted(() => { active = false; requestId++ })
</script>

<template>
  <el-dialog v-model="visible" title="查看 Chunk" width="min(960px, 94vw)" class="chunk-viewer-dialog">
    <div class="chunk-viewer">
      <div class="viewer-heading">
        <div class="file-heading">{{ file.file_name }}</div>
        <div class="counts">
          <el-tag>正文 {{ contentCount }} 块</el-tag>
          <el-tag type="success">摘要 {{ summaryCount }} 块</el-tag>
        </div>
      </div>
      <div class="viewer-toolbar">
        <el-input v-model="search" placeholder="搜索已入库正文或摘要（区分大小写）" clearable
          maxlength="200" @keyup.enter="applySearch" @clear="applySearch" />
        <el-button type="primary" @click="applySearch">搜索</el-button>
        <el-button :disabled="exporting || loading || !!error || contentCount + summaryCount === 0"
          @click="exportChunks('txt')">导出 TXT</el-button>
        <el-button :disabled="exporting || loading || !!error || contentCount + summaryCount === 0"
          @click="exportChunks('json')">导出 JSON</el-button>
      </div>
      <p class="viewer-note">导出包含该文件全部记录；JSON 包含完整向量。</p>
      <div v-loading="loading" class="chunk-list">
        <div v-if="error" class="viewer-error" role="alert">
          <p>{{ error }}</p><el-button @click="fetchChunks">重试</el-button>
        </div>
        <el-empty v-else-if="!loading && items.length === 0"
          :description="appliedSearch ? '没有匹配的 Chunk，试试其他关键词' : '该文件暂无已入库的 Chunk，请确认解析已成功完成'" />
        <article v-for="(chunk, index) in items" :key="chunk.id" class="chunk-card">
          <div class="chunk-title">
            <strong>记录 {{ (page - 1) * pageSize + index + 1 }}</strong>
            <el-tag :type="chunk.metadata.is_summary ? 'success' : 'info'" size="small">
              {{ chunk.metadata.is_summary ? '摘要' : '正文' }}
            </el-tag>
            <span>{{ chunk.character_count }} 字符 · {{ chunk.vector_dimension }} 维</span>
          </div>
          <pre class="chunk-content">{{ chunk.content }}</pre>
          <div v-if="!chunk.metadata.is_summary && chunk.metadata.summary" class="chunk-summary">
            <strong>摘要</strong><p>{{ chunk.metadata.summary }}</p>
          </div>
          <div class="chunk-source">
            <div>记录 ID：{{ chunk.id }}</div>
            <div>Chunk ID：{{ chunk.metadata.chunk_id || chunk.id }}</div>
            <div>来源：{{ file.file_name }} · 文件 ID：{{ chunk.metadata.file_id }}</div>
            <div>更新时间：{{ chunk.metadata.update_time || '未记录' }}</div>
          </div>
          <details class="metadata-details">
            <summary>查看全部元信息</summary>
            <pre>{{ JSON.stringify(chunk.metadata, null, 2) }}</pre>
          </details>
          <div class="vector-section">
            <div class="vector-preview">向量前 8 项：{{ chunk.vector_preview.map(n => n.toFixed(6)).join(', ') }}</div>
            <el-button size="small" :loading="vectorLoading[chunk.id]" @click="toggleVector(chunk)">
              {{ vectorOpen[chunk.id] ? '收起完整向量' : '展开完整向量' }}
            </el-button>
            <pre v-if="vectorOpen[chunk.id] && vectors[chunk.id]" class="full-vector">{{ JSON.stringify(vectors[chunk.id], null, 2) }}</pre>
          </div>
        </article>
      </div>
      <el-pagination v-if="!error && total > 0" v-model:current-page="page" v-model:page-size="pageSize"
        :total="total" :page-sizes="[5, 10, 20]" layout="total, sizes, prev, pager, next"
        :disabled="loading" @current-change="fetchChunks" @size-change="page = 1; fetchChunks()" />
    </div>
  </el-dialog>
</template>

<style scoped>
.viewer-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.file-heading { font-size: 18px; font-weight: 600; overflow-wrap: anywhere; color: var(--el-text-color-primary); }
.counts { display: flex; flex-shrink: 0; gap: 8px; }
.viewer-toolbar { display: flex; align-items: center; gap: 8px; }
.viewer-toolbar .el-button + .el-button { margin-left: 0; }
.viewer-note { color: var(--el-text-color-secondary); font-size: 12px; margin: 10px 0; }
.chunk-list { min-height: 160px; max-height: 58vh; overflow-y: auto; padding-right: 8px; margin-bottom: 18px; }
.chunk-card { border: 1px solid var(--el-border-color); border-radius: 10px; padding: 18px; margin-bottom: 14px; }
.chunk-title { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.chunk-title span:last-child { font-size: 12px; color: var(--el-text-color-secondary); }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; margin: 0; line-height: 1.7; }
.chunk-content { color: var(--el-text-color-primary); }
.chunk-summary { margin-top: 12px; padding: 12px; border-radius: 6px; background: var(--el-fill-color-light); }
.chunk-summary p { margin: 6px 0 0; white-space: pre-wrap; }
.chunk-source { margin-top: 16px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.metadata-details { margin-top: 12px; font-size: 12px; }
summary { cursor: pointer; color: var(--el-color-primary); }
.metadata-details pre, .full-vector { margin-top: 10px; background: var(--el-fill-color-light); padding: 12px; border-radius: 6px; font-family: monospace; max-height: 240px; overflow-y: auto; }
.vector-section { border-top: 1px solid var(--el-border-color-lighter); margin-top: 14px; padding-top: 12px; }
.vector-preview { color: var(--el-text-color-secondary); font-size: 12px; margin-bottom: 10px; overflow-wrap: anywhere; }
.viewer-error { text-align: center; padding: 30px; color: var(--el-color-danger); }
@media (max-width: 600px) {
  .viewer-heading { flex-direction: column; align-items: flex-start; }
  .viewer-toolbar { flex-wrap: wrap; }
  .viewer-toolbar .el-input { flex-basis: 100%; }
  .chunk-card { padding: 12px; }
}
</style>
