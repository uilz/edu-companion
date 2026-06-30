/**
 * Scheduler Tasks — 客户端周期任务注册
 *
 * 将所有需要在客户端执行的后台任务注册到 clientScheduler：
 * 1. 事件聚合 (Web Worker) — 60s
 * 2. 活跃检查 (API) — 600s
 */
import { clientScheduler } from './client'
import { api } from '@/lib/api/api'

let _started = false

export function startClientTasks(): void {
  if (_started) return
  _started = true

  clientScheduler.addTask('event_aggregation', 60000, aggregateViaWorker)
  clientScheduler.addTask('active_check', 600000, activeCheck)
  clientScheduler.startAll()
}

export function stopClientTasks(): void {
  _started = false
  clientScheduler.stopAll()
}

let _worker: Worker | null = null

function getWorker(): Worker {
  if (!_worker) {
    _worker = new Worker(
      new URL('./event-aggregator.worker', import.meta.url),
      { type: 'module' },
    )
    _worker.onmessage = async (e) => {
      const { type, aggregates, userId } = e.data
      if (type !== 'result' || !aggregates?.length) return
      try {
        await api('/api/events/aggregate', {
          method: 'POST',
          body: JSON.stringify({ aggregates }),
        })
        console.debug(`[ClientTasks] 写入 ${aggregates.length} 条聚合结果 (user=${userId})`)
      } catch (err) {
        console.error('[ClientTasks] 聚合结果写入失败:', err)
      }
    }
  }
  return _worker
}

async function aggregateViaWorker(): Promise<void> {
  try {
    const res = await api<{ ok: boolean; events: Record<string, unknown>[]; count: number }>(
      '/api/events/raw?limit=500&window_minutes=43200',
    )
    if (!res.ok || !res.events?.length) return

    const userStr = typeof window !== 'undefined'
      ? localStorage.getItem('current_user')
      : null
    const userId = userStr ? JSON.parse(userStr).id || '' : ''

    getWorker().postMessage({ type: 'aggregate', events: res.events, userId })
  } catch (err) {
    console.debug('[ClientTasks] 事件聚合获取失败:', err)
  }
}

async function activeCheck(): Promise<void> {
  try {
    await api('/api/secretary/checker/run', { method: 'POST' })
  } catch (err) {
    console.debug('[ClientTasks] 活跃检查失败:', err)
  }
}
