'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Play, Pause, RotateCcw, Timer, Coffee, Flame, TrendingUp, Clock, Zap, Brain, Target } from 'lucide-react';
import Card from '@/components/ui/Card';

// ── Constants ──
const POMODORO_WORK = 25 * 60;
const POMODORO_BREAK = 5 * 60;

type Phase = 'work' | 'break';

interface SessionLog {
  date: string;
  minutes: number;
  completed: boolean;
}

export function StudyTab() {
  const [seconds, setSeconds] = useState(POMODORO_WORK);
  const [isRunning, setIsRunning] = useState(false);
  const [phase, setPhase] = useState<Phase>('work');
  const [todaySessions, setTodaySessions] = useState<SessionLog[]>([]);
  const [streak, setStreak] = useState(0);
  const [todayMinutes, setTodayMinutes] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // ── Load today's sessions from localStorage ──
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    const stored = localStorage.getItem(`study-sessions-${today}`);
    if (stored) {
      const sessions: SessionLog[] = JSON.parse(stored);
      setTodaySessions(sessions);
      setTodayMinutes(sessions.reduce((s, l) => s + l.minutes, 0));
    }
    const streakVal = parseInt(localStorage.getItem('study-streak') || '0', 10);
    setStreak(streakVal);
  }, []);

  // ── Timer logic ──
  const tick = useCallback(() => {
    setSeconds((prev) => {
      if (prev <= 1) {
        // Timer done — switch phase
        if (phase === 'work') {
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
          return POMODORO_BREAK;
        } else {
          setPhase('work');
          return POMODORO_WORK;
        }
      }
      return prev - 1;
    });
  }, [phase, todaySessions]);

  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(tick, 1000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isRunning, tick]);

  const toggleTimer = () => setIsRunning((r) => !r);
  const resetTimer = () => {
    setIsRunning(false);
    setSeconds(phase === 'work' ? POMODORO_WORK : POMODORO_BREAK);
  };

  // ── Format ──
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

  const workSessions = todaySessions.length;
  const goalSessions = 6; // 6×25 = 150 min/day

  return (
    <div className="max-w-3xl mx-auto space-y-8 py-4">
      {/* ── Timer ── */}
      <Card className="!p-8 text-center">
        <div className="inline-flex items-center gap-2 text-xs text-[var(--color-text-muted)] uppercase tracking-widest mb-4">
          {phase === 'work' ? (
            <><Brain size={14} className="text-[var(--color-accent)]" /> 专注学习</>
          ) : (
            <><Coffee size={14} className="text-[var(--color-success)]" /> 休息一下</>
          )}
        </div>

        <div className="text-7xl font-bold text-[var(--color-text)] tabular-nums tracking-tight mb-8"
          style={{ fontVariantNumeric: 'tabular-nums' }}>
          {timeStr}
        </div>

        <div className="flex items-center justify-center gap-3">
          <button
            onClick={toggleTimer}
            className="inline-flex items-center gap-2 px-6 py-3 text-sm font-semibold bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
            style={{ borderRadius: '2px' }}
          >
            {isRunning ? <><Pause size={16} /> 暂停</> : <><Play size={16} /> 开始</>}
          </button>
          <button
            onClick={resetTimer}
            className="inline-flex items-center gap-2 px-4 py-3 text-sm text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-surface)] transition-colors"
            style={{ borderRadius: '2px' }}
          >
            <RotateCcw size={14} /> 重置
          </button>
        </div>

        {phase === 'work' && (
          <p className="text-xs text-[var(--color-text-muted)] mt-4">
            番茄钟 · {POMODORO_WORK / 60}分钟专注 → {POMODORO_BREAK / 60}分钟休息
          </p>
        )}
      </Card>

      {/* ── Today stats ── */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="!p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Flame size={18} className="text-[var(--color-warning)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--color-text)]">{streak}</div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">连续天数</div>
        </Card>

        <Card className="!p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Timer size={18} className="text-[var(--color-accent)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--color-text)]">{todayMinutes}</div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">今日分钟</div>
        </Card>

        <Card className="!p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Target size={18} className="text-[var(--color-success)]" />
          </div>
          <div className="text-2xl font-bold text-[var(--color-text)]">
            {workSessions}<span className="text-sm text-[var(--color-text-muted)]">/{goalSessions}</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">完成番茄</div>
        </Card>
      </div>

      {/* ── Progress bar ── */}
      <Card className="!p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-[var(--color-text)]">
            🍅 今日进度
          </span>
          <span className="text-xs text-[var(--color-text-muted)]">
            {Math.round((workSessions / goalSessions) * 100)}%
          </span>
        </div>
        <div className="h-2 bg-[var(--color-surface)] overflow-hidden">
          <div
            className="h-full bg-[var(--color-accent)] transition-all duration-700"
            style={{ width: `${Math.min((workSessions / goalSessions) * 100, 100)}%` }}
          />
        </div>
        <p className="text-[10px] text-[var(--color-text-muted)] mt-3">
          目标：每天 {goalSessions} 个番茄钟 ({goalSessions * POMODORO_WORK / 60} 分钟)
        </p>
      </Card>

      {/* ── Session log ── */}
      {todaySessions.length > 0 && (
        <Card title="📋 今日记录">
          <div className="space-y-2">
            {todaySessions.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-[var(--color-surface)] last:border-0">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-accent)] text-[10px] font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <span className="text-[var(--color-text-secondary)] text-xs">
                    番茄钟 #{i + 1}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                  <span>{s.minutes}分钟</span>
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

      {/* ── Tips ── */}
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
