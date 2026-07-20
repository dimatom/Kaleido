<template>
  <el-container class="el-container-main">
    <el-header class="dimatom-header">
      <el-menu
      class="dimatom-menu"
        default-active="/home"
        :collapse="isCollapse"
        collapse-transition
        mode="horizontal"
        @open="handleOpen"
        @close="handleClose"
        :router="true">
        <el-menu-item>
          <img :src="kaleidoRagIcon" alt="KaleidoRAG" class="kaleido-rag-icon" />
        </el-menu-item>
        <el-menu-item index="/home">
          <template #title>
            <el-icon><HomeFilled /></el-icon>
            <span>主页</span>
          </template>
        </el-menu-item>
        <!-- <el-menu-item index="/home">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>知识库</span>
          </template>
        </el-menu-item> -->
        <el-menu-item index="/Chat">
          <template #title>
            <el-icon><ChatDotRound /></el-icon>
            <span>聊天</span>
          </template>
        </el-menu-item>
      </el-menu>
      <div class="header-task-btn">
        <TaskButton />
      </div>
    </el-header>
    <el-main class="dimatom-main">
      <router-view :key="$route.fullPath"></router-view>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Document,
  Menu as IconMenu,
  Location,
  Setting,
  ArrowLeft,
  ArrowRight,
  HomeFilled,
  ChatDotRound
} from '@element-plus/icons-vue'
import kaleidoRagIcon from '@/assets/KaleidoRAG.png'
import req from '../common/interface'
import TaskButton from '../components/task/TaskButton.vue'
import taskStore from '../common/taskStore'


const router = useRouter()
// const isCollapse = ref(false);

onMounted(() => {
   if (!req.getAccessToken()) {
     router.replace('/login')
     return
   }
   taskStore.startPolling()
})

function handleOpen(key, keyPath) {
  console.log(key, keyPath);
}

function handleClose(key, keyPath) {
  console.log(key, keyPath);
}
</script>

<style scoped>
.dimatom-header {
  padding: 0px;
  display: flex;
  align-items: center;
}
.kaleido-rag-icon {
  height: 100%;
  width: auto;
  vertical-align: middle;
  /* margin-left: 16px;
  margin-right: 16px; */
}
.dimatom-main {
  padding-left: 0px;
  padding-right: 0px;
}
.dimatom-menu {
  display: flex;
  flex: 1;
  /* background-color: lightslategray;
  color: white; */
}
.header-task-btn {
  margin-left: auto;
  padding-right: 16px;
  display: flex;
  align-items: center;
  height: 100%;
  flex-shrink: 0;
  border-bottom: solid 1px var(--el-menu-border-color);
}

</style>
