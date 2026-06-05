'use client';

// ── 导入 React Hooks 和 UI 图标库 ──
import { useState, useEffect, useRef, useCallback } from 'react';
import { Play, Pause, RotateCcw, Timer, Coffee, Flame, TrendingUp, Clock, Zap, Brain, Target } from 'lucide-react';
// ── 导入自定义卡片组件 ──
import Card from '@/components/ui/Card';

// ── Constants ──
// 番茄钟工作时长：25 分钟（单位：秒）
const POMODORO_WORK = 25 * 60;
// 番茄钟休息时长：5 分钟（单位：秒）
const POMODORO_BREAK = 5 * 60;

// ── 当前阶段的类型：工作 or 休息 ──
type Phase = 'work' | 'break';

// ── 单次番茄钟会话的日志接口 ──
interface SessionLog {
  date: string;       // 日期（YYYY-MM-DD）
  minutes: number;    // 专注分钟数
  completed: boolean; // 是否完成
}

// ── 学习计划 Tab 主组件 ──
export function StudyTab() {
  // ── 状态管理 ──
  const [seconds, setSeconds] = useState(POMODORO_WORK);           // 当前倒计时秒数
  const [isRunning, setIsRunning] = useState(false);                // 计时器是否正在运行
  const [phase, setPhase] = useState<Phase>('work');                // 当前阶段（工作/休息）
  const [todaySessions, setTodaySessions] = useState<SessionLog[]>([]); // 今日已完成会话列表
  const [streak, setStreak] = useState(0);                          // 连续学习天数
  const [todayMinutes, setTodayMinutes] = useState(0);              // 今日累计专注分钟数
  const intervalRef = useRef<NodeJS.Timeout | null>(null);          // 定时器引用

  // ── 组件挂载时：从 localStorage 加载今日会话和连续天数 ──
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);           // 获取今天的日期字符串
    const stored = localStorage.getItem(`study-sessions-${today}`); // 读取今日存储的会话数据
    if (stored) {
      const sessions: SessionLog[] = JSON.parse(stored);
      setTodaySessions(sessions);
      setTodayMinutes(sessions.reduce((s, l) => s + l.minutes, 0)); // 累加今日总分钟数
    }
    const streakVal = parseInt(localStorage.getItem('study-streak') || '0', 10);
    setStreak(streakVal);
  }, []);

  // ── 计时器核心逻辑：每秒 tick，到点时切换阶段并记录会话 ──
  const tick = useCallback(() => {
    setSeconds((prev) => {
      if (prev <= 1) {
        // 计时结束——切换阶段
        if (phase === 'work') {
          // 工作阶段结束：记录本次会话并切换到休息
          const session: SessionLog = {
            date: new Date().toISOString().slice(0, 10),
            minutes: POMODORO_WORK / 60,
            completed: true,
          };
          const updated = [...todaySessions, session];
          setTodaySessions(updated);
          setTodayMinutes((m) => m + POMODORO_WORK / 60);
          const today = new Date().toISOString().slice(0, 10);
          localStorage.setItem(`study-sessions-${today}`, JSON.stringify(updated));
          setPhase('break');
          return POMODORO_BREAK; // 重置为休息时长
        } else {
          // 休息阶段结束：切回工作
          setPhase('work');
          return POMODORO_WORK; // 重置为工作时长
        }
      }
      return prev - 1; // 正常倒计时
    });
  }, [phase, todaySessions]);

  // ── 根据 isRunning 状态启动/停止定时器 ──
  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(tick, 1000); // 每秒执行一次 tick
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current); // 清理定时器
    };
  }, [isRunning, tick]);

  // ── 切换计时器运行/暂停状态 ──
  const toggleTimer = () => setIsRunning((r) => !r);

  // ── 重置计时器到当前阶段的初始时长 ──
  const resetTimer = () => {
    setIsRunning(false);
    setSeconds(phase === 'work' ? POMODORO_WORK : POMODORO_BREAK);
  };

  // ── 格式化显示时间 ──
  const mins = Math.floor(seconds / 60);          // 取分钟部分
  const secs = seconds % 60;                      // 取秒部分
  const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`; // 格式化为 MM:SS

  // ── 统计信息 ──
  const workSessions = todaySessions.length;       // 已完成番茄钟数
  const goalSessions = 6; // 每日目标：6 个番茄钟（6×25 = 150 分钟/天）

  return (
    <div className="max-w-3xl mx-auto space-y-8 py-4">
      {/* ── Timer 计时器区域 ── */}
      <Card className="!p-8 text-center">
        <div className="inline-flex items-center gap-2 text-xs text-[var(--color-text-muted)] uppercase tracking-widest mb-4">
          {phase === 'work' ? (
            <><Brain size={14} className="text-[var(--color-accent)]" /> 专注学习</>
          ) : (
            <><Coffee size={14} className="text-[var(--color-success)]" /> 休息一下</>
          )}
        </div>

        {/* 倒计时数字展示 */}
        <div className="text-7xl font-semibold text-[var(--color-text)] tabular-nums tracking-tight mb-8"
          style={{ fontVariantNumeric: 'tabular-nums' }}>
          {timeStr}
        </div>

        {/* 控制按钮组：开始/暂停 + 重置 */}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={toggleTimer}
            className="inline-flex items-center gap-2 px-6 py-3 text-sm font-semibold bg-[var(--color-accent)] text-white hover:opacity-90 active:scale-[0.97] transition-opacity"
            style={{ borderRadius: '2px' }}
          >
            {isRunning ? <><Pause size={16} /> 暂停</> : <><Play size={16} /> 开始</>}
          </button>
          <button
            onClick={resetTimer}
            className="inline-flex items-center gap-2 px-4 py-3 text-sm text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-surface)] active:scale-[0.97] transition-all"
            style={{ borderRadius: '2px' }}
          >
            <RotateCcw size={14} /> 重置
          </button>
        </div>

        {/* 工作时长提示信息 */}
        {phase === 'work' && (
          <p className="text-xs text-[var(--color-text-muted)] mt-4">
            番茄钟 · {POMODORO_WORK / 60}分钟专注 → {POMODORO_BREAK / 60}分钟休息
          </p>
        )}
      </Card>

      {/* ── Today stats 今日统计数据 ── */}
      <div className="grid grid-cols-3 gap-4">
        {/* 连续天数 */}
        <Card className="!p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Flame size={18} className="text-[var(--color-warning)]" />
          </div>
          <div className="text-2xl font-semibold text-[var(--color-text)]">{streak}</div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">连续天数</div>
        </Card>

        {/* 今日专注总分钟数 */}
        <Card className="!p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Timer size={18} className="text-[var(--color-accent)]" />
          </div>
          <div className="text-2xl font-semibold text-[var(--color-text)]">{todayMinutes}</div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">今日分钟</div>
        </Card>

        {/* 今日已完成番茄钟数 / 目标 */}
        <Card className="!p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Target size={18} className="text-[var(--color-success)]" />
          </div>
          <div className="text-2xl font-semibold text-[var(--color-text)]">
            {workSessions}<span className="text-sm text-[var(--color-text-muted)]">/{goalSessions}</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">完成番茄</div>
        </Card>
      </div>

      {/* ── Progress bar 今日进度条 ── */}
      <Card className="!p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-[var(--color-text)]">
            🍅 今日进度
          </span>
          <span className="text-xs text-[var(--color-text-muted)]">
            {Math.round((workSessions / goalSessions) * 100)}%
          </span>
        </div>
        {/* 进度条填充 */}
        <div className="h-2 bg-[var(--color-surface)] overflow-hidden">
          <div
            className="h-full bg-[var(--color-accent)] active:scale-[0.97] transition-all duration-700"
            style={{ width: `${Math.min((workSessions / goalSessions) * 100, 100)}%` }}
          />
        </div>
        {/* 每日目标描述 */}
        <p className="text-[10px] text-[var(--color-text-muted)] mt-3">
          目标：每天 {goalSessions} 个番茄钟 ({goalSessions * POMODORO_WORK / 60} 分钟)
        </p>
      </Card>

      {/* ── Session log 今日会话记录 ── */}
      {todaySessions.length > 0 && (
        <Card title="📋 今日记录">
          <div className="space-y-2">
            {todaySessions.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-[var(--color-surface)] last:border-0">
                <div className="flex items-center gap-2">
                  {/* 序号标识 */}
                  <span className="w-6 h-6 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-accent)] text-[10px] font-semibold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <span className="text-[var(--color-text-secondary)] text-xs">
                    番茄钟 #{i + 1}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                  <span>{s.minutes}分钟</span>
                  {/* 完成状态标识 */}
                  {s.completed ? (
                    <span className="text-[var(--color-success)]">✓ 完成</span>
                  ) : (
                    <span className="text-[var(--color-text-muted)]">未完成</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Tips 专注技巧提示 ── */}
      <Card title="💡 专注技巧" className="!p-5">
        <div className="space-y-2 text-xs text-[var(--color-text-secondary)] leading-relaxed">
          <p>• <b>5秒法则</b>：想做一件事时，在5秒内行动，否则大脑会找借口</p>
          <p>• <b>环境锚定</b>：固定学习位置，大脑会自动切换到"学习模式"</p>
          <p>• <b>单任务</b>：一次只做一件事，切换任务损失20%效率</p>
          <p>• <b>结束仪式</b>：学习结束后花2分钟简单复盘，加深记忆</p>
        </div>
      </Card>
    </div>
  );
}
