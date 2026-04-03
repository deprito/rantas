'use client';

import { EmailEffectiveness } from '@/types/stats';
import { Mail, Send, CheckCircle, Percent } from 'lucide-react';

interface EmailMetricsCardProps {
  data: EmailEffectiveness | null;
  isLoading: boolean;
}

export function EmailMetricsCard({ data, isLoading }: EmailMetricsCardProps) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Mail className="h-5 w-5 text-orange-500" />
          Email Effectiveness
        </h3>
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Mail className="h-5 w-5 text-orange-500" />
          Email Effectiveness
        </h3>
        <div className="text-center py-8 text-muted-foreground">
          No email data available
        </div>
      </div>
    );
  }

  const metrics = [
    {
      label: 'Total Emails Sent',
      value: data.total_emails_sent,
      icon: <Send className="h-4 w-4 text-orange-500" />,
    },
    {
      label: 'Cases with Emails',
      value: data.cases_with_emails,
      icon: <Mail className="h-4 w-4 text-blue-500" />,
    },
    {
      label: 'Avg Emails per Case',
      value: data.avg_emails_per_case.toFixed(1),
      icon: <Percent className="h-4 w-4 text-purple-500" />,
    },
    {
      label: 'Resolved After Email',
      value: data.cases_resolved_after_email,
      icon: <CheckCircle className="h-4 w-4 text-green-500" />,
    },
  ];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Mail className="h-5 w-5 text-orange-500" />
        Email Effectiveness
      </h3>
      <div className="space-y-3">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-800 last:border-0"
          >
            <div className="flex items-center gap-2">
              {metric.icon}
              <span className="text-sm text-muted-foreground">{metric.label}</span>
            </div>
            <span className="font-semibold">{metric.value}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Email Success Rate</span>
          <span className={`text-lg font-bold ${
            data.email_success_rate >= 70 ? 'text-green-600' :
            data.email_success_rate >= 40 ? 'text-amber-600' : 'text-red-600'
          }`}>
            {data.email_success_rate.toFixed(1)}%
          </span>
        </div>
        <div className="mt-2 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              data.email_success_rate >= 70 ? 'bg-green-500' :
              data.email_success_rate >= 40 ? 'bg-amber-500' : 'bg-red-500'
            }`}
            style={{ width: `${Math.min(data.email_success_rate, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
