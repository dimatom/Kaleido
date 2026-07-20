<template>
  <view class="profile-container">
    <uni-card>
      <view class="user-info">
        <uni-icons type="person-filled" size="40" color="#007AFF"></uni-icons>
        <view class="user-detail">
          <text class="username">{{user.username}}</text>
          <text class="email">{{user.email}}</text>
        </view>
      </view>
    </uni-card>
	
	
    <uniList>
      <uniListItem 
        title="个人信息" 
        :show-arrow="true"
        @click="navigateTo('/pages/profile/info')"
      >
        <template v-slot:extra>
          <uni-icons type="compose" size="20" color="#666"></uni-icons>
        </template>
      </uniListItem>
      
      <uniListItem 
        title="修改密码" 
        :show-arrow="true"
        @click="navigateTo('/pages/profile/password')"
      >
        <template v-slot:extra>
          <uni-icons type="locked-filled" size="20" color="#666"></uni-icons>
        </template>
      </uniListItem>
      
      <uniListItem 
        title="系统设置" 
        :show-arrow="true"
        @click="navigateTo('/pages/settings')"
      >
        <template v-slot:extra>
          <uni-icons type="gear-filled" size="20" color="#666"></uni-icons>
        </template>
      </uniListItem>
      
      <uniListItem 
        title="关于我们" 
        :show-arrow="true"
        @click="navigateTo('/pages/about')"
      >
        <template v-slot:extra>
          <uni-icons type="info-filled" size="20" color="#666"></uni-icons>
        </template>
      </uniListItem>
    </uniList>
  </view>
</template>

<script setup>
import { ref,onMounted } from 'vue';
import { http } from '/pages/req.uts';
import uniList from '@/uni_modules/uni-list/components/uni-list/uni-list.vue'
import uniListItem from '@/uni_modules/uni-list/components/uni-list-item/uni-list-item.vue'

const navigateTo = (path) => {
  uni.navigateTo({
    url: path
  });
};

var user = ref({
	username: "",
	email: ""
});

onMounted(() => {
  load();
});

function load() {
	http.get("/getuser/").then(res => {
		if (res) {
			user.value.username = res.username;
			user.value.email = res.email;
		}
	}).catch(err => {
		uni.showToast({
			title: err,
		});
	});
}
</script>

<style lang="scss" scoped>
.profile-container {
  padding: 20rpx;
  
  .user-info {
    display: flex;
    align-items: center;
    padding: 20rpx;
    
    .user-detail {
      margin-left: 30rpx;
      display: flex;
      flex-direction: column;
      
      .username {
        font-size: 32rpx;
        font-weight: bold;
      }
      
      .email {
        font-size: 24rpx;
        color: #888;
      }
    }
  }
  
  .uni-list {
    margin-top: 40rpx;
    border-radius: 10rpx;
    overflow: hidden;
  }
  
  .uni-icons {
    margin-right: 15rpx;
  }
}
</style>