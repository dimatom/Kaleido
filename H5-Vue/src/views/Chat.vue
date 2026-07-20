<template>
    <div class="chat-wrapper">
        <div :class="['chat-sidebar', { collapsed: sidebarCollapsed }]">
            <div class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
                <span class="toggle-icon">{{ sidebarCollapsed ? '▶' : '◀' }}</span>
            </div>
            <div v-show="!sidebarCollapsed" class="sidebar-content">
                <div class="sidebar-tabs">
                    <div
                        :class="['tab-item', { active: historyType === 'all' }]"
                        @click="switchHistoryType('all')"
                    >
                        所有会话
                    </div>
                    <div
                        :class="['tab-item', { active: historyType === 'current_repo' }]"
                        @click="switchHistoryType('current_repo')"
                    >
                        当前知识库会话
                    </div>
                </div>
                <div class="history-list" v-loading="historyLoading">
                    <div
                        v-for="item in historyList"
                        :key="item.id"
                        :class="['history-item', { active: item.id === sessionId }]"
                        @click="loadSession(item.id)"
                    >
                        <div class="history-info">
                            <div class="history-name">{{ item.name || '未命名会话' }}</div>
                            <div class="history-time">{{ formatTime(item.createdon) }}</div>
                        </div>
                        <el-button
                            class="history-delete"
                            type="danger"
                            :icon="Delete"
                            link
                            size="medium"
                            @click.stop="deleteSession(item.id)"
                        >
                        </el-button>
                    </div>
                    <el-empty v-if="!historyLoading && historyList.length === 0" description="暂无记录" :image-size="60" />
                </div>
            </div>
        </div>
        <el-container class="chat-container" v-loading="initLoading">
            <el-header class="chat-header">
                <span class="chat-title">AI 智能对话</span>
                <div class="header-actions">
                    <el-select
                        v-model="knowledgeRepositoryId"
                        placeholder="选择知识库"
                        size="small"
                        style="width: 180px"
                        @change="onRepoChange"
                    >
                        <el-option
                            v-for="repo in knowledgeRepositories"
                            :key="repo.id"
                            :label="repo.name"
                            :value="repo.id"
                        />
                    </el-select>
                    <el-button type="primary" size="small" @click="startNewSession">+ 新会话</el-button>
                    <span v-if="sessionId" class="session-tag">会话: {{ sessionId }}</span>
                </div>
            </el-header>
            <el-main class="chat-main" ref="chatMainRef">
                <div class="msg-list">
                    <div v-for="(msg, idx) in messages" :key="idx" :class="['msg-row', msg.type]">
                        <div class="msg-bubble">
                            <div class="msg-role">{{ msg.type === 'human' ? '用户' : 'AI' }}</div>
                            <MarkdownRenderer
                                :content="msg.data.content"
                                :plain="msg.type === 'human'"
                            />
                        </div>
                    </div>
                    <div v-if="streaming" class="msg-row ai">
                        <div class="msg-bubble">
                            <div class="msg-role">AI</div>
                            <MarkdownRenderer :content="streamingContent" streaming />
                            <span class="cursor-blink">|</span>
                        </div>
                    </div>
                </div>
            </el-main>
            <el-footer class="chat-footer">
                <div class="input-area">
                    <div class="input-composer">
                        <el-input
                            v-model="inputText"
                            type="textarea"
                            :rows="1"
                            :autosize="{ minRows: 1, maxRows: 6 }"
                            placeholder="请输入问题，按 Enter 发送，Shift + Enter 换行..."
                            :disabled="streaming"
                            @keydown.enter.prevent="handleEnter"
                            resize="none"
                        />
                        <div class="composer-actions">
                            <el-button
                                type="primary"
                                :disabled="!inputText.trim() || streaming"
                                @click="send"
                            >
                                {{ streaming ? '生成中...' : '发送' }}
                            </el-button>
                        </div>
                    </div>
                </div>
            </el-footer>
        </el-container>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import req from '../common/interface'
