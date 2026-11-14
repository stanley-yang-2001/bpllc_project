import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { rewardsKey } from "../api/keys";
import { useActiveLanguage } from "../auth/ActiveLanguage";
import { useAuth } from "../auth/AuthContext";

/** The streak, goal, week and badges for the active language. A failure just means "show nothing": rewards never block a page. */
export function useRewards() {
  const { user } = useAuth();
  const { active } = useActiveLanguage();
  return useQuery({ queryKey: rewardsKey(user!.id, active), queryFn: () => api.rewards(active), staleTime: 30_000, retry: false });
}
