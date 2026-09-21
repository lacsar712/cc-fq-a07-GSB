<template>
  <q-page class="page-pad">
    <div class="row items-center q-mb-md">
      <div class="text-h5">作业差分台</div>
      <q-space />
      <q-btn flat icon="refresh" label="刷新作业" @click="loadJobs" :loading="loadingJobs" />
      <q-btn flat label="返回历史" to="/jobs" />
    </div>

    <q-banner rounded class="q-mb-md bg-blue-1 text-blue-9">
      选择两条作业，由<strong class="q-mx-xs">服务端差分接口</strong>给出：状态是否相同、三项指标差值（A − B）、四阶段状态对照。
      审计员可使用本页，本页不提供任何提交作业入口。
    </q-banner>

    <q-card flat bordered class="q-mb-md">
      <q-card-section class="row q-col-gutter-md items-end">
        <div class="col-12 col-md-4">
          <q-select
            v-model="jobAId"
            :options="jobOptions"
            label="作业 A（差值左侧）"
            outlined
            dense
            emit-value
            map-options
          />
        </div>
        <div class="col-12 col-md-1">
          <div class="text-center text-h5 text-grey-6">vs</div>
        </div>
        <div class="col-12 col-md-4">
          <q-select
            v-model="jobBId"
            :options="jobOptions"
            label="作业 B（差值右侧）"
            outlined
            dense
            emit-value
            map-options
          />
        </div>
        <div class="col-12 col-md-3">
          <q-btn
            color="primary"
            icon="difference"
            label="执行服务端差分"
            class="full-width"
            :loading="loadingDiff"
            :disable="!jobAId || !jobBId"
            @click="runDiff(true)"
          />
        </div>
      </q-card-section>
    </q-card>

    <template v-if="diff">
      <!-- Verdict -->
      <q-banner
        rounded
        class="q-mb-md"
        :class="diff.all_equal ? 'bg-positive text-white' : 'bg-negative text-white'"
      >
        <div class="text-subtitle1">
          {{ diff.all_equal ? '两条作业完全一致' : '两条作业存在差异' }}
        </div>
        <div class="q-mt-xs">
          作业总体状态：
          <q-badge :color="diff.status_equal ? 'white' : 'amber'" :text-color="diff.status_equal ? 'positive' : 'dark'">
            {{ diff.status_equal ? '相同' : '不同' }}
          </q-badge>
        </div>
      </q-banner>

      <!-- Two-side summary with links to both detail pages -->
      <div class="row q-col-gutter-md q-mb-md">
        <div class="col-12 col-md-6" v-for="(side, key) in sides" :key="key">
          <q-card flat bordered>
            <q-card-section>
              <div class="text-caption text-grey-7">{{ side === 'a' ? '作业 A' : '作业 B' }}</div>
              <div class="text-h6">
                #{{ sideJob(side).id }} · {{ sideJob(side).sample_name }}
              </div>
              <div class="q-mt-xs">
                <q-badge :color="statusColor(sideJob(side).status)">
                  {{ statusLabel(sideJob(side).status) }}
                </q-badge>
                <span class="q-ml-sm text-grey-8">提交人：{{ sideJob(side).created_by }}</span>
              </div>
              <q-btn
                flat
                dense
                color="primary"
                icon="open_in_new"
                label="查看该侧详情（用于对账）"
                class="q-mt-sm"
                :to="`/jobs/${sideJob(side).id}`"
              />
            </q-card-section>
          </q-card>
        </div>
      </div>

      <!-- Three metric deltas -->
      <div class="text-subtitle1 q-mb-sm">三指标差值（来自差分接口，差值 = A − B）</div>
      <q-markup-table flat bordered class="q-mb-lg diff-table">
        <thead>
          <tr>
            <th class="text-left">指标</th>
            <th class="text-left">作业 A</th>
            <th class="text-left">作业 B</th>
            <th class="text-left">差值 (A − B)</th>
            <th class="text-left">比对</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in diff.metrics" :key="m.key" :class="{ 'row-mismatch': !m.equal }">
            <td class="text-weight-medium">{{ m.label }}</td>
            <td>
              <span v-if="m.present_a">{{ m.value_a }}</span>
              <q-badge v-else color="deep-orange" text-color="white">A 侧缺失</q-badge>
            </td>
            <td>
              <span v-if="m.present_b">{{ m.value_b }}</span>
              <q-badge v-else color="deep-orange" text-color="white">B 侧缺失</q-badge>
            </td>
            <td>
              <span v-if="m.delta !== null" :class="deltaClass(m.delta)" class="text-weight-medium">
                {{ formatDelta(m.delta) }}
              </span>
              <span v-else-if="m.both_missing" class="text-grey-6">—（两侧均无此指标）</span>
              <span v-else class="text-deep-orange">—（单侧缺失，无法相减）</span>
            </td>
            <td>
              <q-badge v-if="m.equal" color="positive">一致</q-badge>
              <q-badge v-else-if="m.present_a && m.present_b" color="negative">不一致</q-badge>
              <q-badge v-else color="deep-orange" text-color="white">单侧缺失</q-badge>
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <!-- Four-stage status table -->
      <div class="text-subtitle1 q-mb-sm">四阶段状态对照表（来自差分接口）</div>
      <q-markup-table flat bordered class="q-mb-lg diff-table">
        <thead>
          <tr>
            <th class="text-left">#</th>
            <th class="text-left">Actor 阶段</th>
            <th class="text-left">作业 A 状态</th>
            <th class="text-left">作业 B 状态</th>
            <th class="text-left">比对</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in diff.stages" :key="s.actor_name" :class="{ 'row-mismatch': !s.equal }">
            <td>{{ s.stage_order + 1 }}</td>
            <td class="text-weight-medium">{{ s.actor_name }}</td>
            <td>
              <q-badge v-if="!s.missing_a" :color="stageColor(s.status_a)">
                {{ stageLabel(s.status_a) }}
              </q-badge>
              <q-badge v-else color="deep-orange" text-color="white">A 侧缺失</q-badge>
            </td>
            <td>
              <q-badge v-if="!s.missing_b" :color="stageColor(s.status_b)">
                {{ stageLabel(s.status_b) }}
              </q-badge>
              <q-badge v-else color="deep-orange" text-color="white">B 侧缺失</q-badge>
            </td>
            <td>
              <q-badge v-if="s.equal" color="positive">一致</q-badge>
              <q-badge v-else color="negative">不一致</q-badge>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
    </template>

    <q-card v-else flat bordered>
      <q-card-section class="text-grey-6">
        请在上方选择两条不同的作业后点击「执行服务端差分」。
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { diffJobs, listJobs } from '../api/client'

