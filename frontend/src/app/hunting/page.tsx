'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import {
  DetectedDomain,
  DetectedDomainStatus,
  DetectedDomainListResponse,
  HuntingStats,
  HuntingStatus,
  detectedDomainStatusLabels,
  detectedDomainStatusColors,
} from '@/types/case';
import { api, ApiError } from '@/lib/api';
import {
  Radar,
  Shield,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
  Trash2,
  Plus,
  ChevronLeft,
  ChevronRight,
  Filter,
  Power,
  Activity,
  Clock,
  Database,
  Terminal,
  FileJson,
  Settings,
  X,
  Tag,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  HuntingStatusSkeleton,
  HuntingStatsSkeleton,
  HuntingFiltersSkeleton,
  CertPatrolStreamSkeleton,
} from '@/components/skeleton';

const PAGE_SIZE = 20;

// HTTP Status Code Labels
const httpStatusLabel = (code: number | null | undefined): string => {
  if (code === null || code === undefined) return 'Not Checked';
  const labels: Record<number, string> = {
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Info',
    204: 'No Content',
    206: 'Partial Content',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    407: 'Proxy Auth Required',
    408: 'Request Timeout',
    410: 'Gone',
    429: 'Too Many Requests',
    500: 'Internal Server Error',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
  };
  return labels[code] || `HTTP ${code}`;
};

const httpStatusColor = (code: number | null | undefined): string => {
  if (code === null || code === undefined) return 'border-gray-400 text-gray-500';
  if (code >= 200 && code < 300) return 'border-green-500 text-green-700 dark:text-green-400';
  if (code >= 300 && code < 400) return 'border-blue-500 text-blue-700 dark:text-blue-400';
  if (code >= 400 && code < 500) return 'border-orange-500 text-orange-700 dark:text-orange-400';
  if (code >= 500) return 'border-red-500 text-red-700 dark:text-red-400';
  return 'border-gray-400 text-gray-500';
};

interface CertPatrolEntry {
  cert_index: number;
  data_type: string;
  update_type: string;
  all_domains: string[];
  seen_at: string;
}

