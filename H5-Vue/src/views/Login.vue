<template>
    <div class="login-wrapper">
        <el-card class="login-card">
            <template #header>
                <div class="login-header">
                    <span class="login-title">Kaleido RAG</span>
                </div>
            </template>
            <el-form
                ref="loginFormRef"
                :model="form"
                :rules="rules"
                label-position="top"
                @keyup.enter="handleLogin"
            >
                <el-form-item label="用户名" prop="username">
                    <el-input
                        v-model="form.username"
                        placeholder="请输入用户名"
                        :prefix-icon="User"
                        clearable
                        autofocus
                    />
                </el-form-item>
                <el-form-item label="密码" prop="password">
                    <el-input
                        v-model="form.password"
                        type="password"
                        placeholder="请输入密码"
                        :prefix-icon="Lock"
                        show-password
                        clearable
                    />
                </el-form-item>
                <el-form-item>
                    <el-button
                        type="primary"
                        class="login-button"
                        :loading="loading"
                        @click="handleLogin"
                    >
                        登录
                    </el-button>
                </el-form-item>
            </el-form>
        </el-card>
    </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import req from '../common/interface'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const form = reactive({
    username: '',
    password: ''
})

const rules = {
    username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
    ],
    password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 1, message: '密码不能为空', trigger: 'blur' }
    ]
}

async function handleLogin() {
    if (!loginFormRef.value) return
    try {
        await loginFormRef.value.validate()
    } catch (err) {
        return
    }
    loading.value = true
    try {
        await req.login(form.username, form.password)
        ElMessage.success('登录成功')
        router.replace('/')
    } catch (err) {
        var msg = '登录失败'
        if (err && err.response && err.response.data) {
            var detail = err.response.data.detail || err.response.data.message
            if (detail) {
                msg = '登录失败: ' + detail
            }
        } else if (err && err.message) {
            msg = '登录失败: ' + err.message
        }
        ElMessage.error(msg)
    } finally {
        loading.value = false
    }
}
</script>

<style scoped>
.login-wrapper {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
}

.login-card {
    width: 380px;
    border-radius: 12px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
}

.login-header {
    text-align: center;
    padding: 8px 0;
}

.login-title {
    font-size: 24px;
    font-weight: 600;
    color: #303133;
    letter-spacing: 1px;
}

.login-button {
    width: 100%;
}
</style>