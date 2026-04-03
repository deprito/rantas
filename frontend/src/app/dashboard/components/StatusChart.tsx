'use client';

import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { StatusDistribution, STATUS_COLORS, STATUS_LABELS } from '@/types/stats';

interface StatusChartProps {
  data: StatusDistribution | null;
  isLoading: boolean;
}

// CustomTooltip component defined outside to avoid recreation
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: { name: string; value: number; percentage: number } }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3">
        <p className="font-medium">{data.name}</p>
        <p className="text-sm text-muted-foreground">
          Count: <span className="font-medium">{data.value}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Percentage: <span className="font-medium">{data.percentage.toFixed(1)}%</span>
        </p>
      </div>
    );
  }
  return null;
}

export function StatusChart({ data, isLoading }: StatusChartProps) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px]">
        <h3 className="text-lg font-semibold mb-4">Status Distribution</h3>
        <div className="flex items-center justify-center h-[280px]">
          <div className="w-48 h-48 rounded-full bg-slate-200 dark:bg-slate-700 animate-pulse" />
        </div>
      </div>
    );
  }

  if (!data || data.distribution.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px]">
        <h3 className="text-lg font-semibold mb-4">Status Distribution</h3>
        <div className="flex items-center justify-center h-[280px] text-muted-foreground">
          No data available
        </div>
      </div>
    );
  }

  // Memoize chart data to avoid recalculation on every render
  const chartData = useMemo(
    () => data.distribution.map((item) => ({
      name: STATUS_LABELS[item.status] || item.status,
      value: item.count,
      percentage: item.percentage,
      fill: STATUS_COLORS[item.status] || '#94a3b8',
    })),
    [data.distribution]
  );

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px] fade-in">
      <h3 className="text-lg font-semibold mb-4">Status Distribution</h3>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
            label={({ name, percentage }) => `${name}: ${percentage.toFixed(0)}%`}
            labelLine={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value: string) => (
              <span className="text-sm text-slate-600 dark:text-slate-400">{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
