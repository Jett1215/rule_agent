import { request } from "../utils/request"

// 统一响应模型
export interface UnifiedResponse<T = any> {
  status_code: number
  status_message: string
  data?: T
}

// 知识库文件状态枚举
export enum KnowledgeFileStatus {
  FAIL = "❌ 失败",
  PROCESS = "🚀 进行中", 
  SUCCESS = "✅ 完成"
}

// 知识库文件响应类型
export interface KnowledgeFileResponse {
  id: string
  file_name: string
  knowledge_id: string
  status: KnowledgeFileStatus
  user_id: string
  oss_url: string
  file_size: number
  create_time: string
  update_time: string
}

// 知识库文件创建请求
export interface KnowledgeFileCreateRequest {
  knowledge_id: string
  file_url: string
}

// 知识库文件删除请求
export interface KnowledgeFileDeleteRequest {
  knowledge_file_id: string
}

// 文件上传到知识库
export function createKnowledgeFileAPI(data: KnowledgeFileCreateRequest) {
  return request<UnifiedResponse<null>>({
    url: '/api/v1/knowledge_file/create',
    method: 'POST',
    data,
    timeout: 0  // 等待完整解析和入库结果
  })
}

// 查询知识库文件列表
export function getKnowledgeFileListAPI(knowledge_id: string) {
  return request<UnifiedResponse<KnowledgeFileResponse[]>>({
    url: '/api/v1/knowledge_file/select',
    method: 'GET',
    params: { knowledge_id }
  })
}

export interface StoredChunk {
  id: string
  content: string
  character_count: number
  metadata: {
    chunk_id?: string
    file_id?: string
    file_name?: string
    knowledge_id?: string
    update_time?: string
    summary?: string
    is_summary?: boolean
    [key: string]: unknown
  }
  vector_dimension: number
  vector_preview: number[]
}

export interface FileChunksResult {
  items: StoredChunk[]
  total: number
  content_count: number
  summary_count: number
  page: number
  page_size: number
}

export function getFileChunksAPI(knowledge_file_id: string, page: number, page_size: number, search: string) {
  return request<UnifiedResponse<FileChunksResult>>({
    url: '/api/v1/knowledge_file/chunks',
    method: 'GET',
    params: { knowledge_file_id, page, page_size, search }
  })
}

export function getChunkVectorAPI(knowledge_file_id: string, record_id: string) {
  return request<UnifiedResponse<{ id: string; embedding: number[] }>>({
    url: '/api/v1/knowledge_file/chunks/vector',
    method: 'GET',
    params: { knowledge_file_id, record_id }
  })
}

export function exportFileChunksAPI(knowledge_file_id: string, format: 'txt' | 'json') {
  return request<Blob>({
    url: '/api/v1/knowledge_file/chunks/export',
    method: 'GET',
    params: { knowledge_file_id, format },
    responseType: 'blob',
    timeout: 0
  })
}

// 删除知识库文件
export function deleteKnowledgeFileAPI(data: KnowledgeFileDeleteRequest) {
  return request<UnifiedResponse<null>>({
    url: '/api/v1/knowledge_file/delete',
    method: 'DELETE',
    data: {
      knowledge_file_id: data.knowledge_file_id
    }
  })
}

// 格式化文件大小
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 获取文件扩展名
export function getFileExtension(filename: string): string {
  return filename.slice((filename.lastIndexOf(".") - 1 >>> 0) + 2)
}

// 根据文件扩展名获取文件类型
export function getFileType(filename: string): string {
  const ext = getFileExtension(filename).toLowerCase()
  
  const fileTypes: { [key: string]: string } = {
    pdf: 'PDF文档',
    doc: 'Word文档',
    docx: 'Word文档',
    txt: '文本文件',
    md: 'Markdown文档',
    xls: 'Excel表格',
    xlsx: 'Excel表格',
    ppt: 'PowerPoint演示',
    pptx: 'PowerPoint演示',
    jpg: '图片文件',
    jpeg: '图片文件',
    png: '图片文件',
    gif: '图片文件',
    bmp: '图片文件'
  }
  
  return fileTypes[ext] || '未知文件'
}
