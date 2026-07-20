<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑知识库' : '新建知识库'"
    width="500px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="头像">
        <el-upload
          class="avatar-uploader"
          action="#"
          :show-file-list="false"
          :before-upload="beforeAvatarUpload"
          :http-request="handleAvatarUpload"
        >
          <img v-if="imageUrl" :src="imageUrl" class="avatar" />
          <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
        </el-upload>
      </el-form-item>

      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入知识库名称" maxlength="255" />
      </el-form-item>

      <el-form-item label="描述" prop="desc">
        <el-input
          v-model="form.desc"
          type="textarea"
          :rows="3"
          placeholder="请输入知识库描述"
          maxlength="1000"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="系统提示词" prop="system_prompt">
        <el-input
          v-model="form.system_prompt"
          type="textarea"
          :rows="4"
          placeholder="请输入系统提示词，用于AI理解知识库内容"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import req from '../../common/interface'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  knowledge: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'success'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const isEdit = computed(() => !!props.knowledge)

const formRef = ref(null)
const loading = ref(false)
const form = ref({
  id: null,
  name: '',
  desc: '',
  system_prompt: '',
  image: null
})

const rules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' }
  ]
}

const imageUrl = ref('')

watch(() => props.knowledge, (val) => {
  if (val) {
    form.value = {
      id: val.id,
      name: val.name,
      desc: val.desc || '',
      system_prompt: val.system_prompt || '',
      image: val.image || null
    }
    if (val.image) {
      imageUrl.value = req.getBaseUrl() + val.image
    } else {
      imageUrl.value = ''
    }
  } else {
    form.value = {
      id: null,
      name: '',
      desc: '',
      system_prompt: '',
      image: null
    }
    imageUrl.value = ''
  }
}, { immediate: true })

function beforeAvatarUpload(file) {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!')
    return false
  }
  return true
}

function handleAvatarUpload(options) {
  form.value.image = options.file
  const reader = new FileReader()
  reader.onload = (e) => {
    imageUrl.value = e.target.result
  }
  reader.readAsDataURL(options.file)
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('name', form.value.name)
    formData.append('desc', form.value.desc)
    formData.append('system_prompt', form.value.system_prompt)
    if (form.value.id) {
      formData.append('id', form.value.id)
    }
    if (form.value.image && form.value.image instanceof File) {
      formData.append('image', form.value.image)
    }

    const res = await req.post('/knowledge/save/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
    emit('success', res.data)
    handleClose()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  } finally {
    loading.value = false
  }
}

function handleClose() {
  formRef.value?.resetFields()
  dialogVisible.value = false
}
</script>

<style scoped>
.avatar-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s;
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-uploader:hover {
  border-color: #409eff;
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar {
  width: 100px;
  height: 100px;
  object-fit: cover;
}
</style>
