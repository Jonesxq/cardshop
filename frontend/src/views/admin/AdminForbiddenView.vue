<template>
  <main class="admin-forbidden">
    <el-result icon="warning" title="无法访问运营后台" sub-title="当前账号没有后台权限，或登录状态已失效。">
      <template #extra>
        <RouterLink to="/login">
          <el-button type="primary">重新登录</el-button>
        </RouterLink>
        <RouterLink to="/">
          <el-button>返回店铺</el-button>
        </RouterLink>
      </template>
    </el-result>
  </main>
</template>
