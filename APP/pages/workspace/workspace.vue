<template>
	<view>
		<uni-section title="生态林业" type="line" padding>
			<uni-grid :column="3" :highlight="true" @change="change">
				<uni-grid-item v-for="(item, index) in gridList" :index="index" :key="index">
					<view class="grid-item-box" style="background-color: #fff;">
						<uni-icons type="star" :size="30" color="#777"  />
						<text class="text">{{item.name}}</text>
					</view>
				</uni-grid-item>
			</uni-grid>
		</uni-section>
		
	</view>
</template>

<script setup>
	import { ref } from "vue";
	import { http } from '/pages/req.uts';
	var gridList = ref([
		{
			name: "基本信息",
			url: '/pages/index/index'
		},
		{
			name: "调查",
			url: '/pages/home/home'
		},
		{
			name: "登录",
			url: '/pages/index/index'
		},
		{
			name: "标准地调查",
			url: '/pages/index/index'
		},
		{
			name: "立木调查",
			url: '/pages/index/index'
		},
		
	]);
	
	function change(e) {
		
		let {
			index
		} = e.detail
		
		const menu = gridList.value[index];

		uni.navigateTo({
			url: menu.url
		});
	}
</script>

<style lang="scss">
.image {
		width: 25px;
		height: 25px;
	}

	.text {
		font-size: 14px;
		margin-top: 5px;
	}

	.example-body {
		/* #ifndef APP-NVUE */
		// display: block;
		/* #endif */
	}

	.grid-dynamic-box {
		margin-bottom: 15px;
	}

	.grid-item-box {
		flex: 1;
		// position: relative;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 10px 0;
	}

	.grid-item-box-row {
		flex: 1;
		// position: relative;
		/* #ifndef APP-NVUE */
		display: flex;
		/* #endif */
		flex-direction: row;
		align-items: center;
		justify-content: center;
		padding: 10px 0;
	}

	.grid-dot {
		position: absolute;
		top: 5px;
		right: 15px;
	}

	.swiper {
		height: 420px;
	}

	/* #ifdef H5 */
	@media screen and (min-width: 768px) and (max-width: 1425px) {
		.swiper {
			height: 630px;
		}
	}

	@media screen and (min-width: 1425px) {
		.swiper {
			height: 830px;
		}
	}

	/* #endif */
</style>