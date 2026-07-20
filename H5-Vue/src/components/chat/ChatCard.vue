<template>
  <el-card class="chat-card" shadow="hover" @click="handleClick">
    <div class="card-content">
      <el-avatar :size="60" class="card-avatar">
        <el-icon :size="30" style="color: #409eff;"><ChatDotRound /></el-icon>
      </el-avatar>
      <div class="card-info">
        <h3 class="card-title">{{ session.name || '未命名会话' }}</h3>
        <p class="card-desc">{{ repoName || '暂无关联知识库' }}</p>
        <div class="card-meta">
          <span class="card-date">{{ formatDate(session.modifiedon || session.createdon) }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ChatDotRound } from '@element-plus/icons-vue'

const props = defineProps({
  session: {
    type: Object,
    required: true
  },
  repoName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['click'])

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  if (isNaN(date)) return dateStr
  return date.toLocaleDateString('zh-CN')
}

function handleClick() {
  emit('click', props.session)
}
</script>

<style scoped>
.chat-card {
  cursor: pointer;
  transition: all 0.3s;
  height: 100%;
}

.chat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.card-avatar {
  margin-bottom: 12px;
  background-color: #f5f7fa;
}

.card-info {
  width: 100%;
}

.card-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-desc {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  height: 36px;
}

.card-meta {
  font-size: 12px;
  color: #c0c4cc;
}

.card-date {
  margin-right: 8px;
}
</style>
