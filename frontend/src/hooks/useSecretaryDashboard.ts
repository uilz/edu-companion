import { useApiQuery } from "./useApiQuery";
import {
  secretaryDashboardApi,
  type SecretaryDashboardData,
} from "@/lib/api/secretary-dashboard-api";

const QUERY_KEY = "secretary-dashboard";

/**
 * 查询秘书仪表盘聚合数据
 *
 * 用法：
 *   const { data, loading, error, refetch } = useSecretaryDashboard();
 */
export function useSecretaryDashboard() {
  return useApiQuery<SecretaryDashboardData>(
    [QUERY_KEY],
    () => secretaryDashboardApi.getDashboard(),
    {
      staleTime: 30_000,
      refetchInterval: 60_000,
    },
  );
}
