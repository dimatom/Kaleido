<template>
  <el-card class="knowledge-card" shadow="hover" @click="handleClick">
    <div class="card-content">
      <el-avatar :src="imageUrl" :size="60" class="card-avatar">
        <el-icon :size="30" style="color: #409eff;"><Document /></el-icon>
      </el-avatar>
      <div class="card-info">
        <h3 class="card-title">{{ knowledge.name }}</h3>
        <p class="card-desc">{{ knowledge.desc || '暂无描述' }}</p>
        <div class="card-meta">
          <span class="card-date">{{ formatDate(knowledge.createdon) }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { Document } from '@element-plus/icons-vue'
import req from '../../common/interface'

const props = defineProps({
  knowledge: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click'])

const imageUrl = computed(() => {
  if (props.knowledge.image) {
    return req.getBaseUrl() + props.knowledge.image
  }
  return ''
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

function handleClick() {
  emit('click', props.knowledge)
}
</script>

<style scoped>
.knowledge-card {
  cursor: pointer;
  transition: all 0.3s;
  height: 100%;
}

.knowledge-card:hover {
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
