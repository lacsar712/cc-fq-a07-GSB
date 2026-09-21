<template>
  <q-page class="page-pad">
    <div class="row items-center q-mb-md">
      <div class="text-h5">作业历史</div>
      <q-space />
      <q-btn
        color="deep-purple"
        icon="difference"
        class="q-mr-sm"
        :label="`差分选中（${selected.length}/2）`"
        :disable="selected.length !== 2"
        @click="goDiff"
      />
      <q-btn flat icon="refresh" label="刷新" @click="load" :loading="loading" />
      <q-btn
        v-if="auth.role === 'bioops'"
        color="primary"
        class="q-ml-sm"
        label="新建作业"
        to="/jobs/new"
      />
    </div>

    <div v-if="auth.role === 'auditor'" class="text-caption text-grey-7 q-mb-sm">
      审计员为只读角色：可勾选两条作业进行差分，但不能提交新作业。
    </div>

    <q-table
      flat
      bordered
      row-key="id"
      :rows="rows"
      :columns="columns"
      :loading="loading"
      selection="multiple"
      :selected="selected"
      @update:selected="onSelectionUpdate"
      hide-pagination
      :pagination="{ rowsPerPage: 0 }"
    >
      <template #body-cell-status="props">
        <q-td :props="props">
          <q-badge :color="statusColor(props.row.status)">
            {{ statusLabel(props.row.status) }}
          </q-badge>
        </q-td>
      </template>
      <template #body-cell-metrics="props">
        <q-td :props="props">
          <span v-if="props.row.metrics">
            Q={{ props.row.metrics.mean_quality ?? '—' }}
            · N={{ props.row.metrics.n_rate ?? '—' }}
            · reads={{ props.row.metrics.reads ?? '—' }}
          </span>
          <span v-else class="text-grey-6">—</span>
        </q-td>
      </template>
      <template #body-cell-actions="props">
        <q-td :props="props">
          <q-btn dense flat color="primary" label="详情" :to="`/jobs/${props.row.id}`" />
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { listJobs } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const $q = useQuasar()
const loading = ref(false)
const rows = ref([])
const selected = ref([])

const columns = [
  { name: 'id', label: 'ID', field: 'id', align: 'left' },
  { name: 'sample_name', label: '样例', field: 'sample_name', align: 'left' },
  { name: 'status', label: '状态', field: 'status', align: 'left' },
  { name: 'created_by', label: '提交人', field: 'created_by', align: 'left' },
  { name: 'metrics', label: '指标摘要', field: 'metrics', align: 'left' },
  {
    name: 'created_at',
    label: '创建时间',
    field: 'created_at',
    align: 'left',
    format: (v) => (v ? new Date(v).toLocaleString() : ''),
  },
  { name: 'actions', label: '操作', field: 'actions', align: 'left' },
]

function onSelectionUpdate(val) {
  if (val.length > 2) {
    // Reject the (de)selection beyond two rows; :selected stays at two.
    $q.notify({ type: 'warning', message: '差分最多选择两条作业' })
    return
  }
  selected.value = val.slice()
}

function goDiff() {
  if (selected.value.length !== 2) return
  const [a, b] = selected.value
  router.push({ path: '/jobs/diff', query: { a: a.id, b: b.id } })
}

function statusLabel(s) {
  return { pending: '排队中', running: '运行中', success: '成功', failed: '失败' }[s] || s
}

function statusColor(s) {
  return { pending: 'grey', running: 'info', success: 'positive', failed: 'negative' }[s] || 'grey'
}

async function load() {
  loading.value = true
  try {
    rows.value = await listJobs()
    selected.value = []
  } catch (e) {
    $q.notify({ type: 'negative', message: e.message || '加载失败' })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
