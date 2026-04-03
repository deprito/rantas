'use client';

import { useState, useCallback, useMemo } from 'react';
import { Calendar, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DateRangeFilter as DateRangeFilterType } from '@/types/stats';

interface DateRangeFilterProps {
  dateRange: DateRangeFilterType;
  onDateRangeChange: (range: DateRangeFilterType) => void;
}

type PresetRange = 'today' | 'week' | 'month' | 'quarter' | 'year' | 'all';

// Helper function outside component to avoid recreation on every render
function getPresetRange(preset: PresetRange): DateRangeFilterType {
  const now = new Date();
  const today = now.toISOString().split('T')[0];

  switch (preset) {
    case 'today': {
      return { startDate: today, endDate: today };
    }
    case 'week': {
      const weekAgo = new Date(now);
      weekAgo.setDate(weekAgo.getDate() - 7);
      return { startDate: weekAgo.toISOString().split('T')[0], endDate: today };
    }
    case 'month': {
      const monthAgo = new Date(now);
      monthAgo.setMonth(monthAgo.getMonth() - 1);
      return { startDate: monthAgo.toISOString().split('T')[0], endDate: today };
    }
    case 'quarter': {
      const quarterAgo = new Date(now);
      quarterAgo.setMonth(quarterAgo.getMonth() - 3);
      return { startDate: quarterAgo.toISOString().split('T')[0], endDate: today };
    }
    case 'year': {
      const yearAgo = new Date(now);
      yearAgo.setFullYear(yearAgo.getFullYear() - 1);
      return { startDate: yearAgo.toISOString().split('T')[0], endDate: today };
    }
    case 'all':
    default:
      return { startDate: null, endDate: null };
  }
}

export function DateRangeFilter({ dateRange, onDateRangeChange }: DateRangeFilterProps) {
  const [showCustom, setShowCustom] = useState(false);
  const [customStart, setCustomStart] = useState(dateRange.startDate || '');
  const [customEnd, setCustomEnd] = useState(dateRange.endDate || '');

  // Memoize the active filter check to avoid recalculation on every render
  const hasActiveFilter = useMemo(
    () => dateRange.startDate !== null || dateRange.endDate !== null,
    [dateRange.startDate, dateRange.endDate]
  );

  // Memoize preset check function
  const isActive = useCallback(
    (preset: PresetRange): boolean => {
      const presetRange = getPresetRange(preset);
      return presetRange.startDate === dateRange.startDate && presetRange.endDate === dateRange.endDate;
    },
    [dateRange.startDate, dateRange.endDate]
  );

  // Memoize event handlers to prevent child re-renders
  const handlePresetClick = useCallback(
    (preset: PresetRange) => {
      setShowCustom(false);
      onDateRangeChange(getPresetRange(preset));
    },
    [onDateRangeChange]
  );

  const handleCustomApply = useCallback(() => {
    onDateRangeChange({
      startDate: customStart || null,
      endDate: customEnd || null,
    });
    setShowCustom(false);
  }, [customStart, customEnd, onDateRangeChange]);

  const handleClearFilter = useCallback(() => {
    onDateRangeChange({ startDate: null, endDate: null });
    setCustomStart('');
    setCustomEnd('');
    setShowCustom(false);
  }, [onDateRangeChange]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
        {(['all', 'today', 'week', 'month', 'quarter', 'year'] as PresetRange[]).map((preset) => (
          <button
            key={preset}
            onClick={() => handlePresetClick(preset)}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              isActive(preset)
                ? 'bg-white dark:bg-slate-700 shadow-sm font-medium'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {preset === 'all' ? 'All Time' : preset.charAt(0).toUpperCase() + preset.slice(1)}
          </button>
        ))}
        <button
          onClick={() => setShowCustom(!showCustom)}
          className={`px-3 py-1 text-sm rounded-md transition-colors flex items-center gap-1 ${
            showCustom || (hasActiveFilter && !isActive('all') && !isActive('today') && !isActive('week') && !isActive('month') && !isActive('quarter') && !isActive('year'))
              ? 'bg-white dark:bg-slate-700 shadow-sm font-medium'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <Calendar className="h-3 w-3" />
          Custom
        </button>
      </div>

      {hasActiveFilter && (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClearFilter}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear
        </Button>
      )}

      {showCustom && (
        <div className="flex items-center gap-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-2">
          <input
            type="date"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            className="px-2 py-1 text-sm border border-slate-200 dark:border-slate-700 rounded bg-transparent"
          />
          <span className="text-muted-foreground">to</span>
          <input
            type="date"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            className="px-2 py-1 text-sm border border-slate-200 dark:border-slate-700 rounded bg-transparent"
          />
          <Button size="sm" onClick={handleCustomApply}>
            Apply
          </Button>
        </div>
      )}
    </div>
  );
}
