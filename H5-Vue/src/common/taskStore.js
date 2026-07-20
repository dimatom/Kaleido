import { reactive, computed } from 'vue'
import req from './interface'

const state = reactive({
  tasks: [],
  loaded: false
})

let timer = null

const runningCount = computed(() =>
  state.tasks.filter(t => t.status === 'PENDING' || t.status === 'PROGRESS').length
)

async function fetchTasks() {
  try {
    const res = await req.get('/task/list/')
    state.tasks = res.data.tasks || []
    state.loaded = true
    if (runningCount.value === 0) {
      stopPolling()
    }
  } catch (e) {
    // 静默失败，避免持续弹窗；下一轮自动重试
  }
}

function startPolling() {
  if (timer) return
  fetchTasks()
  timer = setInterval(fetchTasks, 2000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function notifyTaskCreated() {
  startPolling()
}

export default {
  state,
  runningCount,
  fetchTasks,
  startPolling,
  stopPolling,
  notifyTaskCreated
}
