'use client';

import { StatsOverview } from '@/types/stats';
import { Card } from '@/components/ui/card';
import { CardContent } from '@/components/ui/card';
import {
  Briefcase,
  Activity,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Mail,
  Users,
  Globe2,
  Inbox,
  Tag,
  AlertCircle,
} from 'lucide-react';
import Link from 'next/link';

interface StatsCardsProps {
  data: StatsOverview | null;
  isLoading: boolean;
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: 'blue' | 'green' | 'red' | 'amber' | 'purple' | 'cyan' | 'slate';
  isLoading?: boolean;
  href?: string;
}

const colorClasses = {
  blue: 'bg-blue-50 text-blue-600 border-blue-200',
  green: 'bg-green-50 text-green-600 border-green-200',
  red: 'bg-red-50 text-red-600 border-red-200',
  amber: 'bg-amber-50 text-amber-600 border-amber-200',
  purple: 'bg-purple-50 text-purple-600 border-purple-200',
  cyan: 'bg-cyan-50 text-cyan-600 border-cyan-200',
  slate: 'bg-slate-50 text-slate-600 border-slate-200',
};

const iconBgClasses = {
  blue: 'bg-blue-100',
  green: 'bg-green-100',
  red: 'bg-red-100',
  amber: 'bg-amber-100',
  purple: 'bg-purple-100',
  cyan: 'bg-cyan-100',
  slate: 'bg-slate-100',
};

function StatCard({ title, value, subtitle, icon, color, isLoading, href }: StatCardProps) {
  const cardContent = (
    <div className={`rounded-lg border p-4 ${colorClasses[color]} ${href ? 'hover:opacity-80 transition-opacity cursor-pointer' : ''}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium opacity-80">{title}</p>
          {isLoading ? (
            <div className="h-8 w-16 bg-current opacity-20 rounded animate-pulse mt-1" />
          ) : (
            <p className="text-2xl font-bold">{value}</p>
          )}
          {subtitle && !isLoading && (
            <p className="text-xs opacity-60 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`p-3 rounded-full ${iconBgClasses[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  );

  if (href) {
    return <Link href={href}>{cardContent}</Link>;
  }

  return cardContent;
}

export function StatsCards({ data, isLoading }: StatsCardsProps) {
  const formatHours = (hours: number | null): string => {
    if (hours === null) return 'N/A';
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    return `${(hours / 24).toFixed(1)}d`;
  };

  return (
    <div className="space-y-4">
      {/* Main Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          title="Total Cases"
          value={data?.total_cases ?? 0}
          subtitle={data?.cases_created_today ? `+${data.cases_created_today} today` : undefined}
          icon={<Briefcase className="h-5 w-5" />}
          color="blue"
          isLoading={isLoading}
        />
        <StatCard
          title="Active Cases"
          value={data?.active_cases ?? 0}
          icon={<Activity className="h-5 w-5" />}
          color="amber"
          isLoading={isLoading}
        />
        <StatCard
          title="Resolved"
          value={data?.resolved_cases ?? 0}
          subtitle={data?.cases_resolved_today ? `+${data.cases_resolved_today} today` : undefined}
          icon={<CheckCircle2 className="h-5 w-5" />}
          color="green"
          isLoading={isLoading}
        />
        <StatCard
          title="Failed"
          value={data?.failed_cases ?? 0}
          icon={<XCircle className="h-5 w-5" />}
          color="red"
          isLoading={isLoading}
        />
        <StatCard
          title="Success Rate"
          value={data ? `${data.success_rate.toFixed(1)}%` : '0%'}
          icon={<TrendingUp className="h-5 w-5" />}
          color="purple"
          isLoading={isLoading}
        />
        <StatCard
          title="Emails Sent"
          value={data?.total_emails_sent ?? 0}
          subtitle={data?.average_resolution_time_hours
            ? `Avg: ${formatHours(data.average_resolution_time_hours)}`
            : undefined}
          icon={<Mail className="h-5 w-5" />}
          color="cyan"
          isLoading={isLoading}
        />
      </div>

      {/* Source Breakdown Row */}
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-medium mb-3 text-muted-foreground">Case Source Breakdown</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              title="Internal Cases"
              value={data?.internal_cases ?? 0}
              subtitle="Created by team members"
              icon={<Users className="h-5 w-5" />}
              color="slate"
              isLoading={isLoading}
            />
            <StatCard
              title="Public Cases"
              value={data?.public_cases ?? 0}
              subtitle="From public submissions"
              icon={<Globe2 className="h-5 w-5" />}
              color="purple"
              isLoading={isLoading}
            />
            <StatCard
              title="Pending Submissions"
              value={data?.pending_submissions ?? 0}
              subtitle="Awaiting review"
              icon={<Inbox className="h-5 w-5" />}
              color="amber"
              isLoading={isLoading}
              href="/admin?tab=submissions"
            />
          </div>
        </CardContent>
      </Card>

      {/* Brand Impacted Breakdown Row */}
      {(data?.total_cases_with_brand ?? 0) > 0 && (
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium mb-3 text-muted-foreground">Brand Impacted Statistics</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard
                title="Cases with Brand"
                value={data?.total_cases_with_brand ?? 0}
                subtitle={`${((data?.total_cases_with_brand ?? 0) / ((data?.total_cases_with_brand ?? 0) + (data?.total_cases_without_brand ?? 0)) * 100).toFixed(1)}% of total`}
                icon={<Tag className="h-5 w-5" />}
                color="blue"
                isLoading={isLoading}
              />
              <StatCard
                title="Cases without Brand"
                value={data?.total_cases_without_brand ?? 0}
                subtitle="Brand not specified"
                icon={<AlertCircle className="h-5 w-5" />}
                color="slate"
                isLoading={isLoading}
              />
              <StatCard
                title="Top Brands"
                value={data?.top_brands?.length ?? 0}
                subtitle={data?.top_brands?.slice(0, 3).join(', ') || 'No brands yet'}
                icon={<Tag className="h-5 w-5" />}
                color="green"
                isLoading={isLoading}
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
