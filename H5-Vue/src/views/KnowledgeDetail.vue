<template>
  <div class="knowledge-detail">
    <div class="detail-header">
      <el-button @click="goBack" :icon="ArrowLeft">返回</el-button>
    </div>

    <div v-if="loading" class="loading-container">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <div v-else-if="knowledge" class="detail-content">
      <!-- 左侧信息区 -->
      <div class="left-panel">
        <el-card shadow="hover">
          <div class="knowledge-info">
            <el-avatar :src="imageUrl" :size="80" class="info-avatar">
              <el-icon :size="40"><Document /></el-icon>
            </el-avatar>
            <h2 class="info-name">{{ knowledge.name }}</h2>
            <div class="info-meta">
              <p><span class="label">创建时间：</span>{{ formatDate(knowledge.createdon) }}</p>
              <p><span class="label">文件数量：</span>{{ total }} 个</p>
            </div>
            <div class="info-prompt" v-if="knowledge.system_prompt">
              <p class="label">系统提示词：</p>
              <el-input
                v-model="knowledge.system_prompt"
                type="textarea"
                :rows="4"
                readonly
              />
            </div>
            <div class="info-actions">
              <el-button type="primary" @click="handleEdit">编辑</el-button>
              <el-button type="danger" :loading="deleteLoading" @click="handleDelete">删除</el-button>
              <el-button type="success" @click="handleChat">AI 对话</el-button>
              <el-button v-if="isSuperuser" type="warning" @click="openEvaluationDialog">创建评估</el-button>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 右侧文件列表区 -->
      <div class="right-panel">
        <el-card shadow="hover">
          <template #header>
            <div class="panel-header">
              <span>文件列表</span>
              <div class="header-actions">
                <el-input
                  v-model="searchKeyword"
                  placeholder="搜索文件名"
                  style="width: 200px; margin-right: 10px"
                  clearable
                  @clear="loadDocuments"
                  @keyup.enter="loadDocuments"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
                <el-button type="primary" @click="handleUpload">上传文档</el-button>
                <el-button type="primary" :loading="parseLoading" :disabled="!canParse" @click="handleParse">解析文档</el-button>
                <el-button type="danger" :loading="batchDeleteLoading" :disabled="!selectedRows.length" @click="handleBatchDelete">
                  删除选中
                </el-button>
              </div>
            </div>
          </template>

          <el-table
            ref="tableRef"
            :data="documents"
            style="width: 100%"
            @selection-change="handleSelectionChange"
            v-loading="docLoading"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="name" label="文件名" min-width="200" show-overflow-tooltip />
            <el-table-column prop="size" label="文件大小" width="120">
              <template #default="{ row }">
                {{ formatSize(row.size) }}
              </template>
            </el-table-column>
            <el-table-column prop="chunk" label="分块数" width="100" />
            <el-table-column prop="parse_status" label="解析状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusMap[row.parse_status]?.type || 'info'" size="small">
                  {{ statusMap[row.parse_status]?.text || row.parse_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createdon" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.createdon) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleDownload(row)">下载</el-button>
                <!-- <el-button link type="danger" @click="handleDeleteDoc(row)">删除</el-button> -->
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-container">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="total"
              layout="total, prev, pager, next"
              @current-change="loadDocuments"
            />
          </div>
        </el-card>
      </div>
    </div>

    <!-- 新建/编辑知识库表单 -->
    <KnowledgeForm
      v-model="formVisible"
      :knowledge="currentKnowledge"
      @success="handleFormSuccess"
    />

    <!-- 上传文件对话框 -->
    <el-dialog v-model="uploadVisible" title="上传文件" width="400px" @close="handleUploadClose">
      <el-upload
        ref="uploadRef"
        class="upload-demo"
        drag
        action="#"
        :auto-upload="false"
        :limit="10"
        :on-change="handleFileChange"
        :file-list="uploadFileList"
        multiple
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持任意文件类型，单个文件不超过50MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
      </template>
    </el-dialog>
    <!-- 创建评估对话框 -->
    <el-dialog v-model="evaluationVisible" title="创建 RAG 评估" width="520px">
      <el-form label-width="100px">
        <el-form-item label="评估名称">
          <el-input v-model="evaluationForm.name" placeholder="默认使用知识库名称" />
        </el-form-item>
        <el-form-item label="消息时间">
          <el-date-picker
            v-model="evaluationForm.timeRange"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="评估用户">
          <el-select v-model="evaluationForm.selectedUserIds" multiple filterable clearable placeholder="不选表示全部用户" style="width: 100%">
            <el-option v-for="user in evaluationUsers" :key="user.id" :label="user.username" :value="user.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert v-if="precheckCount !== null" :title="`可生成 ${precheckCount} 条完整问答数据`" type="info" :closable="false" />
      <template #footer>
        <el-button @click="evaluationVisible = false">取消</el-button>
        <el-button :loading="prechecking" @click="precheckEvaluation">预检</el-button>
        <el-button type="primary" :loading="creatingEvaluation" @click="createEvaluation">创建评估</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, Loading, Search, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import req from '../common/interface'
import taskStore from '../common/taskStore'
import KnowledgeForm from '../components/knowledge/KnowledgeForm.vue'

const router = useRouter()
const route = useRoute()

const knowledgeId = computed(() => route.params.id)

const loading = ref(false)
const docLoading = ref(false)
const deleteLoading = ref(false)
const batchDeleteLoading = ref(false)
const parseLoading = ref(false)
const knowledge = ref(null)
const documents = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchKeyword = ref('')
const selectedRows = ref([])
const formVisible = ref(false)
const currentKnowledge = ref(null)
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadRef = ref(null)
const uploadFileList = ref([])
const tableRef = ref(null)
const isSuperuser = ref(false)
const evaluationVisible = ref(false)
const prechecking = ref(false)
const creatingEvaluation = ref(false)
const precheckCount = ref(null)
const evaluationUsers = ref([])
const evaluationForm = ref({ name: '', timeRange: [], selectedUserIds: [] })

const imageUrl = computed(() => {
  if (knowledge.value?.image) {
    return req.getBaseUrl() + knowledge.value.image
  }
  return ''
})

const statusMap = {
  unparsed: { text: '未解析', type: 'info' },
  parsing: { text: '解析中', type: 'warning' },
  parsed: { text: '解析成功', type: 'success' },
  failed: { text: '解析失败', type: 'danger' }
}

const canParse = computed(() => {
  if (!selectedRows.value.length) return false
  return selectedRows.value.every(row => row.parse_status === 'unparsed' || row.parse_status === 'failed')
})

onMounted(async () => {
  loadKnowledge()
  loadDocuments()
  try {
    const response = await req.get('/getuser/')
    isSuperuser.value = !!response.data.is_superuser
  } catch (error) {
    isSuperuser.value = false
  }
})

async function loadKnowledge() {
  loading.value = true
  try {
    const res = await req.get(`/knowledge/${knowledgeId.value}/`)
    knowledge.value = res.data
  } catch (e) {
    ElMessage.error('加载知识库详情失败')
    router.replace('/')
  } finally {
    loading.value = false
  }
}

async function loadDocuments() {
  docLoading.value = true
  try {
    let url = `/document/list/?knowledge_id=${knowledgeId.value}&page=${currentPage.value}&page_size=${pageSize.value}`
    if (searchKeyword.value) {
      url += `&search=${encodeURIComponent(searchKeyword.value)}`
    }
    const res = await req.get(url)
    documents.value = res.data.results || []
    total.value = res.data.count || 0
  } catch (e) {
    ElMessage.error('加载文件列表失败')
  } finally {
    docLoading.value = false
  }
}

function handleEdit() {
  currentKnowledge.value = knowledge.value
  formVisible.value = true
}

function handleDelete() {
  ElMessageBox.confirm('确定要删除该知识库吗？删除后无法恢复。', '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    deleteLoading.value = true
    try {
      await req.post(`/knowledge/${knowledgeId.value}/delete/`)
      ElMessage.success('删除成功')
      router.replace('/')
    } catch (e) {
      console.error(e)
      ElMessage.error(e?.response?.data?.error || '删除失败')
    } finally {
      deleteLoading.value = false
    }
  }).catch(() => {})
}

function handleChat() {
  router.push({
    path: '/Chat',
    query: {
      knowledge_repository_id: knowledgeId.value
    }
  })
}

async function openEvaluationDialog() {
  evaluationForm.value = { name: `${knowledge.value?.name || ''} 评估`, timeRange: [], selectedUserIds: [] }
  precheckCount.value = null
  try {
    const response = await req.get('/evaluation/precheck/')
    evaluationUsers.value = response.data.users || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载用户列表失败')
    return
  }
  evaluationVisible.value = true
}

function evaluationPayload() {
  const [conversation_start_at, conversation_end_at] = evaluationForm.value.timeRange || []
  return {
    knowledge_repository_id: knowledgeId.value,
    name: evaluationForm.value.name,
    conversation_start_at,
    conversation_end_at,
    selected_user_ids: evaluationForm.value.selectedUserIds
  }
}

async function precheckEvaluation() {
  prechecking.value = true
  try {
    const response = await req.post('/evaluation/precheck/', evaluationPayload())
    precheckCount.value = response.data.available_count || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '预检失败')
  } finally {
    prechecking.value = false
  }
}