import { ElMessage } from 'element-plus'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { Delete } from "@element-plus/icons-vue";

const route = useRoute()
const router = useRouter()
const inputText = ref('')
const messages = ref([])
const streaming = ref(false)
const streamingContent = ref('')
const initLoading = ref(false)
const chatMainRef = ref(null)
const sessionId = ref('')
const knowledgeRepositoryId = ref('')
const knowledgeRepositories = ref([])

// 侧边栏状态
const sidebarCollapsed = ref(false)
const historyType = ref('all') // 'all' | 'current_repo'
const historyList = ref([])
const historyLoading = ref(false)

/** 格式化时间 */
function formatTime(timeStr) {
    if (!timeStr) return ''
    const d = new Date(timeStr)
    if (isNaN(d)) return timeStr
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 加载知识库列表 */
async function loadKnowledgeRepositories() {
    try {
        const res = await req.get('/chat/repositories/')
        if (Array.isArray(res.data)) {
            knowledgeRepositories.value = res.data
            if (!knowledgeRepositoryId.value && res.data.length > 0) {
                knowledgeRepositoryId.value = res.data[0].id
            }
        }
    } catch (err) {
        ElMessage.error(`加载知识库列表失败: ${err.message}`)
    }
}

/** 加载历史记录列表 */
async function loadHistoryList() {
    historyLoading.value = true
    try {
        const params = new URLSearchParams()
        params.append('pageIndex', '1')
        params.append('pageSize', '100')
        if (historyType.value === 'current_repo' && knowledgeRepositoryId.value) {
            params.append('knowledge_repository_id', knowledgeRepositoryId.value)
        }
        const res = await req.get(`/chat/sessions/?${params.toString()}`)
        if (Array.isArray(res.data)) {
            historyList.value = res.data
        } else {
            historyList.value = []
        }
    } catch (err) {
        ElMessage.error(`加载历史列表失败: ${err.message}`)
    } finally {
        historyLoading.value = false
    }
}

/** 切换历史类型 */
function switchHistoryType(type) {
    if (historyType.value === type) return
    if (type === 'current_repo' && !knowledgeRepositoryId.value) {
        ElMessage.warning('当前没有选择知识库，无法查看当前知识库会话')
        return
    }
    historyType.value = type
    loadHistoryList()
}

/** 加载指定会话 */
async function loadSession(id) {
    if (!id || id === sessionId.value) return
    const item = historyList.value.find(h => h.id === id)
    if (item && item.dim_knowledge_repository_id) {
        knowledgeRepositoryId.value = item.dim_knowledge_repository_id
    }
    sessionId.value = id
    messages.value = []
    streamingContent.value = ''
    streaming.value = false
    router.replace({
        path: '/Chat',
        query: {
            session_id: id,
            knowledge_repository_id: knowledgeRepositoryId.value
        }
    })
    await loadHistory()
}

/** 开始新会话 */
function startNewSession() {
    sessionId.value = ''
    messages.value = []
    streamingContent.value = ''
    streaming.value = false
    inputText.value = ''
    router.replace({
        path: '/Chat',
        query: {
            knowledge_repository_id: knowledgeRepositoryId.value
        }
    })
}

/** 删除会话 */
async function deleteSession(id) {
    if (!id) return
    try {
        await req.post('/chat/sessions/delete/', [id])
        ElMessage.success('删除成功')
        // 如果删除的是当前会话，清空当前会话
        if (id === sessionId.value) {
            startNewSession()
        }
        loadHistoryList()
    } catch (err) {
        ElMessage.error(`删除失败: ${err.message}`)
    }
}

/** 滚动到底部 */
function scrollToBottom() {
    nextTick(() => {
        const el = chatMainRef.value?.$el
        if (el) {
            el.scrollTop = el.scrollHeight
        }
    })
}

/** 加载历史会话 */
async function loadHistory() {
    if (!sessionId.value) return
    initLoading.value = true
    try {
        const res = await req.get(`/chat/history/?session_id=${sessionId.value}`)
        if (Array.isArray(res.data)) {
            messages.value = res.data.filter(
                item => item && item.type && item.data && typeof item.data.content === 'string'
            )
        }
    } catch (err) {
        ElMessage.error(`加载历史失败: ${err.message}`)
    } finally {
        initLoading.value = false
    }
}

/** 处理文本域回车：Enter 发送，Shift+Enter 换行 */
function handleEnter(e) {
    if (!e.shiftKey) {
        e.preventDefault()
        send()
    }
}

/** 发送消息 */
async function send() {
    const query = inputText.value.trim()
    if (!query || streaming.value) return

    if (!knowledgeRepositoryId.value) {
        ElMessage.warning('请先选择一个知识库')
        return
    }

    // 追加用户消息到本地展示
    messages.value.push({
        type: 'human',
        data: { content: query }
    })
    inputText.value = ''
    streaming.value = true
    streamingContent.value = ''
    scrollToBottom()

    try {
        const body = {
            user_query: query,
            knowledge_repository_id: knowledgeRepositoryId.value
        }
        if (sessionId.value) {
            body.session_id = sessionId.value
        }

        const { response, reader, decoder } = await req.postStream('/chat/stream/', body)

        // 如果之前没有 session_id，从响应头获取新的
        if (!sessionId.value) {
            const newSessionId = response.headers.get('X-Session-Id')
            if (newSessionId) {
                sessionId.value = newSessionId
                // 同步到 URL，刷新后可保持对话
                router.replace({
                    path: '/Chat',
                    query: {
                        session_id: newSessionId,
                        knowledge_repository_id: knowledgeRepositoryId.value
                    }
                })
                loadHistoryList()
            }
        }

        let done = false
        while (!done) {
            const { value, done: readerDone } = await reader.read()
            done = readerDone
            if (value) {
                const chunk = decoder.decode(value, { stream: true })
                streamingContent.value += chunk
                scrollToBottom()
            }
        }

        // 流结束，将 AI 回复归档到本地展示
        if (streamingContent.value) {
            messages.value.push({
                type: 'ai',
                data: { content: streamingContent.value }
            })
        }
    } catch (err) {
        ElMessage.error(`请求失败: ${err.message}`)
        messages.value.push({
            type: 'ai',
            data: { content: `请求出错: ${err.message}` }
        })
    } finally {
        streaming.value = false
        streamingContent.value = ''
        scrollToBottom()
    }
}

/** 切换知识库 */
function onRepoChange() {
    sessionId.value = ''
    messages.value = []
    streamingContent.value = ''
    streaming.value = false
    router.replace({
        path: '/Chat',
        query: {
            knowledge_repository_id: knowledgeRepositoryId.value
        }
    })
    loadHistoryList()
}

onMounted(() => {
    const sid = route.query.session_id
    const krId = route.query.knowledge_repository_id
    if (krId) {
        knowledgeRepositoryId.value = krId
    }
    if (sid) {
        sessionId.value = sid
        loadHistory()
    }
    loadKnowledgeRepositories().then(() => {
        loadHistoryList()
    })
    const raw = sessionStorage.getItem('chat_pre_query')
    if (raw) {
        try {
            const preQuery = raw
            sessionStorage.removeItem('chat_pre_query')
            inputText.value = preQuery
            send()
            console.log('收到预查询上下文:', preQuery)
        } catch (e) {
            console.warn('预查询上下文解析失败:', e)
        }
    }
})

watch(messages, scrollToBottom, { deep: true })

</script>

<style scoped>
.chat-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: #f5f7fa;
}