const route = useRoute()
const router = useRouter()
const $q = useQuasar()

const jobs = ref([])
const jobAId = ref(null)
const jobBId = ref(null)
const diff = ref(null)
const loadingJobs = ref(false)
const loadingDiff = ref(false)

const jobOptions = computed(() =>
  jobs.value.map((j) => ({
    value: j.id,
    label: `#${j.id} ${j.sample_name}（${statusLabel(j.status)} · ${j.created_by}）`,
  })),
)

const sides = ['a', 'b']

function sideJob(side) {
  return side === 'a' ? diff.value.job_a : diff.value.job_b
}

function statusLabel(s) {
  return { pending: '排队中', running: '运行中', success: '成功', failed: '失败' }[s] || s || '缺失'
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
    }[s] || s || '缺失'
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

function formatDelta(d) {
  if (typeof d !== 'number') return String(d)
  return d > 0 ? `+${d}` : `${d}`
}

function deltaClass(d) {
  if (d === 0) return 'text-positive'
  return d > 0 ? 'text-positive' : 'text-negative'
}

async function loadJobs() {
  loadingJobs.value = true
  try {
    jobs.value = await listJobs()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.message || '作业列表加载失败' })
  } finally {
    loadingJobs.value = false
  }
}

async function runDiff(syncQuery) {
  if (!jobAId.value || !jobBId.value) {
    $q.notify({ type: 'warning', message: '请先选择两条作业' })
    return
  }
  if (jobAId.value === jobBId.value) {
    $q.notify({ type: 'warning', message: '差分需要选择两条不同的作业' })
    return
  }
  loadingDiff.value = true
  try {
    diff.value = await diffJobs(jobAId.value, jobBId.value)
    if (syncQuery) {
      router.replace({
        query: { a: String(jobAId.value), b: String(jobBId.value) },
      })
    }
  } catch (e) {
    diff.value = null
    $q.notify({ type: 'negative', message: e.message || '差分失败' })
  } finally {
    loadingDiff.value = false
  }
}

onMounted(async () => {
  await loadJobs()
  const qa = Number(route.query.a)
  const qb = Number(route.query.b)
  if (qa && qb && qa !== qb) {
    jobAId.value = qa
    jobBId.value = qb
    await runDiff(false)
  }
})
</script>
