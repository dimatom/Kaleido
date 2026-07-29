<template>
  <div class="evaluation-page" v-loading="loading">
    <div class="page-header">
      <div>
        <el-button :icon="ArrowLeft" text @click="router.back()">返回</el-button>
        <h2>{{ evaluation?.name || 'RAG评估' }}</h2>
      </div>
      <el-button type="primary" :loading="runLoading" :disabled="!selectedTask" @click="startRun">启动评估</el-button>
    </div>

    <el-alert v-if="forbidden" title="仅超级管理员可使用评估功能" type="error" show-icon />
    <template v-else>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="评估数据" name="data">
          <div class="toolbar">
            <el-button type="primary" @click="openDataDialog()">新增数据</el-button>
            <span>共 {{ dataTotal }} 条数据，启动前必须填写标准答案</span>
          </div>
          <el-table :data="dataItems" border>
            <el-table-column prop="question" label="问题" min-width="260" show-overflow-tooltip />
            <el-table-column prop="ai_answer" label="原AI回答" min-width="260" show-overflow-tooltip />
            <el-table-column label="标准答案" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ row.reference_answer || '未填写' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDataDialog(row)">编辑</el-button>
                <el-button link type="danger" @click="deleteData(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination :current-page="dataPage" :page-size="10" :total="dataTotal" layout="total, prev, pager, next" @current-change="changeDataPage" />
        </el-tab-pane>

        <el-tab-pane label="配置任务" name="tasks">
          <div class="toolbar"><el-button type="primary" @click="openTaskDialog()">新增配置</el-button></div>
          <el-table :data="tasks" border highlight-current-row @current-change="selectTask">
            <el-table-column prop="name" label="任务名称" width="180" />
            <el-table-column prop="task_mark" label="标记" width="110" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="配置" min-width="360">
              <template #default="{ row }"><pre>{{ JSON.stringify(row.rag_config, null, 2) }}</pre></template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="selectedTask = row; openTaskDialog(row)">编辑</el-button>
                <el-button link type="success" @click="applyConfig(row)">应用配置</el-button>
                <el-button link type="danger" @click="deleteTask(row)" :disabled="row.task_mark === 'baseline'">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="执行历史" name="runs">
          <el-table :data="runs" border>
            <el-table-column prop="createdon" label="创建时间" width="190" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="汇总指标" min-width="320">
              <template #default="{ row }"><span v-if="row.result">{{ formatResult(row.result) }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }"><el-button link type="primary" :disabled="!row.file" @click="download(row)">下载报告</el-button></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-dialog v-model="dataDialogVisible" :title="editingData ? '编辑评估数据' : '新增评估数据'" width="620px">
      <el-form label-width="90px">
        <el-form-item label="问题"><el-input v-model="dataForm.question" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="AI回答"><el-input v-model="dataForm.ai_answer" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="标准答案"><el-input v-model="dataForm.reference_answer" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dataDialogVisible = false">取消</el-button><el-button type="primary" @click="saveData">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="taskDialogVisible" :title="editingTask ? '编辑配置任务' : '新增配置任务'" width="650px">
      <el-form label-width="110px">
        <el-form-item label="任务名称"><el-input v-model="taskForm.name" /></el-form-item>
        <el-form-item label="任务标记"><el-select v-model="taskForm.task_mark"><el-option label="候选" value="candidate" /><el-option label="基线" value="baseline" /></el-select></el-form-item>
        <el-form-item label="分块大小"><el-input-number v-model="taskForm.rag_config.indexing.chunk_size" :min="1" /></el-form-item>
        <el-form-item label="分块重叠"><el-input-number v-model="taskForm.rag_config.indexing.chunk_overlap" :min="0" /></el-form-item>
        <el-form-item label="向量权重"><el-input-number v-model="taskForm.rag_config.retrieval.vector_weight" :min="0" :step="0.1" /></el-form-item>
        <el-form-item label="BM25权重"><el-input-number v-model="taskForm.rag_config.retrieval.bm25_weight" :min="0" :step="0.1" /></el-form-item>
        <el-form-item label="融合候选数"><el-input-number v-model="taskForm.rag_config.retrieval.ensemble_top_k" :min="1" /></el-form-item>
        <el-form-item label="重排数量"><el-input-number v-model="taskForm.rag_config.retrieval.rerank_top_k" :min="1" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="taskDialogVisible = false">取消</el-button><el-button type="primary" @click="saveTask">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import req from '../common/interface'
import taskStore from '../common/taskStore'

const route = useRoute()
const router = useRouter()
const evaluationId = route.params.id
const loading = ref(false)
const forbidden = ref(false)
const activeTab = ref('data')
const evaluation = ref(null)
const dataItems = ref([])
const dataPage = ref(1)
const dataTotal = ref(0)
const tasks = ref([])
const selectedTask = ref(null)
const runs = ref([])
const runLoading = ref(false)
const dataDialogVisible = ref(false)
const taskDialogVisible = ref(false)
const editingData = ref(null)
const editingTask = ref(null)
const dataForm = reactive({ question: '', ai_answer: '', reference_answer: '' })
const taskForm = reactive({ name: '', task_mark: 'candidate', rag_config: defaultConfig() })

