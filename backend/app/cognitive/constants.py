"""全局可学习参数默认值（每个学生一份）"""

DEFAULT_PARAMS = {
    # 激活/遗忘
    "student.decay_factor": 0.5,
    "student.mastery_gate": 0.85,
    "student.retrieval_sigma": 0.3,
    "student.min_pseudo_count": 1.0,
    "student.diagnostic_precision": 10.0,

    # 调度
    "student.sched_retention_weight": 0.3,
    "student.sched_mastery_push_weight": 0.5,
    "student.sched_interleaving_weight": 0.6,
    "student.sched_core_boost": 0.2,
    "student.sched_stagnation_penalty": 0.15,

    # 疲劳
    "student.fatigue_decay_lambda": 0.1,
    "student.fatigue_increment_eta": 0.2,

    # 趋势
    "student.velocity_decay_lambda": 0.5,

    # 事件权重
    "event_weight.practice_response": 1.0,
    "event_weight.diagnostic_result": 1.5,
    "event_weight.conversation_assessment": 0.5,
    "event_weight.material_view": 0.1,
}

# 节点初始值
INITIAL_BELIEF_ALPHA = 2.0
INITIAL_BELIEF_BETA = 2.0
INITIAL_PEAK_PROFICIENCY = 0.5
INITIAL_RETRIEVAL_PROB = 0.5
INITIAL_LATENCY_MS = 5000

# 快速重学参数
RAPID_RELEARN_WEIGHT_MULTIPLIER = 2.0
RAPID_RELEARN_COOLDOWN_DAYS = 365
RAPID_RELEARN_PEAK_THRESHOLD = 0.95
RAPID_RELEARN_CURRENT_THRESHOLD = 0.8
RAPID_RELEARN_LATENCY_MAX = 3000
RAPID_RELEARN_LATENCY_FACTOR = 1.5

# 趋势参数
TREND_VELOCITY_EMA_ALPHA = 0.1
TREND_VELOCITY_DECAY_LAMBDA = 0.5  # 对应 params["student.velocity_decay_lambda"]
TREND_STAGNATION_THRESHOLD = 0.005
TREND_VOLATILITY_THRESHOLD = 0.05
TREND_HISTORY_MAX = 7

# 聚合参数
AGGREGATION_K = 1.0  # 调和指数

# 对话上下文
MAX_DIALOGUE_CONTEXTS = 5
CONTEXT_HISTORY_MAX = 20
SESSION_TIMEOUT_HOURS = 1
FATIGUE_SESSION_DIVISOR = 30  # practice_count / 30 → session load

# 练习历史
MAX_PRACTICE_EVENTS = 50
PRACTICE_EVENT_MAX = 50

# 调度
SCHED_URGENCY_MAX = 1.0
SCHED_NEXT_REVIEW_DEFAULT_DAYS = 7
SCHED_INTERLEAVING_GROUP = "default"

# 冷却
RAPID_RELEARN_COOLDOWN_SECONDS = 365 * 86400

# Chunk形成
CHUNK_MIN_CO_OCCURRENCE = 10
CHUNK_MIN_AUTO_PROB = 0.8
CHUNK_CONSECUTIVE_SESSIONS = 5

# 诊断
DIAGNOSTIC_CACHE_TTL_SECONDS = 3600

# 下降检测
DECLINE_THRESHOLD = 0.05
DECLINE_DANGER_THRESHOLD = 0.6
