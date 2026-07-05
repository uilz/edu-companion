"use client";

/**
 * 本地权重查看 — 不发送到服务端
 * 依据 docs/modules/interest-explorer/overview.md §7.4 + ADR 0007 决策 10
 */
import { useEffect, useState, useCallback } from "react";
import {
  ChevronLeft, Scale, RefreshCw, Loader2, AlertCircle,
  Trash2, Info, TrendingDown,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  interestService, InterestWeightAdjustment, InterestSamplingWeight,
} from "@/lib/api/interest-api";

export default function WeightPage() {
  const router = useRouter();
  const [data, setData] = useState<{
    adjustments: InterestWeightAdjustment[];
    sampling_weights: InterestSamplingWeight[];
    principle: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await interestService.getWeightAdjustments();
      setData(r);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onReset = async () => {
    if (!confirm("确定清空所有本地权重？恢复默认")) return;
    setBusy(true);
    try {
      await interestService.resetWeights();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
      await load();
    } catch (e: any) {
      setError(e.message || "重置失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Scale className="w-6 h-6 text-blue-500" />
            本地权重
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            不感兴趣反馈仅本地调整采样概率 · 不发送到服务端
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/interest")}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50"
          >
            返回
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 flex items-center gap-1"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={onReset}
            disabled={busy}
            className="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50 flex items-center gap-1"
          >
            <Trash2 className="w-4 h-4" />
            清空
          </button>
        </div>
      </div>

      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-2 text-sm text-blue-800">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <div>
          <p className="font-medium">本地权重原则</p>
          <p className="text-xs mt-0.5 text-blue-700">
            {data?.principle || "local_only_not_sent_to_server"}。
            每次标记"不感兴趣"时，对应标签 dislike_score += 0.1（最高 1.0）。
            采样时 effective_weight = base_weight * (1 - dislike_score)。
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          清空成功
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400">
          <Loader2 className="w-8 h-8 mx-auto animate-spin" />
        </div>
      ) : !data ? null : (
        <>
          <div className="mb-6 border rounded-lg p-4 bg-white">
            <h2 className="font-medium text-sm mb-3 flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-red-500" />
              标签 dislike 调整 ({data.adjustments.length})
            </h2>
            {data.adjustments.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-4">
                暂无 dislike 记录
              </p>
            ) : (
              <div className="space-y-2">
                {data.adjustments.map((adj) => (
                  <div
                    key={adj.id}
                    className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                          L{adj.tag_level}
                        </span>
                        <span className="font-medium text-sm">
                          {adj.tag_name || "(标签已删除)"}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">
                        累计 {adj.adjustment_count} 次不感兴趣
                      </p>
                    </div>
                    <div className="w-32">
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-red-500"
                          style={{ width: `${adj.dislike_score * 100}%` }}
                        />
                      </div>
                      <p className="text-xs text-right text-gray-500 mt-0.5">
                        {(adj.dislike_score * 100).toFixed(0)}%
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border rounded-lg p-4 bg-white">
            <h2 className="font-medium text-sm mb-3">
              当前采样权重 ({data.sampling_weights.length})
            </h2>
            {data.sampling_weights.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-4">
                暂无采样权重（请先配置兴趣标签）
              </p>
            ) : (
              <div className="space-y-2">
                {data.sampling_weights
                  .sort((a, b) => b.effective_weight - a.effective_weight)
                  .map((sw) => (
                  <div
                    key={sw.tag_id}
                    className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                          L{sw.level}
                        </span>
                        <span className="font-medium text-sm">
                          {sw.tag_name || "(标签已删除)"}
                        </span>
                      </div>
                    </div>
                    <div className="w-32">
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500"
                          style={{
                            width: `${Math.min(100, sw.effective_weight * 100)}%`,
                          }}
                        />
                      </div>
                      <p className="text-xs text-right text-gray-500 mt-0.5">
                        {sw.effective_weight.toFixed(2)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
