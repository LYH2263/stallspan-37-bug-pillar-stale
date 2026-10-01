<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/segments') })
</script>
<template>
  <h1>街段</h1>
  <p class="sub">沿街可用宽度（米）</p>
  <div class="card">
    <table>
      <thead><tr><th>街段</th><th>宽度(m)</th><th>集日ID</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)"><td>{{ r.name }}</td><td>{{ r.width_m }}</td><td>{{ r.market_day_id }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
