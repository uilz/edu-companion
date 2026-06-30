/**
 * EventAggregator Worker — 客户端事件聚合
 *
 * 在 Web Worker 中执行 3维度×6时间窗口 的事件聚合计算，
 * 不阻塞主线程。
 *
 * WINDOWS: 5m, 30m, 1h, day, week, month
 * DIMENSIONS: mixed, topic, type
 */

const WINDOWS = [5, 30, 60, 1440, 10080, 43200]
const DIMENSIONS = ['mixed', 'topic', 'type'] as const
const THRESHOLDS: Record<string, number> = { mixed: 2, topic: 1, type: 2 }

interface RawEvent {
  id: string
  event_type: string
  user_id: string
  payload?: Record<string, unknown>
  created_at: string | number
  importance?: number
  stream_type?: string
  stream_id?: string
}

interface AggregateResult {
  event_type: string
  dimension: string
  window_minutes: number
  child_ids: string[]
  payload: Record<string, unknown>
  summary: string
  importance: number
}

interface AggregationRequest {
  type: 'aggregate'
  events: RawEvent[]
  userId: string
}

interface AggregationResponse {
  type: 'result'
  aggregates: AggregateResult[]
  userId: string
}

self.onmessage = (e: MessageEvent<AggregationRequest>) => {
  if (e.data.type !== 'aggregate') return

  const { events, userId } = e.data
  const aggregates: AggregateResult[] = []

  for (const windowMinutes of WINDOWS) {
    for (const dimension of DIMENSIONS) {
      const results = aggregateDimension(events, dimension, windowMinutes)
      aggregates.push(...results)
    }
  }

  const response: AggregationResponse = { type: 'result', aggregates, userId }
  self.postMessage(response)
}

function aggregateDimension(
  events: RawEvent[],
  dimension: string,
  windowMinutes: number,
): AggregateResult[] {
  const threshold = THRESHOLDS[dimension] ?? 2
  const windowEvents = filterByWindow(events, windowMinutes)
  if (windowEvents.length < threshold) return []

  const groups = groupByDimension(windowEvents, dimension, windowMinutes)
  const results: AggregateResult[] = []

  for (const [groupKey, groupEvents] of Object.entries(groups)) {
    if (groupEvents.length < threshold) continue

    const payload: Record<string, unknown> = {
      dimension,
      window_minutes: windowMinutes,
      child_count: groupEvents.length,
      child_type_counts: countByType(groupEvents),
    }
    if (dimension === 'topic') payload.topic_label = groupKey
    if (dimension === 'type') payload.type_label = groupKey

    const answers = groupEvents.filter((e) => e.event_type === 'AnswerSubmitted')
    if (answers.length > 0) {
      const correct = answers.filter((a) => {
        const p = a.payload ?? {}
        return (p as Record<string, unknown>).is_correct === true
      }).length
      payload.accuracy = correct / answers.length
    }

    const avgImp = groupEvents.reduce((s, e) => s + (e.importance ?? 0), 0) / groupEvents.length
    const importance = Math.min(1, avgImp + 0.1 * (windowMinutes / 1440))

    const eventTypeMap: Record<string, string> = {
      mixed: 'EpisodeDigest',
      topic: 'TopicDigest',
      type: 'TypeDigest',
    }

    results.push({
      event_type: eventTypeMap[dimension] ?? 'EpisodeDigest',
      dimension,
      window_minutes: windowMinutes,
      child_ids: groupEvents.map((e) => e.id),
      payload,
      summary: buildSummary(groupEvents, dimension, windowMinutes, groupKey),
      importance,
    })
  }
  return results
}

function filterByWindow(events: RawEvent[], windowMinutes: number): RawEvent[] {
  const now = Date.now()
  const cutoff = now - windowMinutes * 60 * 1000
  return events.filter((e) => {
    const t = typeof e.created_at === 'string'
      ? new Date(e.created_at).getTime()
      : e.created_at * 1000
    return t >= cutoff
  })
}

function groupByDimension(events: RawEvent[], dimension: string, _wm: number): Record<string, RawEvent[]> {
  const groups: Record<string, RawEvent[]> = {}
  if (dimension === 'mixed') {
    groups['all'] = events
  } else if (dimension === 'type') {
    for (const e of events) {
      const key = e.event_type || 'unknown'
      if (!groups[key]) groups[key] = []
      groups[key].push(e)
    }
  } else if (dimension === 'topic') {
    for (const e of events) {
      const key = extractTopic(e) || '未分类'
      if (!groups[key]) groups[key] = []
      groups[key].push(e)
    }
  }
  return groups
}

function extractTopic(event: RawEvent): string {
  const p = (event.payload ?? {}) as Record<string, unknown>
  for (const field of ['skill_id', 'label', 'topic_label', 'domain']) {
    const v = p[field]
    if (v && typeof v === 'string' && v.length > 0) return v
  }
  return '未分类'
}

function countByType(events: RawEvent[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const e of events) counts[e.event_type] = (counts[e.event_type] ?? 0) + 1
  return counts
}

function buildSummary(_events: RawEvent[], dimension: string, wm: number, groupKey: string): string {
  const wn: Record<number, string> = { 5: '5分钟', 30: '30分钟', 60: '1小时', 1440: '一天', 10080: '一周', 43200: '一个月' }
  const dl: Record<string, string> = { mixed: '学习片段', topic: groupKey, type: groupKey }
  return `${wn[wm] ?? wm + '分钟'}内的${dl[dimension] ?? dimension} (${_events.length}条事件)`
}
