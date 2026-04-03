'use client';

import { UserStatsResponse } from '@/types/stats';
import { Trophy, Mail, Shield, Globe } from 'lucide-react';

interface UserLeaderboardProps {
  data: UserStatsResponse | null;
  isLoading: boolean;
}

export function UserLeaderboard({ data, isLoading }: UserLeaderboardProps) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Trophy className="h-5 w-5 text-amber-500" />
          User Leaderboard
        </h3>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-14 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.users.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Trophy className="h-5 w-5 text-amber-500" />
          User Leaderboard
        </h3>
        <div className="text-center py-8 text-muted-foreground">
          No user statistics available
        </div>
      </div>
    );
  }

  const getResolutionColor = (rate: number): string => {
    if (rate >= 80) return 'text-green-600';
    if (rate >= 50) return 'text-amber-600';
    return 'text-red-600';
  };

  const getResolutionBgColor = (rate: number): string => {
    if (rate >= 80) return 'bg-green-100 dark:bg-green-900/30';
    if (rate >= 50) return 'bg-amber-100 dark:bg-amber-900/30';
    return 'bg-red-100 dark:bg-red-900/30';
  };

  const getRankBadge = (rank: number): string => {
    if (rank === 1) return 'text-amber-500';
    if (rank === 2) return 'text-slate-400';
    if (rank === 3) return 'text-amber-700';
    return 'text-muted-foreground';
  };

  const getRankIcon = (rank: number): string => {
    if (rank === 1) return '';
    if (rank === 2) return '';
    if (rank === 3) return '';
    return `#${rank}`;
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Trophy className="h-5 w-5 text-amber-500" />
        User Leaderboard
        <span className="text-sm font-normal text-muted-foreground ml-auto">
          {data.total} {data.total === 1 ? 'contributor' : 'contributors'}
        </span>
      </h3>

      {/* Mobile Card View */}
      <div className="sm:hidden space-y-2">
        {data.users.map((user, index) => (
          <div
            key={user.user_id}
            className="bg-muted/30 rounded-lg p-3 border border-slate-100 dark:border-slate-800"
          >
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-lg font-bold ${getRankBadge(index + 1)} w-6`}>
                {index === 0 ? '' : index === 1 ? '' : index === 2 ? '' : `#${index + 1}`}
              </span>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate" title={user.username}>
                  {user.username}
                </div>
                <div className="text-xs text-muted-foreground truncate flex items-center gap-1">
                  <Mail className="h-3 w-3" />
                  {user.email}
                </div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold">{user.total_cases}</div>
                <div className="text-xs text-muted-foreground">cases</div>
              </div>
            </div>

            {/* Source breakdown */}
            <div className="flex gap-2 mb-2">
              <div className="flex items-center gap-1 text-xs">
                <Shield className="h-3 w-3 text-blue-500" />
                <span className="text-muted-foreground">Internal:</span>
                <span className="font-medium">{user.internal_cases}</span>
              </div>
              <div className="flex items-center gap-1 text-xs">
                <Globe className="h-3 w-3 text-green-500" />
                <span className="text-muted-foreground">Public:</span>
                <span className="font-medium">{user.public_cases}</span>
              </div>
            </div>

            {/* Resolution rate bar */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  {user.resolved_count} resolved / {user.failed_count} failed
                </span>
                <span className={`font-medium ${getResolutionColor(user.resolution_rate)}`}>
                  {user.resolution_rate.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full ${getResolutionBgColor(user.resolution_rate)} transition-all`}
                  style={{ width: `${user.resolution_rate}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop Table View */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700">
              <th className="text-left py-2 px-2 font-medium text-muted-foreground w-12">Rank</th>
              <th className="text-left py-2 px-2 font-medium text-muted-foreground">User</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Total</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Internal</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Public</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Resolved</th>
              <th className="text-center py-2 px-2 font-medium text-muted-foreground">Failed</th>
              <th className="text-right py-2 px-2 font-medium text-muted-foreground w-32">Resolution Rate</th>
            </tr>
          </thead>
          <tbody>
            {data.users.map((user, index) => (
              <tr
                key={user.user_id}
                className={`border-b border-slate-100 dark:border-slate-800 ${
                  index % 2 === 0 ? 'bg-slate-50/50 dark:bg-slate-800/20' : ''
                }`}
              >
                <td className={`py-2 px-2 font-bold ${getRankBadge(index + 1)}`}>
                  {index < 3 ? ['🥇', '🥈', '🥉'][index] : `#${index + 1}`}
                </td>
                <td className="py-2 px-2">
                  <div className="font-medium" title={user.username}>
                    {user.username}
                  </div>
                  <div className="text-xs text-muted-foreground truncate max-w-[180px]" title={user.email}>
                    {user.email}
                  </div>
                </td>
                <td className="py-2 px-2 text-center font-bold">{user.total_cases}</td>
                <td className="py-2 px-2 text-center">
                  <span className="flex items-center justify-center gap-1">
                    <Shield className="h-3 w-3 text-blue-500" />
                    {user.internal_cases}
                  </span>
                </td>
                <td className="py-2 px-2 text-center">
                  <span className="flex items-center justify-center gap-1">
                    <Globe className="h-3 w-3 text-green-500" />
                    {user.public_cases}
                  </span>
                </td>
                <td className="py-2 px-2 text-center text-green-600">{user.resolved_count}</td>
                <td className="py-2 px-2 text-center text-red-600">{user.failed_count}</td>
                <td className="py-2 px-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${getResolutionBgColor(user.resolution_rate)} transition-all`}
                        style={{ width: `${user.resolution_rate}%` }}
                      />
                    </div>
                    <span className={`text-xs font-medium ${getResolutionColor(user.resolution_rate)}`}>
                      {user.resolution_rate.toFixed(0)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
