<template>
  <div class="home-page">
    <el-collapse v-model="activeNames">
      <el-collapse-item title="知识库" name="knowledge">
        <div class="knowledge-section">
          <!-- 加载状态 -->
          <div v-if="loading" class="loading-container">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>

          <!-- 知识库卡片列表 -->
          <div v-else class="card-grid">
            <KnowledgeCard
              v-for="item in knowledgeList"
              :key="item.id"
              :knowledge="item"
              @click="handleCardClick"
            />

            <!-- 创建知识库卡片 -->
            <el-card class="action-card" shadow="hover" @click="handleCreate">
              <div class="action-content">
                <el-icon :size="40"><Plus /></el-icon>
                <span>创建知识库</span>
              </div>
            </el-card>

            <!-- 更多知识库卡片 -->
            <el-card
              v-if="hasMore"
              class="action-card"
              shadow="hover"
              @click="loadMore"
            >
              <div class="action-content">
                <el-icon :size="40"><MoreFilled /></el-icon>
                <span>更多知识库</span>
              </div>
            </el-card>
          </div>

          <!-- 分页 -->
          <div v-if="total > pageSize" class="pagination-container">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="total"
              layout="prev, pager, next"
              @current-change="loadKnowledge"
            />
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item title="聊天" name="chat">
        <div class="chat-section">
          <!-- 加载状态 -->
          <div v-if="chatLoading" class="loading-container">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>

          <!-- 聊天会话卡片列表 -->
          <div v-else class="card-grid">
            <ChatCard
              v-for="item in chatList"
              :key="item.id"
              :session="item"
              :repo-name="getRepoName(item.dim_knowledge_repository_id)"
              @click="handleChatCardClick"
            />

            <!-- 更多聊天卡片 -->
            <el-card class="action-card" shadow="hover" @click="handleChatMore">
              <div class="action-content">
                <el-icon :size="40"><MoreFilled /></el-icon>
                <span>更多聊天</span>
              </div>
            </el-card>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- 新建/编辑知识库表单 -->
    <KnowledgeForm
      v-model="formVisible"
      :knowledge="currentKnowledge"
      @success="handleFormSuccess"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, MoreFilled, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import req from '../common/interface'
import KnowledgeCard from '../components/knowledge/KnowledgeCard.vue'
import KnowledgeForm from '../components/knowledge/KnowledgeForm.vue'
import ChatCard from '../components/chat/ChatCard.vue'

const router = useRouter()

const activeNames = ref(['knowledge', 'chat'])
const loading = ref(false)
const knowledgeList = ref([])
const currentPage = ref(1)
const pageSize = ref(5)
const total = ref(0)
const formVisible = ref(false)
const currentKnowledge = ref(null)

const hasMore = ref(false)
const chatLoading = ref(false)
const chatList = ref([])
const knowledgeRepoMap = ref({})

async function loadKnowledge() {
  loading.value = true
  try {
    const res = await req.get(`/knowledge/list/?page=${currentPage.value}&page_size=${pageSize.value}`)
    knowledgeList.value = res.data.results || []
    total.value = res.data.count || 0
    hasMore.value = total.value > currentPage.value * pageSize.value
  } catch (e) {
    ElMessage.error('加载知识库列表失败')
  } finally {
    loading.value = false
  }
}

async function loadAllRepoNames() {
  try {
    const res = await req.get('/chat/repositories/')
    const repos = res.data || []
    repos.forEach(repo => {
      knowledgeRepoMap.value[repo.id] = repo.name
    })
  } catch (e) {
    // 静默失败，因为卡片可以只显示空关联
  }
}

async function loadChatSessions() {
  chatLoading.value = true
  try {
    const res = await req.get('/chat/sessions/?pageIndex=1&pageSize=5')
    chatList.value = res.data || []
  } catch (e) {
    ElMessage.error('加载聊天会话失败')
  } finally {
    chatLoading.value = false
  }
}

function getRepoName(repoId) {
  if (!repoId) return ''
  return knowledgeRepoMap.value[repoId] || ''
}

function handleChatMore() {
  router.push('/Chat')
}

onMounted(() => {
  loadKnowledge().then(() => loadChatSessions())
  loadAllRepoNames()
})

function loadMore() {
  currentPage.value++
  loadKnowledge()
}

function handleCardClick(knowledge) {
  router.push(`/knowledge/${knowledge.id}`)
}

function handleCreate() {
  currentKnowledge.value = null
  formVisible.value = true
}

function handleChatCardClick(session) {
  router.push({
    path: '/Chat',
    query: {
      session_id: session.id,
      knowledge_repository_id: session.dim_knowledge_repository_id
    }
  })
}

function handleFormSuccess(data) {
  if (data.id) {
    router.push(`/knowledge/${data.id}`)
  } else {
    loadKnowledge()
  }
}
</script>

<style scoped>
.home-page {
  padding: 20px;
}

.knowledge-section {
  min-height: 200px;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #909399;
  padding: 40px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
  padding: 10px 0;
}

.action-card {
  cursor: pointer;
  height: 100%;
  min-height: 180px;
  border: 2px dashed #dcdfe6;
  background-color: #fafafa;
}

.action-card:hover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.action-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  gap: 12px;
}

.action-content span {
  font-size: 14px;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.chat-section {
  min-height: 200px;
}

:deep(.el-collapse-item__header) {
  font-size: 16px;
  font-weight: 600;
}
</style>