function defaultConfig() {
  return { indexing: { chunk_size: 500, chunk_overlap: 100 }, retrieval: { vector_weight: 0.8, bm25_weight: 0.2, ensemble_top_k: 6, rerank_top_k: 3 } }
}
function errorMessage(error, fallback) { return error?.response?.data?.error || fallback }
async function loadAll() { loading.value = true; try { await Promise.all([loadEvaluation(), loadData(), loadTasks()]) } catch (error) { forbidden.value = error?.response?.status === 403; if (!forbidden.value) ElMessage.error(errorMessage(error, '加载评估失败')) } finally { loading.value = false } }
async function loadEvaluation() { evaluation.value = (await req.get(`/evaluation/${evaluationId}/`)).data }
async function changeDataPage(page) { dataPage.value = page; await loadData() }
async function loadData() { const result = await req.get(`/evaluation/${evaluationId}/data/?page=${dataPage.value}&page_size=10`); dataItems.value = result.data.results || []; dataTotal.value = result.data.count || 0 }
async function loadTasks() { tasks.value = (await req.get(`/evaluation/${evaluationId}/tasks/`)).data || []; selectedTask.value ||= tasks.value[0] }
async function loadRuns() { if (!selectedTask.value) return; runs.value = (await req.get(`/evaluation/task/${selectedTask.value.id}/runs/`)).data || [] }
function openDataDialog(row) { editingData.value = row || null; Object.assign(dataForm, row || { question: '', ai_answer: '', reference_answer: '' }); dataDialogVisible.value = true }
async function saveData() { try { if (!dataForm.question.trim()) return ElMessage.warning('问题不能为空'); if (editingData.value) await req.post(`/evaluation/data/${editingData.value.id}/`, dataForm); else await req.post(`/evaluation/${evaluationId}/data/`, dataForm); dataDialogVisible.value = false; await loadData(); ElMessage.success('保存成功') } catch (error) { ElMessage.error(errorMessage(error, '保存失败')) } }
async function deleteData(row) { await ElMessageBox.confirm('确定删除这条评估数据吗？', '删除确认').catch(() => { throw new Error('cancelled') }); try { await req.del(`/evaluation/data/${row.id}/`); await loadData() } catch (error) { if (error.message !== 'cancelled') ElMessage.error(errorMessage(error, '删除失败')) } }
async function selectTask(row) { if (row) { selectedTask.value = row; await loadRuns() } }
function openTaskDialog(row) { editingTask.value = row || null; taskForm.name = row?.name || ''; taskForm.task_mark = row?.task_mark || 'candidate'; taskForm.rag_config = JSON.parse(JSON.stringify(row?.rag_config || defaultConfig())); taskDialogVisible.value = true }
async function saveTask() { if (taskForm.rag_config.indexing.chunk_overlap >= taskForm.rag_config.indexing.chunk_size) return ElMessage.warning('分块重叠必须小于分块大小'); if (taskForm.rag_config.retrieval.rerank_top_k > taskForm.rag_config.retrieval.ensemble_top_k) return ElMessage.warning('重排数量不能大于融合候选数'); try { const payload = { name: taskForm.name, task_mark: taskForm.task_mark, rag_config: taskForm.rag_config }; if (editingTask.value) await req.post(`/evaluation/task/${editingTask.value.id}/`, payload); else await req.post(`/evaluation/${evaluationId}/tasks/`, payload); taskDialogVisible.value = false; await loadTasks(); ElMessage.success('配置已保存') } catch (error) { ElMessage.error(errorMessage(error, '保存配置失败')) } }
async function deleteTask(row) { try { await ElMessageBox.confirm('确定删除该配置任务吗？', '删除确认'); await req.del(`/evaluation/task/${row.id}/`); await loadTasks() } catch (error) { if (error?.response) ElMessage.error(errorMessage(error, '删除失败')) } }
async function startRun() { if (!selectedTask.value) return ElMessage.warning('请先选择配置任务'); try { await ElMessageBox.confirm('确定启动本次评估吗？', '执行确认'); runLoading.value = true; await req.post(`/evaluation/task/${selectedTask.value.id}/runs/`); taskStore.notifyTaskCreated(); await loadRuns(); ElMessage.success('评估任务已创建') } catch (error) { if (error?.response) ElMessage.error(errorMessage(error, '启动失败')) } finally { runLoading.value = false } }
async function applyConfig(row) { try { await ElMessageBox.confirm('应用配置可能触发全文档重建，确定继续吗？', '应用确认'); const result = await req.post(`/evaluation/task/${row.id}/apply-config/`); if (result.data.rebuild_task_id) taskStore.notifyTaskCreated(); ElMessage.success('配置已应用') } catch (error) { if (error?.response) ElMessage.error(errorMessage(error, '应用失败')) } }
async function download(row) { try { await req.downloadWithAuth(`/evaluation/run/${row.id}/download/`, `evaluation_${row.id}.xlsx`) } catch (error) { ElMessage.error('报告下载失败') } }
function formatResult(result) { return Object.entries(result || {}).map(([key, value]) => `${key}: ${Number(value).toFixed(4)}`).join('，') }
onMounted(async () => { await loadAll(); if (tasks.value.length) { await loadRuns() } })
</script>

<style scoped>
.evaluation-page { padding: 20px; }
.page-header, .toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-header h2 { display: inline-block; margin: 0 0 0 10px; vertical-align: middle; }
.el-pagination { justify-content: flex-end; margin-top: 16px; }
pre { max-height: 120px; overflow: auto; margin: 0; white-space: pre-wrap; }
</style>
