<template>
  <q-page class="page-pad">
    <div class="row items-center q-mb-md">
      <div class="text-h5">双作业差分台</div>
      <q-space />
      <q-btn flat label="返回历史" to="/jobs" />
    </div>

    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="text-caption text-grey-7 q-mb-sm">
          选择两条作业，由服务端差分接口（POST /api/jobs/diff）计算总体状态、三指标差值与四阶段状态对照。
          审计员可使用本页；本页不会提交新作业。
        </div>
        <div class="row q-col-gutter-md items-center">
          <div class="col-12 col-md-5">
            <q-select
              v-model="baseId"
              :options="jobOptions"
              label="基准作业 A"
              outlined
              dense
              emit-value
              map-options
            >
              <template #option="slotProps">
                <q-item v-bind="slotProps.itemProps">
                  <q-item-section>
                    <q-item-label>
                      #{{ slotProps.opt.value }} {{ slotProps.opt.sample_name }}
                      <q-badge
                        :color="statusColor(slotProps.opt.status)"
                        class="q-ml-xs"
                      >{{ statusLabel(slotProps.opt.status) }}</q-badge>
                    </q-item-label>
                    <q-item-label caption>
                      {{ slotProps.opt.created_by }} · {{ fmtTime(slotProps.opt.created_at) }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </template>
            </q-select>
          </div>
          <div class="col-12 col-md-5">
            <q-select
              v-model="targetId"
              :options="jobOptions"
              label="对比作业 B（差值 = B − A）"
              outlined
              dense
              emit-value
              map-options
            >
              <template #option="slotProps">
                <q-item v-bind="slotProps.itemProps">
                  <q-item-section>
                    <q-item-label>
                      #{{ slotProps.opt.value }} {{ slotProps.opt.sample_name }}
                      <q-badge
                        :color="statusColor(slotProps.opt.status)"
                        class="q-ml-xs"
                      >{{ statusLabel(slotProps.opt.status) }}</q-badge>
                    </q-item-label>
                    <q-item-label caption>
                      {{ slotProps.opt.created_by }} · {{ fmtTime(slotProps.opt.created_at) }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </template>
            </q-select>
          </div>
          <div class="col-12 col-md-2">
            <q-btn
              color="primary"
              class="full-width"
              label="执行差分"
              :loading="loading"
              :disable="!baseId || !targetId || baseId === targetId"
              @click="runDiff"
            />
          </div>
        </div>
      </q-card-section>
    </q-card>

    <template v-if="diff">
      <q-banner
        rounded
        class="q-mb-md"
        :class="diff.status_same ? 'bg-positive text-white' : 'bg-negative text-white'"
      >
        <div class="text-subtitle1">
          总体状态：{{ diff.status_same ? '相同' : '不一致' }}
        </div>
        <div class="q-mt-sm row q-col-gutter-md items-center">
          <div class="col-auto">
            <strong>基准 A：</strong>
            <router-link :to="`/jobs/${diff.base.id}`" class="text-white">
              #{{ diff.base.id }} {{ diff.base.sample_name }}
            </router-link>
            <q-badge :color="statusColor(diff.base.status)" class="q-ml-sm">
              {{ statusLabel(diff.base.status) }}
            </q-badge>
          </div>
          <div class="col-auto">
            <strong>对比 B：</strong>
            <router-link :to="`/jobs/${diff.target.id}`" class="text-white">
              #{{ diff.target.id }} {{ diff.target.sample_name }}
            </router-link>
            <q-badge :color="statusColor(diff.target.status)" class="q-ml-sm">
              {{ statusLabel(diff.target.status) }}
            </q-badge>
          </div>
        </div>
      </q-banner>

      <div class="text-subtitle1 q-mb-sm">三指标差值（B − A）</div>
      <q-markup-table flat bordered class="diff-table q-mb-lg">
        <thead>
          <tr>
            <th class="text-left">指标</th>
            <th class="text-left">基准 A</th>
            <th class="text-left">对比 B</th>
            <th class="text-left">差值（B − A）</th>
            <th class="text-left">结论</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in diff.metric_diffs" :key="m.key" :class="{ 'row-mismatch': !m.same }">
            <td>{{ m.label }}</td>
            <td>
              <q-badge v-if="m.base_missing" color="orange-9" text-color="white">A 侧缺失</q-badge>
              <span v-else>{{ m.base_value }}</span>
            </td>
            <td>
              <q-badge v-if="m.target_missing" color="orange-9" text-color="white">B 侧缺失</q-badge>
              <span v-else>{{ m.target_value }}</span>
            </td>
            <td>
              <q-badge v-if="m.base_missing || m.target_missing" color="grey-7">无法比较</q-badge>
              <span v-else :class="deltaClass(m.delta)">{{ formatDelta(m.delta) }}</span>
            </td>
            <td>
              <q-badge :color="m.same ? 'positive' : 'negative'">
                {{ m.same ? '一致' : '不一致' }}
              </q-badge>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <div class="text-subtitle1 q-mb-sm">四阶段状态对照表</div>
      <q-markup-table flat bordered class="diff-table q-mb-lg">
        <thead>
          <tr>
            <th class="text-left">阶段（Actor）</th>
            <th class="text-left">基准 A</th>
            <th class="text-left">对比 B</th>
            <th class="text-left">结论</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in diff.stage_diffs" :key="s.actor_name" :class="{ 'row-mismatch': !s.same }">
            <td>{{ s.stage_order + 1 }}. {{ s.actor_name }}</td>
            <td>
              <q-badge v-if="s.base_missing" color="orange-9" text-color="white">A 侧缺失</q-badge>
              <q-badge v-else :color="stageColor(s.base_status)">{{ stageLabel(s.base_status) }}</q-badge>
            </td>
            <td>
              <q-badge v-if="s.target_missing" color="orange-9" text-color="white">B 侧缺失</q-badge>
              <q-badge v-else :color="stageColor(s.target_status)">{{ stageLabel(s.target_status) }}</q-badge>
            </td>
            <td>
              <q-badge :color="s.same ? 'positive' : 'negative'">
                {{ s.same ? '一致' : '不一致' }}
              </q-badge>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <div class="text-caption text-grey-7">
        以上差值与状态对照全部来自服务端差分接口 <code>POST /api/jobs/diff</code> 的响应，
        页面未基于两条作业详情自行做减法；可点作业编号进入两侧详情页核对。
      </div>
    </template>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { diffJobs, listJobs } from '../api/client'

const route = useRoute()
const $q = useQuasar()

const jobs = ref([])
const baseId = ref(null)
const targetId = ref(null)
const loading = ref(false)
const diff = ref(null)

const jobOptions = computed(() =>
  jobs.value.map((j) => ({
    value: j.id,
    label: `#${j.id} ${j.sample_name}（${statusLabel(j.status)}）`,
    sample_name: j.sample_name,
    status: j.status,
    created_by: j.created_by,
    created_at: j.created_at,
  })),
)

function statusLabel(s) {
  return { pending: '排队中', running: '运行中', success: '成功', failed: '失败' }[s] || s || '—'
}

function statusColor(s) {
  return { pending: 'grey', running: 'info', success: 'positive', failed: 'negative' }[s] || 'grey'
}

function stageLabel(s) {
  return (
    {
      pending: '排队中',
      running: '运行中',
      success: '成功',
      failed: '失败',
      skipped: '已跳过',
    }[s] || s || '—'
  )
}

function stageColor(s) {
  return (
    {
      pending: 'grey',
      running: 'info',
      success: 'positive',
      failed: 'negative',
      skipped: 'warning',
    }[s] || 'grey'
  )
}

function formatDelta(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return `${v > 0 ? '+' : ''}${v}`
  return String(v)
}

function deltaClass(v) {
  if (v === null || v === undefined || v === 0) return 'text-grey-7'
  return v > 0 ? 'text-positive' : 'text-negative'
}

function fmtTime(iso) {
  return iso ? new Date(iso).toLocaleString() : ''
}

async function loadJobs() {
  jobs.value = await listJobs()
}

async function runDiff() {
  if (!baseId.value || !targetId.value) {
    $q.notify({ type: 'warning', message: '请先选择两条作业' })
    return
  }
  if (baseId.value === targetId.value) {
    $q.notify({ type: 'warning', message: '请选择两条不同的作业' })
    return
  }
  loading.value = true
  diff.value = null
  try {
    diff.value = await diffJobs(baseId.value, targetId.value)
  } catch (e) {
    $q.notify({ type: 'negative', message: e.message || '差分失败' })
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await loadJobs()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.message || '作业列表加载失败' })
    return
  }
  const qBase = Number(route.query.base)
  const qTarget = Number(route.query.target)
  if (qBase && jobs.value.some((j) => j.id === qBase)) baseId.value = qBase
  if (qTarget && jobs.value.some((j) => j.id === qTarget)) targetId.value = qTarget
  if (baseId.value && targetId.value && baseId.value !== targetId.value) {
    await runDiff()
  }
})
</script>

<style scoped>
.diff-table .row-mismatch {
  background-color: #fdecea;
}
</style>