function HuntingContent() {
  const router = useRouter();
  const { hasPermission } = useAuth();

  const [domains, setDomains] = useState<DetectedDomain[]>([]);
  const [stats, setStats] = useState<HuntingStats | null>(null);
  const [status, setStatus] = useState<HuntingStatus | null>(null);
  const [rawStream, setRawStream] = useState<CertPatrolEntry[]>([]);

  // Progressive loading states
  const [isLoadingDomains, setIsLoadingDomains] = useState(true);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const rawStreamContainerRef = useRef<HTMLDivElement>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [brandFilter, setBrandFilter] = useState<string>('');
  const [httpStatusFilter, setHttpStatusFilter] = useState<number | undefined>();
  const [minScoreFilter, setMinScoreFilter] = useState<number | undefined>();

  // Configuration dialog state
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [huntingConfig, setHuntingConfig] = useState<{
    monitor_enabled: boolean;
    min_score_threshold: number;
    alert_threshold: number;
    monitored_brands: string[];
    retention_days: number;
    raw_log_retention_days: number;
    custom_brand_patterns: Record<string, string[]>;
    custom_brand_regex_patterns: Record<string, string[]>;
  } | null>(null);
  const [newBrandName, setNewBrandName] = useState('');
  const [newBrandPatterns, setNewBrandPatterns] = useState('');
  const [newBrandRegexPatterns, setNewBrandRegexPatterns] = useState('');
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  // Editing state for inline editing
  const [editingBrand, setEditingBrand] = useState<{brand: string, newName: string} | null>(null);
  const [editingPattern, setEditingPattern] = useState<{brand: string, oldPattern: string, newPattern: string} | null>(null);
  const [newPatternsForBrand, setNewPatternsForBrand] = useState<Record<string, string>>({});

  // Editing state for regex patterns
  const [editingRegexBrand, setEditingRegexBrand] = useState<{brand: string, newName: string} | null>(null);
  const [editingRegexPattern, setEditingRegexPattern] = useState<{brand: string, oldPattern: string, newPattern: string} | null>(null);
  const [newRegexPatternsForBrand, setNewRegexPatternsForBrand] = useState<Record<string, string>>({});

  // Permission checks
  const canViewHunting = hasPermission(Permission.HUNTING_VIEW);
  const canUpdateHunting = hasPermission(Permission.HUNTING_UPDATE);
  const canDeleteHunting = hasPermission(Permission.HUNTING_DELETE);

  const loadStats = useCallback(async () => {
    setIsLoadingStats(true);
    try {
      const data = await api.getHuntingStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load hunting stats:', err);
    } finally {
      setIsLoadingStats(false);
    }
  }, []);

  const loadStatus = useCallback(async () => {
    setIsLoadingStatus(true);
    try {
      const data = await api.getHuntingStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to load hunting status:', err);
    } finally {
      setIsLoadingStatus(false);
    }
  }, []);

  const loadRawStream = useCallback(async () => {
    try {
      const data = await api.getRawCertStream(20);
      setRawStream(data.entries || []);
    } catch (err) {
      console.error('Failed to load raw stream:', err);
    }
  }, []);

  // Set up SSE for real-time CertPatrol raw stream
  useEffect(() => {
    if (!canViewHunting) return;

    // Get the base URL from environment or use current origin
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
    let apiUrl = apiBaseUrl.startsWith('http')
      ? `${apiBaseUrl}/hunting/certpatrol-stream`
      : `${window.location.protocol}//${window.location.hostname}:8000/api/hunting/certpatrol-stream`;

    // EventSource doesn't support custom headers, so we pass the token as a query parameter
    // The backend has a special auth dependency that checks both header and query param
    const token = localStorage.getItem('phishtrack_token');
    console.log('[SSE] Token from localStorage:', token ? `${token.substring(0, 20)}...` : 'null');
    if (token) {
      apiUrl += `?token=${encodeURIComponent(token)}`;
    }

    console.log('[SSE] Connecting to:', apiUrl);
    const eventSource = new EventSource(apiUrl);

    eventSource.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data);
        setRawStream(prev => {
          // Keep only last 50 entries to prevent memory issues
          const updated = [...prev, entry];
          if (updated.length > 50) {
            return updated.slice(-50);
          }
          return updated;
        });
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.addEventListener('ready', (event) => {
      console.log('CertPatrol SSE stream is live');
    });

    eventSource.onerror = (error) => {
      console.error('[SSE] CertPatrol SSE connection error:', error);
      console.error('[SSE] EventSource readyState:', eventSource.readyState);
      // EventSource will automatically try to reconnect
    };

    return () => {
      eventSource.close();
    };
  }, [canViewHunting]);

  const loadDomains = useCallback(async (silent = false) => {
    if (!silent) setIsLoadingDomains(true);
    setError(null);

    try {
      const response = await api.getDetectedDomains({
        page: currentPage,
        page_size: PAGE_SIZE,
        status: statusFilter || undefined,
        brand_filter: brandFilter || undefined,
        http_status_filter: httpStatusFilter,
        min_score: minScoreFilter,
      });

      setDomains(response.domains);
      setTotalPages(Math.ceil(response.total / PAGE_SIZE));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setDomains([]);
        setTotalPages(1);
      } else {
        console.error('Failed to load detected domains:', err);
        if (!silent) {
          setError(err instanceof Error ? err.message : 'Failed to load detected domains');
        }
      }
    } finally {
      if (!silent) {
        setIsLoadingDomains(false);
      }
    }
  }, [currentPage, statusFilter, brandFilter, httpStatusFilter, minScoreFilter]);

  // Load data on mount
  useEffect(() => {
    if (canViewHunting) {
      loadStats();
      loadStatus();
      loadDomains();
    }
  }, [canViewHunting, loadDomains, loadStats, loadStatus]);

  // Auto-refresh status and stats every 30 seconds
  // Raw stream uses SSE for real-time updates
  useEffect(() => {
    if (!canViewHunting) return;

    const interval = setInterval(() => {
      loadStatus();
      loadStats();
      loadDomains(true); // Silent refresh to get new alerts
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [canViewHunting, loadStatus, loadStats, loadDomains]);

  // Auto-scroll raw stream to bottom when new entries arrive
  useEffect(() => {
    if (rawStreamContainerRef.current) {
      rawStreamContainerRef.current.scrollTop = rawStreamContainerRef.current.scrollHeight;
    }
  }, [rawStream]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([loadStats(), loadDomains(true), loadStatus()]);
    setTimeout(() => setIsRefreshing(false), 500);
  }, [loadStats, loadDomains, loadStatus]);

  const handleToggle = useCallback(async () => {
    setIsToggling(true);
    try {
      const newStatus = await api.toggleHuntingMonitor();
      setStatus(newStatus);
      // Don't wait for loadStatus - it can be slow
      // Status will be updated via SSE stream and auto-refresh
    } catch (err) {
      console.error('Failed to toggle monitor:', err);
      setError(err instanceof Error ? err.message : 'Failed to toggle monitor');
      // Refresh status to get actual state
      await loadStatus();
    } finally {
      setIsToggling(false);
    }
  }, [loadStatus]);

  const handleStatusChange = async (domainId: string, newStatus: DetectedDomainStatus) => {
    try {
      await api.updateDetectedDomain(domainId, { status: newStatus });
      await loadDomains(true);
      await loadStats();
    } catch (err) {
      console.error('Failed to update domain status:', err);
      setError(err instanceof Error ? err.message : 'Failed to update status');
    }
  };

  const handleCreateCase = async (domainId: string) => {
    try {
      await api.createCaseFromDetection(domainId);
      await loadDomains(true);
      await loadStats();
    } catch (err) {
      console.error('Failed to create case:', err);
      setError(err instanceof Error ? err.message : 'Failed to create case');
    }
  };

  const handleDelete = async (domainId: string) => {
    if (!confirm('Are you sure you want to delete this detected domain?')) {
      return;
    }
    try {
      await api.deleteDetectedDomain(domainId);
      await loadDomains(true);
      await loadStats();
    } catch (err) {
      console.error('Failed to delete domain:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete domain');
    }
  };

  const clearFilters = () => {
    setStatusFilter('');
    setBrandFilter('');
    setHttpStatusFilter(undefined);
    setMinScoreFilter(undefined);
    setCurrentPage(1);
  };

  const loadConfig = useCallback(async () => {
    try {
      const config = await api.getHuntingConfig();
      setHuntingConfig(config);
    } catch (err) {
      console.error('Failed to load hunting config:', err);
    }
  }, []);

  const saveConfig = useCallback(async (newConfig: typeof huntingConfig) => {
    if (!newConfig) return;
    setIsSavingConfig(true);
    try {
      const updated = await api.updateHuntingConfig({
        custom_brand_patterns: newConfig.custom_brand_patterns,
        custom_brand_regex_patterns: newConfig.custom_brand_regex_patterns,
        raw_log_retention_days: newConfig.raw_log_retention_days,
      });
      setHuntingConfig(updated);
    } catch (err) {
      console.error('Failed to save hunting config:', err);
      setError(err instanceof Error ? err.message : 'Failed to save config');
    } finally {
      setIsSavingConfig(false);
    }
  }, []);

  const addCustomBrand = () => {
    if (!newBrandName.trim() || !newBrandPatterns.trim()) return;

    const patterns = newBrandPatterns
      .split(',')
      .map(p => p.trim().toLowerCase())
      .filter(p => p.length > 0);

    if (patterns.length === 0) return;

    setHuntingConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        custom_brand_patterns: {
          ...prev.custom_brand_patterns,
          [newBrandName.toLowerCase()]: patterns,
        },
      };
    });

    setNewBrandName('');
    setNewBrandPatterns('');
  };

  const removeCustomBrand = (brand: string) => {
    setHuntingConfig(prev => {
      if (!prev) return prev;
      const newPatterns = { ...prev.custom_brand_patterns };
      delete newPatterns[brand];
      return {
        ...prev,
        custom_brand_patterns: newPatterns,
      };
    });
  };

  const addPatternToBrand = (brand: string, pattern: string) => {
    if (!pattern.trim()) return;
    setHuntingConfig(prev => {
      if (!prev) return prev;
      const existingPatterns = prev.custom_brand_patterns[brand] || [];
      if (!existingPatterns.includes(pattern.toLowerCase())) {
        return {
          ...prev,
          custom_brand_patterns: {
            ...prev.custom_brand_patterns,
            [brand]: [...existingPatterns, pattern.toLowerCase()],
          },
        };
      }
      return prev;
    });
  };

  const removePatternFromBrand = (brand: string, pattern: string) => {
    setHuntingConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        custom_brand_patterns: {
          ...prev.custom_brand_patterns,
          [brand]: prev.custom_brand_patterns[brand]?.filter(p => p !== pattern) || [],
        },
      };
    });
  };

  // Regex pattern handling functions
  const addCustomBrandWithRegex = () => {
    if (!newBrandName.trim()) return;

    const regexPatterns = newBrandRegexPatterns
      .split('\n')
      .map(p => p.trim())
      .filter(p => p.length > 0);

    setHuntingConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        custom_brand_regex_patterns: {
          ...prev.custom_brand_regex_patterns,
          [newBrandName.toLowerCase()]: regexPatterns,
        },
      };
    });

    setNewBrandName('');
    setNewBrandRegexPatterns('');
  };

  const removeCustomRegexBrand = (brand: string) => {
    setHuntingConfig(prev => {
      if (!prev) return prev;
      const newRegexPatterns = { ...prev.custom_brand_regex_patterns };
      delete newRegexPatterns[brand];
      return {
        ...prev,
        custom_brand_regex_patterns: newRegexPatterns,
      };
    });
  };

  const addRegexPatternToBrand = (brand: string, pattern: string) => {
    if (!pattern.trim()) return;
    setHuntingConfig(prev => {
      if (!prev) return prev;
      const existingPatterns = prev.custom_brand_regex_patterns[brand] || [];
      if (!existingPatterns.includes(pattern)) {
        return {
          ...prev,
          custom_brand_regex_patterns: {
            ...prev.custom_brand_regex_patterns,
            [brand]: [...existingPatterns, pattern],
          },
        };
      }
      return prev;
    });
  };

  const removeRegexPatternFromBrand = (brand: string, pattern: string) => {
    setHuntingConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        custom_brand_regex_patterns: {
          ...prev.custom_brand_regex_patterns,
          [brand]: prev.custom_brand_regex_patterns[brand]?.filter(p => p !== pattern) || [],
        },
      };
    });
  };

  // Brand name editing functions
  const startEditBrand = (brand: string) => setEditingBrand({brand, newName: brand});
  const saveEditBrand = () => {
    if (!editingBrand || !huntingConfig) return;
    const {brand, newName} = editingBrand;
    if (!newName.trim()) {
      setEditingBrand(null);
      return;
    }
    const patterns = huntingConfig.custom_brand_patterns[brand];
    setHuntingConfig(prev => {
      if (!prev) return prev;
      const newPatterns = {...prev.custom_brand_patterns};
      delete newPatterns[brand];
      return {
        ...prev,
        custom_brand_patterns: {
          ...newPatterns,
          [newName.toLowerCase()]: patterns,
        },
      };
    });
    setEditingBrand(null);
  };
  const cancelEditBrand = () => setEditingBrand(null);

  // Pattern editing functions
  const startEditPattern = (brand: string, pattern: string) => setEditingPattern({brand, oldPattern: pattern, newPattern: pattern});
  const saveEditPattern = () => {
    if (!editingPattern || !huntingConfig) return;
    const {brand, oldPattern, newPattern} = editingPattern;
    if (!newPattern.trim()) {
      setEditingPattern(null);
      return;
    }
    setHuntingConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        custom_brand_patterns: {
          ...prev.custom_brand_patterns,
          [brand]: prev.custom_brand_patterns[brand]?.map(p => p === oldPattern ? newPattern.toLowerCase() : p) || [],
        },
      };
    });
    setEditingPattern(null);
  };
  const cancelEditPattern = () => setEditingPattern(null);

  // Quick-add pattern to existing brand
  const addPatternToBrandInline = (brand: string) => {
    const newPattern = newPatternsForBrand[brand];
    if (newPattern?.trim()) {
      addPatternToBrand(brand, newPattern);
      setNewPatternsForBrand(prev => ({...prev, [brand]: ''}));
    }
  };

  // Regex brand name editing functions
  const startEditRegexBrand = (brand: string) => setEditingRegexBrand({brand, newName: brand});
  const saveEditRegexBrand = () => {
    if (!editingRegexBrand || !huntingConfig) return;
    const {brand, newName} = editingRegexBrand;
    if (!newName.trim()) {
      setEditingRegexBrand(null);
      return;
    }
    const patterns = huntingConfig.custom_brand_regex_patterns[brand];
    setHuntingConfig(prev => {
      if (!prev) return prev;
      const newPatterns = {...prev.custom_brand_regex_patterns};
      delete newPatterns[brand];
      return {
        ...prev,
        custom_brand_regex_patterns: {
          ...newPatterns,
          [newName.toLowerCase()]: patterns,
        },
      };
    });
    setEditingRegexBrand(null);
  };
  const cancelEditRegexBrand = () => setEditingRegexBrand(null);

  // Regex pattern editing functions
  const startEditRegexPattern = (brand: string, pattern: string) => setEditingRegexPattern({brand, oldPattern: pattern, newPattern: pattern});
  const saveEditRegexPattern = () => {
    if (!editingRegexPattern || !huntingConfig) return;
    const {brand, oldPattern, newPattern} = editingRegexPattern;
    if (!newPattern.trim()) {
      setEditingRegexPattern(null);
      return;
    }
    setHuntingConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        custom_brand_regex_patterns: {
          ...prev.custom_brand_regex_patterns,
          [brand]: prev.custom_brand_regex_patterns[brand]?.map(p => p === oldPattern ? newPattern : p) || [],
        },
      };
    });
    setEditingRegexPattern(null);
  };
  const cancelEditRegexPattern = () => setEditingRegexPattern(null);

  // Quick-add regex pattern to existing brand
  const addRegexPatternToBrandInline = (brand: string) => {
    const newPattern = newRegexPatternsForBrand[brand];
    if (newPattern?.trim()) {
      addRegexPatternToBrand(brand, newPattern);
      setNewRegexPatternsForBrand(prev => ({...prev, [brand]: ''}));
    }
  };

  // Format time ago
  const formatTimeAgo = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  // Get score color
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-red-600 bg-red-50 dark:bg-red-950/30';
    if (score >= 80) return 'text-orange-600 bg-orange-50 dark:bg-orange-950/30';
    if (score >= 70) return 'text-yellow-600 bg-yellow-50 dark:bg-yellow-950/30';
    return 'text-blue-600 bg-blue-50 dark:bg-blue-950/30';
  };

  if (!canViewHunting) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
        <div className="container mx-auto px-4 py-8">
          <Card className="p-8 text-center">
            <AlertTriangle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
            <p className="text-muted-foreground">
              You don't have permission to access the Hunting feature.
            </p>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <header className="border-b bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-3 sm:px-4 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-primary/10 p-2 rounded-lg">
                <Radar className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Hunting</h1>
                <p className="text-xs text-muted-foreground">
                  Typosquat Detection via CertPatrol (CT Logs)
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={isRefreshing}>
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              </Button>
              {canUpdateHunting && (
                <Button variant="outline" size="sm" onClick={() => { loadConfig(); setConfigDialogOpen(true); }}>
                  <Settings className="h-4 w-4 mr-2" />
                  Config
                </Button>
              )}
              <Link href="/">
                <Button variant="outline" size="sm">
                  <Shield className="h-4 w-4 mr-2" />
                  Dashboard
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column (2/3) - Detected Domains */}
          <div className="lg:col-span-2 space-y-6">
            {/* Error Display */}
        {error && (
          <div className="mb-6 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg">
            <p className="font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Error
            </p>
            <p className="text-sm mt-1">{error}</p>
          </div>
        )}

        {/* Monitor Status Card */}
        {isLoadingStatus ? (
          <HuntingStatusSkeleton />
        ) : status && (
          <Card className={`p-4 mb-6 border-l-4 fade-in ${
            status.monitor_is_running
              ? 'border-l-green-500 bg-green-50/50 dark:bg-green-950/20'
              : 'border-l-gray-400 bg-gray-50/50 dark:bg-gray-950/20'
          }`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className={`h-4 w-4 ${status.monitor_is_running ? 'text-green-600 animate-pulse' : 'text-gray-400'}`} />
                  <span className="font-semibold text-sm">
                    Monitor Status: {status.monitor_is_running ? (
                      <span className="text-green-600">Running</span>
                    ) : (
                      <span className="text-gray-600">Stopped</span>
                    )}
                  </span>
                  {status.error_message && (
                    <span className="text-xs text-red-600 ml-2">
                      (Error: {status.error_message.slice(0, 50)}...)
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Database className="h-3 w-3" />
                    <span>Certs: {status.certificates_processed.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Radar className="h-3 w-3" />
                    <span>Detected: {status.domains_detected}</span>
                  </div>
                  {status.monitor_last_heartbeat && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>Heartbeat: {formatTimeAgo(status.monitor_last_heartbeat)}</span>
                    </div>
                  )}
                  {status.monitor_started_at && status.monitor_is_running && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>Uptime: {formatTimeAgo(status.monitor_started_at)}</span>
                    </div>
                  )}
                </div>
              </div>
              <Button
                variant={status.monitor_is_running ? "destructive" : "default"}
                size="sm"
                onClick={handleToggle}
                disabled={isToggling}
                className="gap-1 shrink-0"
              >
                <Power className={`h-4 w-4 ${isToggling ? 'animate-pulse' : ''}`} />
                {isToggling ? 'Toggling...' : status.monitor_is_running ? 'Stop' : 'Start'}
              </Button>
            </div>
          </Card>
        )}

        {/* Statistics Cards */}
        {isLoadingStats ? (
          <HuntingStatsSkeleton />
        ) : stats && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6 fade-in">
            <Card className="p-4">
              <div className="text-2xl font-bold">{stats.total_detected}</div>
              <div className="text-xs text-muted-foreground">Total Detected</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
              <div className="text-xs text-muted-foreground">Pending Review</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-blue-600">{stats.reviewed}</div>
              <div className="text-xs text-muted-foreground">Reviewed</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-green-600">{stats.cases_created}</div>
              <div className="text-xs text-muted-foreground">Cases Created</div>
            </Card>
            <Card className="p-4">
              <div className="text-2xl font-bold text-red-600">{stats.high_confidence}</div>
              <div className="text-xs text-muted-foreground">High Confidence</div>
            </Card>
          </div>
        )}

        {/* Filters */}
        {isLoadingDomains && !stats ? (
          <HuntingFiltersSkeleton />
        ) : (
        <Card className="p-4 mb-6">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Filters:</span>
            </div>

            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
              className="px-3 py-1.5 text-sm border rounded-md bg-background"
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="reviewed">Reviewed</option>
              <option value="ignored">Ignored</option>
              <option value="case_created">Case Created</option>
            </select>

            <select
              value={brandFilter}
              onChange={(e) => { setBrandFilter(e.target.value); setCurrentPage(1); }}
              className="px-3 py-1.5 text-sm border rounded-md bg-background"
            >
              <option value="">All Brands</option>
              {stats?.top_brands.map((brand) => (
                <option key={brand} value={brand}>{brand.toUpperCase()}</option>
              ))}
            </select>

            <select
              value={minScoreFilter ?? ''}
              onChange={(e) => { setMinScoreFilter(e.target.value ? Number(e.target.value) : undefined); setCurrentPage(1); }}
              className="px-3 py-1.5 text-sm border rounded-md bg-background"
            >
              <option value="">All Scores</option>
              <option value="80">High (80+)</option>
              <option value="70">Medium (70+)</option>
              <option value="50">Low (50+)</option>
            </select>

            <select
              value={httpStatusFilter ?? ''}
              onChange={(e) => { setHttpStatusFilter(e.target.value ? Number(e.target.value) : undefined); setCurrentPage(1); }}
              className="px-3 py-1.5 text-sm border rounded-md bg-background"
            >
              <option value="">All Status Codes</option>
              <option value="200">200 (OK)</option>
              <option value="301">301 (Redirect)</option>
              <option value="302">302 (Found)</option>
              <option value="404">404 (Not Found)</option>
              <option value="500">500 (Server Error)</option>
              <option value="null">Not Checked</option>
            </select>

            {(statusFilter || brandFilter || httpStatusFilter !== undefined || minScoreFilter) && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear
              </Button>
            )}
          </div>
        </Card>
        )}

        {/* Detected Domains List */}
        {isLoadingDomains && domains.length === 0 ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-accent/5 border border-accent/20 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="h-6 w-48 bg-accent/50 rounded animate-pulse" />
                      <div className="h-6 w-20 bg-accent/50 rounded animate-pulse" />
                      <div className="h-6 w-24 bg-accent/50 rounded animate-pulse" />
                    </div>
                    <div className="h-4 w-64 bg-accent/50 rounded animate-pulse mb-1" />
                    <div className="h-4 w-32 bg-accent/50 rounded animate-pulse" />
                  </div>
                  <div className="flex gap-2">
                    <div className="h-8 w-16 bg-accent/50 rounded animate-pulse" />
                    <div className="h-8 w-20 bg-accent/50 rounded animate-pulse" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : domains.length === 0 ? (
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-muted rounded-full mb-4">
              <Radar className="h-8 w-8 text-muted-foreground" />
            </div>
            <h2 className="text-xl font-semibold mb-2">No Detected Domains</h2>
            <p className="text-muted-foreground max-w-md mx-auto">
              {statusFilter || brandFilter || minScoreFilter
                ? 'No domains match the current filters. Try clearing the filters to see all detections.'
                : 'CertPatrol monitor is running. Typosquat domains will appear here as they are detected.'}
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              {domains.map((domain) => (
                <Card key={domain.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <h3 className="font-semibold text-lg truncate">{domain.domain}</h3>
                        <Badge className={`shrink-0 ${getScoreColor(domain.detection_score)}`}>
                          Score: {domain.detection_score}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={`shrink-0 ${
                            domain.status === 'pending'
                              ? 'border-yellow-500 text-yellow-700'
                              : domain.status === 'case_created'
                                ? 'border-green-500 text-green-700'
                                : ''
                          }`}
                        >
                          {detectedDomainStatusLabels[domain.status]}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={`shrink-0 ${httpStatusColor(domain.http_status_code)}`}
                        >
                          {httpStatusLabel(domain.http_status_code)}
                        </Badge>
                      </div>

                      <div className="text-sm text-muted-foreground space-y-1">
                        {domain.matched_brand && (
                          <div>
                            Matched: <span className="font-semibold text-foreground">{domain.matched_brand.toUpperCase()}</span>
                            {domain.matched_pattern && (
                              <span> - {domain.matched_pattern}</span>
                            )}
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          <span>Seen: {formatTimeAgo(domain.cert_seen_at)}</span>
                          {domain.cert_data.cert_index && (
                            <span className="text-xs">• Cert ID: {domain.cert_data.cert_index?.toString().slice(0, 8)}...</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 flex-wrap">
                      {domain.status === 'pending' && canUpdateHunting && (
                        <>
                          {hasPermission(Permission.CASE_CREATE) && domain.case_id === null && (
                            <Button
                              size="sm"
                              variant="default"
                              onClick={() => handleCreateCase(domain.id)}
                              className="gap-1"
                            >
                              <Plus className="h-3 w-3" />
                              Case
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleStatusChange(domain.id, 'reviewed')}
                            className="gap-1"
                          >
                            <Eye className="h-3 w-3" />
                            Review
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleStatusChange(domain.id, 'ignored')}
                            className="gap-1 text-muted-foreground"
                          >
                            <XCircle className="h-3 w-3" />
                            Ignore
                          </Button>
                        </>
                      )}

                      {domain.status === 'reviewed' && canUpdateHunting && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleStatusChange(domain.id, 'pending')}
                          className="gap-1"
                        >
                          Reopen
                        </Button>
                      )}

                      {domain.case_id && (
                        <Link href={`/?case=${domain.case_id}`}>
                          <Button size="sm" variant="outline" className="gap-1">
                            <CheckCircle2 className="h-3 w-3" />
                            View Case
                          </Button>
                        </Link>
                      )}

                      {canDeleteHunting && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDelete(domain.id)}
                          className="gap-1 text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>

                <span className="text-sm text-muted-foreground">
                  Page {currentPage} of {totalPages}
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
            )}
          </div>

          {/* Right Column (1/3) - CertPatrol Output */}
          <div className="space-y-6">
            {/* CertPatrol Stream */}
            {isLoadingStatus && !status ? (
              <CertPatrolStreamSkeleton />
            ) : (
              <>
              {/* CertPatrol Header */}
              <Card className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-primary" />
                  <span className="font-semibold text-sm">CertPatrol (CT Logs)</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className={`h-2 w-2 rounded-full ${status?.monitor_is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                  <span className="text-xs text-muted-foreground">
                    {rawStream.length} entries
                  </span>
                </div>
              </div>
            </Card>

            {/* CertPatrol Raw Output */}
            <Card className="p-0 overflow-hidden">
              <div ref={rawStreamContainerRef} className="bg-slate-950 text-slate-50 p-3 font-mono text-xs h-[calc(100vh-350px)] overflow-y-auto" id="raw-stream">
                {rawStream.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-slate-500">
                    <FileJson className="h-8 w-8 mb-2 opacity-50" />
                    <p>Waiting for CertPatrol data...</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {rawStream.map((entry, idx) => (
                      <div key={idx} className="border-b border-slate-800 pb-2 last:border-0">
                        <div className="flex items-center gap-2 text-slate-400 mb-1">
                          <span className="text-xs">#{entry.cert_index}</span>
                          <span className="text-xs">{entry.update_type}</span>
                          <span className="text-xs ml-auto">{new Date(entry.seen_at).toLocaleTimeString()}</span>
                        </div>
                        <div className="text-slate-300">
                          {entry.all_domains.map((domain, i) => (
                            <span key={i} className="inline-block mr-2">
                              {i > 0 && <span className="text-slate-600">•</span>}
                              <span className="text-cyan-400">{domain}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
            </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm mt-16">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          <p>
            RANTAS Hunting - Powered by CertPatrol
          </p>
          <p className="mt-1 text-xs">
            Monitoring SSL certificate transparency logs (CT Logs) for typosquat domains
          </p>
        </div>
      </footer>

      {/* Configuration Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Hunting Configuration
            </DialogTitle>
            <DialogDescription>
              Configure custom brand patterns for typosquat detection. These patterns will override the default patterns for each brand.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 mt-4">
            {/* Raw Log Retention Setting */}
            <div className="border rounded-lg p-4 bg-muted/30">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Database className="h-4 w-4" />
                Raw Log Retention
              </h3>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="raw-log-retention">Raw Log Retention (Days)</Label>
                  <Input
                    id="raw-log-retention"
                    type="number"
                    min="1"
                    max="30"
                    value={huntingConfig?.raw_log_retention_days ?? 3}
                    onChange={(e) => setHuntingConfig(prev => prev ? {
                      ...prev,
                      raw_log_retention_days: Number(e.target.value)
                    } : null)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Days to keep raw CT log entries in Redis (default: 3). Raw logs are cleaned up hourly.
                  </p>
                </div>
              </div>
            </div>

            {/* Add new brand pattern */}
            <div className="border rounded-lg p-4 bg-muted/30">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Plus className="h-4 w-4" />
                Add Custom Brand Patterns
              </h3>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="brand-name">Brand Name</Label>
                  <Input
                    id="brand-name"
                    placeholder="e.g., example"
                    value={newBrandName}
                    onChange={(e) => setNewBrandName(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="brand-patterns">Patterns (comma-separated)</Label>
                  <Input
                    id="brand-patterns"
                    placeholder="e.g., example, examplee, exxample"
                    value={newBrandPatterns}
                    onChange={(e) => setNewBrandPatterns(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Enter typosquat patterns separated by commas. These will be matched against domain names.
                  </p>
                </div>
                <Button onClick={addCustomBrand} disabled={!newBrandName.trim() || !newBrandPatterns.trim()}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Brand
                </Button>
              </div>
            </div>

            {/* Existing custom patterns */}
            {huntingConfig && Object.keys(huntingConfig.custom_brand_patterns || {}).length > 0 ? (
              <div className="space-y-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  Custom Brand Patterns
                </h3>
                {Object.entries(huntingConfig.custom_brand_patterns || {}).map(([brand, patterns]) => (
                  <div key={brand} className="border rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      {editingBrand?.brand === brand ? (
                        <Input
                          value={editingBrand.newName}
                          onChange={(e) => setEditingBrand(prev => prev ? {...prev, newName: e.target.value} : null)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveEditBrand();
                            if (e.key === 'Escape') cancelEditBrand();
                          }}
                          onBlur={saveEditBrand}
                          className="h-7 text-sm font-medium uppercase"
                          autoFocus
                        />
                      ) : (
                        <span
                          className="font-medium text-sm uppercase cursor-pointer hover:bg-muted px-1 rounded"
                          onClick={() => startEditBrand(brand)}
                          title="Click to edit brand name"
                        >
                          {brand}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeCustomBrand(brand)}
                        className="h-6 w-6 p-0 text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {patterns.map((pattern) => {
                        const isEditing = editingPattern?.brand === brand && editingPattern?.oldPattern === pattern;
                        if (isEditing) {
                          return (
                            <Input
                              key={pattern}
                              value={editingPattern.newPattern}
                              onChange={(e) => setEditingPattern(prev => prev ? {...prev, newPattern: e.target.value} : null)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') saveEditPattern();
                                if (e.key === 'Escape') cancelEditPattern();
                              }}
                              onBlur={saveEditPattern}
                              className="h-7 text-xs font-mono w-32"
                              autoFocus
                            />
                          );
                        }
                        return (
                          <Badge
                            key={pattern}
                            variant="secondary"
                            className="text-xs cursor-pointer hover:bg-accent"
                            onClick={() => startEditPattern(brand, pattern)}
                            title="Click to edit pattern"
                          >
                            {pattern}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                removePatternFromBrand(brand, pattern);
                              }}
                              className="ml-1 hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        );
                      })}
                    </div>
                    <div className="flex gap-2 mt-2">
                      <Input
                        placeholder="Add pattern..."
                        value={newPatternsForBrand[brand] || ''}
                        onChange={(e) => setNewPatternsForBrand(prev => ({...prev, [brand]: e.target.value}))}
                        onKeyDown={(e) => { if (e.key === 'Enter') addPatternToBrandInline(brand); }}
                        className="h-8 text-sm flex-1"
                      />
                      <Button
                        size="sm"
                        onClick={() => addPatternToBrandInline(brand)}
                        disabled={!newPatternsForBrand[brand]?.trim()}
                      >
                        Add
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Tag className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No custom brand patterns configured yet.</p>
                <p className="text-xs">Add custom patterns above to override default typosquat detection.</p>
              </div>
            )}

            {/* Regex Patterns Section */}
            <div className="border rounded-lg p-4 bg-muted/30">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Plus className="h-4 w-4" />
                Add Custom Regex Patterns
              </h3>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="regex-brand-name">Brand Name</Label>
                  <Input
                    id="regex-brand-name"
                    placeholder="e.g., example"
                    value={newBrandName}
                    onChange={(e) => setNewBrandName(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="regex-patterns">Regex Patterns (one per line)</Label>
                  <textarea
                    id="regex-patterns"
                    className="w-full min-h-[100px] p-2 text-sm border rounded-md bg-background font-mono"
                    placeholder={`e.g.,^.*example.*\\..*$\n.*test.*\\.com$\n.*test.*\\.(id|co)`}
                    value={newBrandRegexPatterns}
                    onChange={(e) => setNewBrandRegexPatterns(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Enter regex patterns (one per line). These will be matched against domain names using case-insensitive matching.
                  </p>
                </div>
                <Button onClick={addCustomBrandWithRegex} disabled={!newBrandName.trim() || !newBrandRegexPatterns.trim()}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Regex Patterns
                </Button>
              </div>
            </div>

            {/* Existing custom regex patterns */}
            {huntingConfig && Object.keys(huntingConfig.custom_brand_regex_patterns || {}).length > 0 ? (
              <div className="space-y-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  Custom Regex Patterns
                </h3>
                {Object.entries(huntingConfig.custom_brand_regex_patterns || {}).map(([brand, patterns]) => (
                  <div key={brand} className="border rounded-lg p-3 bg-blue-50/50 dark:bg-blue-950/20">
                    <div className="flex items-center justify-between mb-2">
                      {editingRegexBrand?.brand === brand ? (
                        <Input
                          value={editingRegexBrand.newName}
                          onChange={(e) => setEditingRegexBrand(prev => prev ? {...prev, newName: e.target.value} : null)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveEditRegexBrand();
                            if (e.key === 'Escape') cancelEditRegexBrand();
                          }}
                          onBlur={saveEditRegexBrand}
                          className="h-7 text-sm font-medium uppercase"
                          autoFocus
                        />
                      ) : (
                        <span
                          className="font-medium text-sm uppercase cursor-pointer hover:bg-muted px-1 rounded"
                          onClick={() => startEditRegexBrand(brand)}
                          title="Click to edit brand name"
                        >
                          {brand}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeCustomRegexBrand(brand)}
                        className="h-6 w-6 p-0 text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {patterns.map((pattern) => {
                        const isEditing = editingRegexPattern?.brand === brand && editingRegexPattern?.oldPattern === pattern;
                        if (isEditing) {
                          return (
                            <Input
                              key={pattern}
                              value={editingRegexPattern.newPattern}
                              onChange={(e) => setEditingRegexPattern(prev => prev ? {...prev, newPattern: e.target.value} : null)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') saveEditRegexPattern();
                                if (e.key === 'Escape') cancelEditRegexPattern();
                              }}
                              onBlur={saveEditRegexPattern}
                              className="h-7 text-xs font-mono w-40"
                              autoFocus
                            />
                          );
                        }
                        return (
                          <Badge
                            key={pattern}
                            variant="secondary"
                            className="text-xs font-mono cursor-pointer hover:bg-accent"
                            onClick={() => startEditRegexPattern(brand, pattern)}
                            title={pattern}
                          >
                            {pattern.length > 30 ? `${pattern.substring(0, 30)}...` : pattern}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                removeRegexPatternFromBrand(brand, pattern);
                              }}
                              className="ml-1 hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        );
                      })}
                    </div>
                    <div className="flex gap-2 mt-2">
                      <Input
                        placeholder="Add regex pattern..."
                        value={newRegexPatternsForBrand[brand] || ''}
                        onChange={(e) => setNewRegexPatternsForBrand(prev => ({...prev, [brand]: e.target.value}))}
                        onKeyDown={(e) => { if (e.key === 'Enter') addRegexPatternToBrandInline(brand); }}
                        className="h-8 text-sm font-mono flex-1"
                      />
                      <Button
                        size="sm"
                        onClick={() => addRegexPatternToBrandInline(brand)}
                        disabled={!newRegexPatternsForBrand[brand]?.trim()}
                      >
                        Add
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-4 text-muted-foreground">
                <p className="text-sm">No custom regex patterns configured yet.</p>
                <p className="text-xs">Regex patterns provide more flexible matching than substring patterns.</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-4 border-t">
              <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  saveConfig(huntingConfig);
                  setConfigDialogOpen(false);
                }}
                disabled={isSavingConfig}
              >
                {isSavingConfig ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Wrap with ProtectedRoute
export default function HuntingPage() {
  return (
    <ProtectedRoute>
      <HuntingContent />
    </ProtectedRoute>
  );
}