async function createEvaluation() {
  creatingEvaluation.value = true
  try {
    const response = await req.post('/evaluation/', evaluationPayload())
    evaluationVisible.value = false
    ElMessage.success('评估已创建')
    router.push(`/evaluation/${response.data.id}`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '创建评估失败')
  } finally {
    creatingEvaluation.value = false
  }
}

function handleFormSuccess() {
  loadKnowledge()
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

function handleUpload() {
  uploadFileList.value = []
  uploadVisible.value = true
}

function handleFileChange(file, fileList) {
  uploadFileList.value = fileList
}

function handleUploadClose() {
  uploadFileList.value = []
  uploadRef.value?.clearFiles()
}

async function handleFileUpload(option) {
  const formData = new FormData()
  formData.append('knowledge_repository_id', knowledgeId.value)
  formData.append('file', option.file)
  return req.post('/document/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

async function submitUpload() {
  if (!uploadFileList.value.length) {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  let successCount = 0
  let failCount = 0

  for (const fileItem of uploadFileList.value) {
    try {
      await handleFileUpload({ file: fileItem.raw })
      successCount++
    } catch (e) {
      failCount++
    }
  }

  uploading.value = false

  if (successCount > 0) {
    ElMessage.success(`成功上传 ${successCount} 个文件`)
    uploadVisible.value = false
    uploadFileList.value = []
    uploadRef.value?.clearFiles()
    loadDocuments()
  }
  if (failCount > 0) {
    ElMessage.warning(`${failCount} 个文件上传失败`)
  }
}

function handleDownload(row) {
  window.open(req.getBaseUrl() + `/document/${row.id}/download/`, '_blank')
}

function handleDeleteDoc(row) {
  ElMessageBox.confirm(`确定要删除文件 "${row.name}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await req.post(`/document/${row.id}/delete/`)
      ElMessage.success('删除成功')
      loadDocuments()
    } catch (e) {
      ElMessage.error(e?.response?.data?.error || '删除失败')
    }
  }).catch(() => {})
}

function handleBatchDelete() {
  if (!selectedRows.value.length) return

  ElMessageBox.confirm(`确定要删除选中的 ${selectedRows.value.length} 个文件吗？`, '批量删除', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    batchDeleteLoading.value = true
    let successCount = 0
    let failCount = 0
    let firstError = ''
    for (const row of selectedRows.value) {
      try {
        await req.post(`/document/${row.id}/delete/`)
        successCount++
      } catch (e) {
        failCount++
        if (!firstError) {
          firstError = e?.response?.data?.error || '删除失败'
        }
      }
    }
    batchDeleteLoading.value = false
    if (failCount) {
      ElMessage.warning(`成功删除 ${successCount} 个文件，${failCount} 个失败：${firstError}`)
    } else {
      ElMessage.success(`成功删除 ${successCount} 个文件`)
    }
    tableRef.value?.clearSelection()
    loadDocuments()
  }).catch(() => {})
}

function handleParse(){
  // 多选解析
  if (!selectedRows.value.length) return
  ElMessageBox.confirm(`确定要解析选中的 ${selectedRows.value.length} 个文档吗？`, '解析确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    parseLoading.value = true
    try {
      await req.post('/document/parse/task/', {
        document_ids: selectedRows.value.map(r => r.id)
      })
      // 立即本地刷新为解析中，避免重复提交并即时反馈
      selectedRows.value.forEach(row => {
        row.parse_status = 'parsing'
      })
      tableRef.value?.clearSelection()
      selectedRows.value = []
      ElMessage.success('解析任务已创建，可在右上角任务列表查看进度')
      taskStore.notifyTaskCreated()
    } catch (e) {
      ElMessage.error(e?.response?.data?.error || '解析任务创建失败')
    } finally {
      parseLoading.value = false
    }
  }).catch(() => {})
}

function goBack() {
  router.back()
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(2)} ${units[i]}`
}
</script>

<style scoped>
.knowledge-detail {
  padding: 20px;
}

.detail-header {
  margin-bottom: 20px;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #909399;
  padding: 60px;
}

.detail-content {
  display: flex;
  gap: 20px;
}

.left-panel {
  width: 300px;
  flex-shrink: 0;
}

.right-panel {
  flex: 1;
  min-width: 0;
}

.knowledge-info {
  text-align: center;
}

.info-avatar {
  margin-bottom: 16px;
  background-color: #f5f7fa;
}

.info-name {
  margin: 0 0 16px 0;
  font-size: 20px;
  color: #303133;
}

.info-meta {
  text-align: left;
  margin-bottom: 16px;
  color: #606266;
  font-size: 14px;
}

.info-meta p {
  margin: 8px 0;
}

.info-meta .label {
  color: #909399;
}

.info-prompt {
  text-align: left;
  margin-bottom: 16px;
}

.info-prompt .label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 8px;
  display: block;
}

.info-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.upload-demo {
  text-align: center;
}

:deep(.el-upload-dragger) {
  padding: 40px;
}
</style>
