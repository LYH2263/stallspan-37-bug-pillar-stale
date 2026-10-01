<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/days') })
</script>
<template>
  <h1>集日</h1>
  <p class="sub">开市日程</p>
  <div class="card">
    <table>
      <thead><tr><th>名称</th><th>日期</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)"><td>{{ r.name }}</td><td>{{ r.day }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
