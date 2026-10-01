<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const loading = ref(true)
onMounted(async () => {
  try {
    // 与主图同源：按当前柱心即时重算，绝不读旧 run 造成放不下仍按旧柱心
    const data = await api('/allocate/run?segment_id=1', { method: 'POST' })
    rows.value = data.rejected || []
  } finally {
    loading.value = false
  }
})
</script>
<template>
  <h1>放不下</h1>
  <p class="sub">无法在连续空档内安置且不跨越挡柱的摊位 · 与分配带同一套柱心重切</p>
  <div class="card">
    <table>
      <thead><tr><th>摊主</th><th>需求宽度</th><th>原因</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.vendor_id">
          <td>{{ r.vendor_name }}</td><td>{{ r.width_m }}</td><td>{{ r.reason }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="loading" class="muted">重算中…</p>
    <p v-else-if="!rows.length" class="muted">全部放下</p>
  </div>
</template>
