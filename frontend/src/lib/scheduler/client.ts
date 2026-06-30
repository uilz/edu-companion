/**
 * ClientScheduler — 客户端前台调度器
 *
 * 统一管理所有前端周期任务（事件聚合、活跃检查等），
 * 使用 requestIdleCallback 在浏览器空闲时段执行，
 * fallback 到 setTimeout 以保证兼容性。
 */
export interface SchedulerTask {
  name: string
  interval: number
  fn: () => Promise<void> | void
  _timerId?: ReturnType<typeof setTimeout> | null
  _lastRun?: number
  _runCount: number
  _errorCount: number
  _running: boolean
}

class ClientScheduler {
  private _tasks: Map<string, SchedulerTask> = new Map()
  private _started = false

  addTask(name: string, intervalMs: number, fn: () => Promise<void> | void): void {
    if (this._tasks.has(name)) {
      console.warn(`[ClientScheduler] 任务 ${name} 已存在，跳过`)
      return
    }
    this._tasks.set(name, {
      name,
      interval: intervalMs,
      fn,
      _runCount: 0,
      _errorCount: 0,
      _running: false,
    })
  }

  startAll(): void {
    if (this._started) return
    this._started = true
    this._tasks.forEach((task) => {
      task._running = true
      this._scheduleNext(task)
    })
    console.log(`[ClientScheduler] 已启动 ${this._tasks.size} 个前台任务`)
  }

  stopAll(): void {
    this._started = false
    this._tasks.forEach((task) => {
      task._running = false
      if (task._timerId) {
        clearTimeout(task._timerId)
        task._timerId = null
      }
    })
    console.log('[ClientScheduler] 所有前台任务已停止')
  }

  getStats() {
    return {
      started: this._started,
      tasks: Array.from(this._tasks.values()).map((t) => ({
        name: t.name,
        interval: t.interval,
        runCount: t._runCount,
        errorCount: t._errorCount,
        running: t._running,
      })),
    }
  }

  private _scheduleNext(task: SchedulerTask): void {
    if (!task._running) return
    const run = () => {
      if (!task._running) return
      this._executeTask(task)
      this._scheduleAfter(task)
    }
    task._timerId = setTimeout(run, task.interval)
  }

  private _scheduleAfter(task: SchedulerTask): void {
    if (!task._running) return
    if (typeof requestIdleCallback === 'function') {
      task._timerId = setTimeout(
        () => requestIdleCallback(
          () => this._executeTask(task),
          { timeout: task.interval },
        ),
        task.interval,
      )
    } else {
      task._timerId = setTimeout(() => this._executeTask(task), task.interval)
    }
  }

  private async _executeTask(task: SchedulerTask): Promise<void> {
    task._lastRun = Date.now()
    try {
      await task.fn()
      task._runCount++
    } catch (err) {
      task._errorCount++
      console.error(`[ClientScheduler] 任务 ${task.name} 执行失败:`, err)
    }
  }
}

export const clientScheduler = new ClientScheduler()