.chat-header {
    background: #ffffff;
    border-bottom: 1px solid #e4e7ed;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
    position: relative;
}

.chat-title {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
}

.header-actions {
    position: absolute;
    right: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.session-tag {
    font-size: 12px;
    color: #909399;
    background: #f4f4f5;
    padding: 2px 8px;
    border-radius: 4px;
}

.chat-main {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.msg-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 900px;
    margin: 0 auto;
}

.msg-row {
    display: flex;
    width: 100%;
}

.msg-row.human {
    justify-content: flex-end;
}

.msg-row.ai {
    justify-content: flex-start;
}

.msg-bubble {
    max-width: 70%;
    padding: 12px 16px;
    border-radius: 10px;
    line-height: 1.6;
    word-break: break-word;
    white-space: pre-wrap;
}

.msg-row.human .msg-bubble {
    background: #409eff;
    color: #ffffff;
    white-space: pre-wrap;
}

.msg-row.ai .msg-bubble {
    background: #ffffff;
    color: #303133;
    border: 1px solid #e4e7ed;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    white-space: normal;
}

.msg-role {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
    opacity: 0.85;
}

.msg-content {
    font-size: 14px;
}

.cursor-blink {
    font-size: 14px;
    color: #409eff;
    animation: blink 1s step-start infinite;
}

@keyframes blink {
    50% {
        opacity: 0;
    }
}

.chat-footer {
    /* background: #ffffff; */
    /* border-top: 1px solid #e4e7ed; */
    padding: 12px 20px;
    /* box-shadow: 0 -1px 4px rgba(0, 0, 0, 0.05); */
    height: 20%;
}

.input-area {
    display: flex;
    gap: 12px;
    max-width: 900px;
    margin: 0 auto;
    align-items: flex-end;
}

.input-composer {
    flex: 1;
    display: flex;
    flex-direction: column;
    border: 1px solid #dcdfe6;
    border-radius: 16px;
    background: #ffffff;
    padding: 10px 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    transition: border-color 0.2s, box-shadow 0.2s;
}

.input-composer:focus-within {
    border-color: #409eff;
    box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}

.input-composer :deep(.el-textarea__inner) {
    border: none;
    background: transparent;
    padding: 0;
    resize: none;
    box-shadow: none;
    font-size: 14px;
    line-height: 1.6;
    min-height: 22px !important;
}

.composer-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 8px;
}

