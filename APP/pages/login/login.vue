<template>
  <view class="login-container" :loading="loading">
    <uni-forms ref="form" :model="formData as LoginForm">
      
      <uni-easyinput 
	    class="input-username"
        v-model="formData.username as string" 
        placeholder="请输入用户名"
        prefixIcon="person"
        trim
      />
      
      <uni-easyinput
	    class="input-password"
        type="password"
        v-model="formData.password as string"
        placeholder="请输入密码"
        prefixIcon="locked"
        trim
      />

      <!-- 登录按钮 -->
      <button 
        type="primary" 
        class="login-btn" 
        @click="handleLogin"
      >登录</button>

      
    </uni-forms>
  </view>
</template>

<script setup lang="ts">
import { ref,reactive } from "vue";
import { http } from '/pages/req.uts';
var loading = ref(false);
type LoginForm = {
  username: string;
  password: string;
}

var formData = reactive({
	username: '',
	password: ''
} as LoginForm)



function handleLogin() {
	http.post("/token/", {
		"username": formData.username,
		"password": formData.password
	}).then(res => {
		uni.setStorageSync(
			'access_token',
			res.access,
		);
		uni.setStorageSync(
			'refresh_token',
			res.refresh,
		);
		uni.showToast({
			title: '登录成功',
		});
		switchHome();
	}).catch(err => {
		debugger
		if (err.statusCode == 401) {
			uni.showToast({
				title: '用户名或密码不正确',
			});
		}
		else {
			uni.showToast({
				title: '未知错误',
			});
		}
	});
}

function switchHome() {
	uni.switchTab({
		url: '/pages/home/home'
	})
}

</script>

<style lang="scss" scoped>
.login-container {
  padding: 45rpx;
}


.input-username { 
	margin-top: 20%;
}
.input-password {
	margin-top: 10%;
}
.login-btn {
	margin-top: 20%;
}
</style>