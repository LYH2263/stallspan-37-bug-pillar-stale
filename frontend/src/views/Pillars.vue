<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

interface Pillar {
  id: number
  segment_id: number
  position_m: number
  thickness_m: number
  label: string
}

const rows = ref<Pillar[]>([])
const drafts = ref<Record<number, string>>({})
const saving = ref<Record<number, boolean>>({})
const errors = ref<Record<number, string>>({})
const okMsg = ref('')

async function load() {
  rows.value = await api<Pillar[]>('/pillars')
  // 以服务端为准重置草稿，非法米标整单打回时页面/色块一律保持挪柱前
  drafts.value = {}
  for (const r of rows.value) drafts.value[r.id] = String(r.position_m)
}

onMounted(load)

async function save(r: Pillar) {
  errors.value[r.id] = ''
  okMsg.value = ''
  const raw = (drafts.value[r.id] ?? '').trim()
  const pos = Number(raw)
  if (raw === '' || !Number.isFinite(pos)) {
    errors.value[r.id] = '米标非法：必须是有限数字'
    drafts.value[r.id] = String(r.position_m)
    return
  }
  saving.value[r.id] = true
  try {
    await api(`/pillars/${r.id}`, { method: 'PUT', body: JSON.stringify({ position_m: pos }) })
    await load() // 柱列表与顶部禁入色块同时跟新柱心
    okMsg.value = `「${r.label}」已挪到 ${pos}m，请到「分配带」重新分配，主图与放不下将整段按新柱心重切。`
  } catch (e: any) {
    // 整单打回：后端未改任何数据；草稿回滚，页面/色块保持挪柱前，禁止半成功
    errors.value[r.id] = extractErr(e)
    drafts.value[r.id] = String(r.position_m)
  } finally {
    saving.value[r.id] = false
  }
}

function extractErr(e: any): string {
  const m = /"detail"\s*:\s*"([^"]*)"/.exec(String(e?.message ?? e))
  return m ? m[1] : '米标非法，已整单打回'
}
</script>

<template>
  <h1>挡柱</h1>
  <p class="sub">街段障碍 · 挪柱保存后整段重切，柱列表 / 分配带禁入色块 / 放不下同一套新柱心</p>

  <div class="ss-street-band" style="height:90px;min-height:90px">
    <div class="ss-street-inner" style="gap:1rem;padding:0 1rem;align-items:center">
      <div
        v-for="r in rows" :key="r.id"
        class="ss-band-cell ss-pillar"
        :style="{ width: Math.max(r.thickness_m * 28, 36) + 'px', flex: '0 0 auto', height: '70%' }"
      >{{ r.label }} @{{ r.position_m }}m</div>
    </div>
  </div>

  <p v-if="okMsg" class="ok-line">{{ okMsg }}</p>

  <div class="card">
    <table>
      <thead><tr><th>名称</th><th>米标(m)</th><th>厚度(m)</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.label }}</td>
          <td>
            <input
              v-model="drafts[r.id]"
              type="number" step="0.1" inputmode="decimal"
              class="meter-input"
              :aria-label="r.label + ' 米标'"
            >
            <span v-if="errors[r.id]" class="err-line">{{ errors[r.id] }}</span>
          </td>
          <td>{{ r.thickness_m }}</td>
          <td>
            <button
              class="btn"
              :disabled="!!saving[r.id] || drafts[r.id] === String(r.position_m)"
              @click="save(r)"
            >{{ saving[r.id] ? '保存中…' : '保存' }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.meter-input {
  width: 92px;
  padding: 0.32rem 0.45rem;
  font-size: 0.88rem;
  border: 2px solid var(--ss-curb);
  border-radius: 3px;
  background: #fffaf0;
}
.err-line {
  display: block;
  margin-top: 0.25rem;
  color: var(--ss-bad);
  font-size: 0.76rem;
  font-weight: 700;
}
.ok-line {
  color: var(--ss-ok);
  font-size: 0.82rem;
  font-weight: 700;
  margin: 0.4rem 0;
}
</style>