.composer-actions .el-button {
    border-radius: 10px;
    padding: 6px 16px;
    height: 32px;
}

.input-area .el-input {
    flex: 1;
}

.chat-wrapper {
    display: flex;
    height: 100vh;
    overflow: hidden;
}

.chat-sidebar {
    width: 260px;
    background: #ffffff;
    border-right: 1px solid #e4e7ed;
    display: flex;
    flex-shrink: 0;
    transition: width 0.28s;
    position: relative;
}

.chat-sidebar.collapsed {
    width: 36px;
}

.sidebar-toggle {
    width: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    border-right: 1px solid #e4e7ed;
    background: #f5f7fa;
    color: #606266;
    font-size: 12px;
    user-select: none;
}

.sidebar-toggle:hover {
    background: #e4e7ed;
}

.sidebar-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.sidebar-tabs {
    display: flex;
    border-bottom: 1px solid #e4e7ed;
}

.tab-item {
    flex: 1;
    text-align: center;
    padding: 10px 0;
    font-size: 13px;
    color: #606266;
    cursor: pointer;
    user-select: none;
    transition: color 0.2s, background 0.2s;
}

.tab-item:hover {
    color: #409eff;
    background: #f5f7fa;
}

.tab-item.active {
    color: #409eff;
    font-weight: 600;
    border-bottom: 2px solid #409eff;
    margin-bottom: -1px;
}

.history-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.history-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: background 0.2s;
    border: 1px solid transparent;
}

.history-item:hover {
    background: #f5f7fa;
}

.history-item.active {
    background: #ecf5ff;
    border-color: #b3d8ff;
}

.history-info {
    flex: 1;
    min-width: 0;
    overflow: hidden;
}

.history-name {
    font-size: 13px;
    color: #303133;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.4;
}

.history-time {
    font-size: 11px;
    color: #909399;
    margin-top: 4px;
}

.history-delete {
    opacity: 0;
    transition: opacity 0.2s;
    margin-left: 8px;
    flex-shrink: 0;
}

.history-item:hover .history-delete {
    opacity: 1;
}
</style>
