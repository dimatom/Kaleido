<template>
  <el-popover
    placement="bottom-end"
    :width="360"
    trigger="click"
    @show="fetchTasks"
  >
    <template #reference>
      <span class="task-btn-wrapper">
        <el-badge
          :value="runningCount"
          :hidden="runningCount === 0"
          :max="99"
        >
          <el-button text>
            <el-icon :size="18"><Tickets /></el-icon>
            <!-- <span style="margin-left: 4px">任务</span> -->
          </el-button>
        </el-badge>
      </span>
    </template>

    <div class="task-panel">
      <el-empty
        v-if="!state.tasks.length"
        description="暂无任务"
        :image-size="60"
      />
      <el-scrollbar v-else max-height="400px">
        <div
          v-for="t in state.tasks"
          :key="t.task_id"
          class="task-card"
        >
          <div class="task-card__head">
            <span class="task-card__name" :title="t.km_name">{{ t.km_name }}</span>
            <span class="task-card__count">{{ t.doc_count }} 个文件</span>
          </div>
          <el-progress
            :percentage="t.progress"
            :status="progressStatus(t)"
            :stroke-width="10"
          />
          <div
            class="task-card__context"
            :class="{ 'is-error': t.status === 'FAILURE' }"
          >
            {{ t.status === 'FAILURE' ? (t.error || t.context) : t.context }}
          </div>
        </div>
      </el-scrollbar>
    </div>
  </el-popover>
</template>

<script setup>
import { Tickets } from '@element-plus/icons-vue'
import taskStore from '../../common/taskStore'

const { state, runningCount, fetchTasks } = taskStore

function progressStatus(t) {
  if (t.status === 'FAILURE') return 'exception'
  if (t.status === 'SUCCESS') return 'success'
  return ''
}
</script>

<style scoped>
.task-btn-wrapper {
  display: inline-flex;
  align-items: center;
  height: 100%;
  cursor: pointer;
}

.task-panel {
  padding: 8px 4px;
}

.task-card {
  padding: 12px;
  margin-bottom: 10px;
  border-radius: 8px;
  background-color: #f5f7fa;
}

.task-card:last-child {
  margin-bottom: 0;
}

.task-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.task-card__name {
  font-weight: 500;
  color: #303133;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card__count {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}

.task-card__context {
  margin-top: 6px;
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}

.task-card__context.is-error {
  color: #f56c6c;
}
</style>
