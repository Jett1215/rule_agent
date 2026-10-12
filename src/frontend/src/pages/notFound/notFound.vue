<script setup lang="ts"></script>

<template>
  <div class="notFound">
    <div class="error-code">404</div>
    <div class="text">未找到该页面</div>
    <router-link to="/workspace" class="back-link">返回工作台</router-link>
  </div>
</template>

<style>
.notFound{
  height: calc(100vh);
  display: flex;
  justify-content: center;
  align-items: center;
  .text{
    display: flex;
    font-size: 25px;
    justify-content: center;
    color:rgb(157, 157, 157);
  }
}
</style>
