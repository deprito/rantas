'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { BrandImpactedStats } from '@/types/stats';

interface BrandImpactedChartProps {
  data: BrandImpactedStats | null;
  isLoading: boolean;
}

const BRAND_COLORS = [
  '#3b82f6', // blue
  '#ef4444', // red
  '#22c55e', // green
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#84cc16', // lime
  '#f97316', // orange
  '#6366f1', // indigo
];

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      brand: string;
      case_count: number;
      resolved_count: number;
      failed_count: number;
      resolution_rate: number;
    };
  }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3">
        <p className="font-medium">{data.brand}</p>
        <p className="text-sm text-muted-foreground">
          Cases: <span className="font-medium">{data.case_count}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Resolved: <span className="font-medium text-green-600">{data.resolved_count}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Failed: <span className="font-medium text-red-600">{data.failed_count}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          Resolution Rate: <span className="font-medium">{data.resolution_rate.toFixed(1)}%</span>
        </p>
      </div>
    );
  }
  return null;
}

export function BrandImpactedChart({ data, isLoading }: BrandImpactedChartProps) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px]">
        <h3 className="text-lg font-semibold mb-4">Cases by Brand Impacted</h3>
        <div className="flex items-center justify-center h-[280px]">
          <div className="w-full h-48 bg-slate-200 dark:bg-slate-700 animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (!data || data.brands.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px]">
        <h3 className="text-lg font-semibold mb-4">Cases by Brand Impacted</h3>
        <div className="flex flex-col items-center justify-center h-[280px] text-muted-foreground">
          <p>No brand data available</p>
          <p className="text-sm mt-2">Select a brand when sending reports to see statistics</p>
        </div>
      </div>
    );
  }

  const chartData = useMemo(
    () => data.brands.map((item, index) => ({
      ...item,
      fill: BRAND_COLORS[index % BRAND_COLORS.length],
    })),
    [data.brands]
  );

  const totalCases = data.total_cases_with_brand + data.total_cases_without_brand;
  const percentageWithBrand = totalCases > 0
    ? ((data.total_cases_with_brand / totalCases) * 100).toFixed(1)
    : 0;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4 h-[350px]">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">Cases by Brand Impacted</h3>
          <p className="text-sm text-muted-foreground mt-1">
            {data.total_cases_with_brand} cases ({percentageWithBrand}% of total)
          </p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-700" />
          <XAxis type="number" className="text-xs" />
          <YAxis
            dataKey="brand"
            type="category"
            width={80}
            className="text-xs"
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="case_count" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
