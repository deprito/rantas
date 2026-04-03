'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api, PublicSubmission } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Inbox,
  RefreshCw,
  Check,
  X,
  Eye,
  Trash2,
  AlertCircle,
  ExternalLink,
  Mail,
  Clock,
  FileText,
  CheckCircle,
  XCircle,
  Layers,
} from 'lucide-react';
import Link from 'next/link';

const POLL_INTERVAL = 30000; // 30 seconds

// Helper functions defined outside component to avoid recreation on every render
function getAgeColor(submittedAt: string): string {
  const hours = (Date.now() - new Date(submittedAt).getTime()) / 36e5;
  if (hours > 24) return 'text-red-500';
  if (hours > 4) return 'text-amber-500';
  return 'text-green-500';
}

function getAgeText(submittedAt: string): string {
  const hours = (Date.now() - new Date(submittedAt).getTime()) / 36e5;
  if (hours < 1) {
    const minutes = Math.floor(hours * 60);
    return `${minutes}m ago`;
  }
  if (hours < 24) return `${Math.floor(hours)}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function getStatusBadgeColor(status: string): string {
  switch (status) {
    case 'pending':
      return 'bg-yellow-500';
    case 'approved':
      return 'bg-green-500';
    case 'rejected':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
}

function formatDate(dateString: string | null): string {
  if (!dateString) return 'N/A';
  // If the date string doesn't have timezone info, append UTC offset
  // (backend returns naive datetime strings which should be treated as UTC)
  const normalizedDate = dateString.includes('+') || dateString.includes('Z')
    ? dateString
    : dateString + '+00:00';
  return new Date(normalizedDate).toLocaleString('en-US', {
    timeZone: 'Asia/Bangkok',  // GMT+7
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}

function SubmissionsManagementContent() {
  const { hasPermission } = useAuth();

  const [submissions, setSubmissions] = useState<PublicSubmission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | ''>('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [statusCounts, setStatusCounts] = useState({
    pending: 0,
    approved: 0,
    rejected: 0,
    all: 0,
  });

  // Modal states
  const [showViewModal, setShowViewModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [selectedSubmission, setSelectedSubmission] = useState<PublicSubmission | null>(null);

  // Form states
  const [rejectReason, setRejectReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const canViewSubmissions = hasPermission(Permission.SUBMISSION_VIEW);
  const canApproveSubmissions = hasPermission(Permission.SUBMISSION_APPROVE);
  const canDeleteSubmissions = hasPermission(Permission.SUBMISSION_DELETE);

  // Computed values
  const pendingSubmissions = useMemo(
    () => submissions.filter(s => s.status === 'pending'),
    [submissions]
  );
  const hasPending = pendingSubmissions.length > 0;
  const allSelected = pendingSubmissions.length > 0 &&
    pendingSubmissions.every(s => selectedIds.has(s.id));

  const loadStatusCounts = useCallback(async () => {
    if (!canViewSubmissions) return;

    try {
      // Load counts for each status
      const [pendingRes, approvedRes, rejectedRes, allRes] = await Promise.all([
        api.listSubmissions({ status: 'pending', page: 1, page_size: 1 }),
        api.listSubmissions({ status: 'approved', page: 1, page_size: 1 }),
        api.listSubmissions({ status: 'rejected', page: 1, page_size: 1 }),
        api.listSubmissions({ page: 1, page_size: 1 }),
      ]);
      setStatusCounts({
        pending: pendingRes.total,
        approved: approvedRes.total,
        rejected: rejectedRes.total,
        all: allRes.total,
      });
    } catch (err) {
      // Silent fail for counts
      console.error('Failed to load status counts:', err);
    }
  }, [canViewSubmissions]);

  const loadSubmissions = useCallback(async () => {
    if (!canViewSubmissions) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.listSubmissions({
        status: statusFilter || undefined,
        page,
        page_size: 20,
      });
      setSubmissions(response.submissions);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load submissions');
    } finally {
      setIsLoading(false);
    }
  }, [canViewSubmissions, statusFilter, page]);

  useEffect(() => {
    loadSubmissions();
    loadStatusCounts();

    // Set up polling for real-time updates
    const interval = setInterval(() => {
      loadSubmissions();
      loadStatusCounts();
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [loadSubmissions, loadStatusCounts]);

  // Auto-hide success message
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  // Close modals on ESC key press
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showViewModal) setShowViewModal(false);
        if (showRejectModal) setShowRejectModal(false);
      }
    };

    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [showViewModal, showRejectModal]);

  const handleApprove = async (submissionId: string) => {
    if (!canApproveSubmissions) return;

    setIsProcessing(true);
    setError(null);

    try {
      const result = await api.approveSubmission(submissionId);
      setSuccess(`Submission approved. Case created: ${result.case_id}`);
      setShowViewModal(false);
      setSelectedSubmission(null);
      loadSubmissions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve submission');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!canApproveSubmissions || !selectedSubmission) return;

    setIsProcessing(true);
    setError(null);

    try {
      await api.rejectSubmission(selectedSubmission.id, { reason: rejectReason });
      setSuccess('Submission rejected');
      setShowRejectModal(false);
      setSelectedSubmission(null);
      setRejectReason('');
      loadSubmissions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject submission');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDelete = async (submissionId: string) => {
    if (!canDeleteSubmissions) return;

    if (!confirm('Are you sure you want to delete this submission?')) return;

    setIsLoading(true);
    setError(null);

    try {
      await api.deleteSubmission(submissionId);
      setSuccess('Submission deleted');
      loadSubmissions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete submission');
    } finally {
      setIsLoading(false);
    }
  };

  const openViewModal = (submission: PublicSubmission) => {
    setSelectedSubmission(submission);
    setShowViewModal(true);
  };

  const openRejectModal = (submission: PublicSubmission) => {
    setSelectedSubmission(submission);
    setShowRejectModal(true);
  };

  // Bulk selection handlers
  const toggleSelection = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingSubmissions.map(s => s.id)));
    }
  };

  const handleBulkApprove = async () => {
    if (!canApproveSubmissions || selectedIds.size === 0) return;

    setIsProcessing(true);
    setError(null);

    try {
      const approvePromises = Array.from(selectedIds).map(id =>
        api.approveSubmission(id)
      );
      await Promise.all(approvePromises);
      setSuccess(`${selectedIds.size} submission(s) approved successfully`);
      setSelectedIds(new Set());
      loadSubmissions();
      loadStatusCounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve some submissions');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkReject = async () => {
    if (!canApproveSubmissions || selectedIds.size === 0) return;

    if (!confirm(`Are you sure you want to reject ${selectedIds.size} submission(s)?`)) return;

    setIsProcessing(true);
    setError(null);

    try {
      const rejectPromises = Array.from(selectedIds).map(id =>
        api.rejectSubmission(id, { reason: 'Bulk rejected' })
      );
      await Promise.all(rejectPromises);
      setSuccess(`${selectedIds.size} submission(s) rejected`);
      setSelectedIds(new Set());
      loadSubmissions();
      loadStatusCounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject some submissions');
    } finally {
      setIsProcessing(false);
    }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Inbox className="h-6 w-6" />
            Public Submissions
          </h2>
          <p className="text-muted-foreground mt-1">
            Review and approve public URL submissions
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { loadSubmissions(); loadStatusCounts(); }} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Link href="/public/submit" target="_blank">
            <Button variant="outline">
              <ExternalLink className="h-4 w-4 mr-2" />
              Public Form
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-amber-600 dark:text-amber-400">Pending</p>
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">{statusCounts.pending}</p>
              </div>
              <Clock className="h-8 w-8 text-amber-500/50" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-green-200 bg-green-50 dark:bg-green-950/20 dark:border-green-900">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-green-600 dark:text-green-400">Approved</p>
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">{statusCounts.approved}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-500/50" />
            </div>
          </CardContent>
        </Card>
        <Card className="border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-900">
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-red-600 dark:text-red-400">Rejected</p>
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">{statusCounts.rejected}</p>
              </div>
              <XCircle className="h-8 w-8 text-red-500/50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Total</p>
                <p className="text-2xl font-bold">{statusCounts.all}</p>
              </div>
              <Layers className="h-8 w-8 text-muted-foreground/50" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Success Display */}
      {success && (
        <div className="mb-4 bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-900 text-green-800 dark:text-green-400 p-4 rounded-lg">
          {success}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mb-4 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg">
          {error}
        </div>
      )}

      {/* Filter with counts */}
      <div className="mb-4">
        <div className="flex flex-wrap gap-2">
          <Button
            variant={statusFilter === '' ? 'default' : 'outline'}
            size="sm"
            onClick={() => { setStatusFilter(''); setPage(1); setSelectedIds(new Set()); }}
          >
            <Layers className="h-4 w-4 mr-1" />
            All ({total})
          </Button>
          <Button
            variant={statusFilter === 'pending' ? 'default' : 'outline'}
            size="sm"
            onClick={() => { setStatusFilter('pending'); setPage(1); setSelectedIds(new Set()); }}
          >
            <Clock className="h-4 w-4 mr-1" />
            Pending
            {submissions.filter(s => s.status === 'pending').length > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                {submissions.filter(s => s.status === 'pending').length}
              </Badge>
            )}
          </Button>
          <Button
            variant={statusFilter === 'approved' ? 'default' : 'outline'}
            size="sm"
            onClick={() => { setStatusFilter('approved'); setPage(1); setSelectedIds(new Set()); }}
          >
            <CheckCircle className="h-4 w-4 mr-1" />
            Approved
            {submissions.filter(s => s.status === 'approved').length > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                {submissions.filter(s => s.status === 'approved').length}
              </Badge>
            )}
          </Button>
          <Button
            variant={statusFilter === 'rejected' ? 'default' : 'outline'}
            size="sm"
            onClick={() => { setStatusFilter('rejected'); setPage(1); setSelectedIds(new Set()); }}
          >
            <XCircle className="h-4 w-4 mr-1" />
            Rejected
            {submissions.filter(s => s.status === 'rejected').length > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                {submissions.filter(s => s.status === 'rejected').length}
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden space-y-4">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin" />
          </div>
        ) : submissions.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <div className="flex flex-col items-center gap-3 text-center">
                <Inbox className="h-12 w-12 text-muted-foreground/50" />
                <div>
                  <p className="text-lg font-medium">No submissions found</p>
                  <p className="text-sm text-muted-foreground">
                    {statusFilter === 'pending'
                      ? 'No pending submissions to review'
                      : 'Share the public form to start receiving submissions'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          submissions.map((submission) => (
            <Card key={submission.id} className={selectedIds.has(submission.id) ? 'ring-2 ring-primary' : ''}>
              <CardContent className="p-4">
                <div className="space-y-3">
                  {/* Header with checkbox and status */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {canApproveSubmissions && submission.status === 'pending' && (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(submission.id)}
                          onChange={() => toggleSelection(submission.id)}
                          className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                      )}
                      {submission.status === 'pending' ? (
                        <div className="flex items-center gap-2">
                          <span className="relative flex h-2.5 w-2.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
                          </span>
                          <Badge variant="outline" className="text-amber-600 border-amber-300">
                            Pending
                          </Badge>
                        </div>
                      ) : submission.status === 'approved' ? (
                        <Badge variant="outline" className="text-green-600 border-green-300">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          Approved
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-red-600 border-red-300">
                          <XCircle className="h-3 w-3 mr-1" />
                          Rejected
                        </Badge>
                      )}
                    </div>
                    {submission.status === 'pending' && (
                      <span className={`text-xs font-medium ${getAgeColor(submission.submitted_at)}`}>
                        {getAgeText(submission.submitted_at)}
                      </span>
                    )}
                  </div>

                  {/* URL */}
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">URL</p>
                    <p className="font-mono text-sm break-all bg-muted/50 p-2 rounded">
                      {submission.url}
                    </p>
                  </div>

                  {/* Submitter info */}
                  <div className="flex flex-wrap gap-4 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Submitter</p>
                      <p className="flex items-center gap-1">
                        {submission.submitter_email ? (
                          <>
                            <Mail className="h-3 w-3 text-muted-foreground" />
                            {submission.submitter_email}
                          </>
                        ) : (
                          <span className="text-muted-foreground">Anonymous</span>
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Submitted</p>
                      <p className="flex items-center gap-1">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        {formatDate(submission.submitted_at)}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openViewModal(submission)}
                      className="flex-1"
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      View
                    </Button>
                    {submission.status === 'pending' && canApproveSubmissions && (
                      <>
                        <Button
                          size="sm"
                          onClick={() => handleApprove(submission.id)}
                          disabled={isProcessing}
                          className="flex-1 bg-green-600 hover:bg-green-700"
                        >
                          <Check className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => openRejectModal(submission)}
                          disabled={isProcessing}
                          className="flex-1"
                        >
                          <X className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Submissions Table - Desktop */}
      <Card className="hidden md:block">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                {canApproveSubmissions && hasPending && (
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                      title="Select all pending"
                    />
                  </TableHead>
                )}
                <TableHead>URL</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Submitter Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>IP Address</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={canApproveSubmissions && hasPending ? 7 : 6} className="text-center py-8">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto" />
                  </TableCell>
                </TableRow>
              ) : submissions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={canApproveSubmissions && hasPending ? 7 : 6} className="text-center py-12">
                    <div className="flex flex-col items-center gap-3">
                      <Inbox className="h-12 w-12 text-muted-foreground/50" />
                      <div>
                        <p className="text-lg font-medium">No submissions found</p>
                        <p className="text-sm text-muted-foreground">
                          {statusFilter === 'pending'
                            ? 'No pending submissions to review'
                            : statusFilter === 'approved'
                            ? 'No approved submissions yet'
                            : statusFilter === 'rejected'
                            ? 'No rejected submissions'
                            : 'Share the public form to start receiving submissions'}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                submissions.map((submission) => (
                  <TableRow key={submission.id} className={selectedIds.has(submission.id) ? 'bg-primary/5' : ''}>
                    {canApproveSubmissions && hasPending && (
                      <TableCell className="w-10">
                        {submission.status === 'pending' ? (
                          <input
                            type="checkbox"
                            checked={selectedIds.has(submission.id)}
                            onChange={() => toggleSelection(submission.id)}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                          />
                        ) : (
                          <span className="h-4 w-4 block"></span>
                        )}
                      </TableCell>
                    )}
                    <TableCell className="font-medium max-w-xs truncate">
                      {submission.url}
                    </TableCell>
                    <TableCell className="text-sm">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        <span className="text-muted-foreground">{formatDate(submission.submitted_at)}</span>
                        {submission.status === 'pending' && (
                          <span className={`ml-2 text-xs font-medium ${getAgeColor(submission.submitted_at)}`}>
                            ({getAgeText(submission.submitted_at)})
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {submission.submitter_email ? (
                        <div className="flex items-center gap-1">
                          <Mail className="h-3 w-3 text-muted-foreground" />
                          {submission.submitter_email}
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">Anonymous</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {submission.status === 'pending' ? (
                        <div className="flex items-center gap-2">
                          <span className="relative flex h-3 w-3">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
                          </span>
                          <span className="font-medium text-amber-600 dark:text-amber-400">Pending</span>
                          <span className={`text-xs ${getAgeColor(submission.submitted_at)}`}>
                            {getAgeText(submission.submitted_at)}
                          </span>
                        </div>
                      ) : submission.status === 'approved' ? (
                        <div className="flex items-center gap-2">
                          <CheckCircle className="h-4 w-4 text-green-500" />
                          <span className="font-medium text-green-600 dark:text-green-400">Approved</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <XCircle className="h-4 w-4 text-red-500" />
                          <span className="font-medium text-red-600 dark:text-red-400">Rejected</span>
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {submission.ip_address || 'N/A'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openViewModal(submission)}
                          title="View details"
                          className="hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {submission.status === 'pending' && canApproveSubmissions && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleApprove(submission.id)}
                              disabled={isProcessing}
                              title="Approve and create case"
                              className="hover:bg-green-100 dark:hover:bg-green-900/30"
                            >
                              <Check className="h-4 w-4 text-green-600" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openRejectModal(submission)}
                              disabled={isProcessing}
                              title="Reject submission"
                              className="hover:bg-red-100 dark:hover:bg-red-900/30"
                            >
                              <X className="h-4 w-4 text-destructive" />
                            </Button>
                          </>
                        )}
                        {canDeleteSubmissions && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(submission.id)}
                            title="Delete submission"
                            className="hover:bg-red-100 dark:hover:bg-red-900/30"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="flex items-center px-4">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </Button>
        </div>
      )}

      {/* View Modal */}
      {showViewModal && selectedSubmission && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
            <CardHeader>
              <CardTitle>Submission Details</CardTitle>
              <CardDescription>
                Review the submission before taking action
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground text-sm">URL</Label>
                <p className="font-mono text-sm bg-muted p-2 rounded break-all">
                  {selectedSubmission.url}
                </p>
              </div>

              <div className="space-y-2">
                <Label className="text-muted-foreground text-sm">Status</Label>
                <Badge className={getStatusBadgeColor(selectedSubmission.status)}>
                  {selectedSubmission.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-sm">Submitted At</Label>
                  <p className="text-sm">{formatDate(selectedSubmission.submitted_at)}</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-sm">IP Address</Label>
                  <p className="text-sm">{selectedSubmission.ip_address || 'N/A'}</p>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-muted-foreground text-sm flex items-center gap-1">
                  <Mail className="h-4 w-4" />
                  Submitter Email
                </Label>
                <p className="text-sm">
                  {selectedSubmission.submitter_email || 'Anonymous'}
                </p>
              </div>

              {selectedSubmission.additional_notes && (
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-sm flex items-center gap-1">
                    <FileText className="h-4 w-4" />
                    Additional Notes
                  </Label>
                  <p className="text-sm bg-muted p-2 rounded">
                    {selectedSubmission.additional_notes}
                  </p>
                </div>
              )}

              {selectedSubmission.case_id && (
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-sm">Linked Case</Label>
                  <Link
                    href={`/cases/${selectedSubmission.case_id}`}
                    className="text-blue-600 hover:underline flex items-center gap-1"
                  >
                    {selectedSubmission.case_id}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              )}

              {selectedSubmission.reviewed_at && (
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-sm">Reviewed At</Label>
                  <p className="text-sm">{formatDate(selectedSubmission.reviewed_at)}</p>
                </div>
              )}

              <div className="flex gap-2 justify-end pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowViewModal(false);
                    setSelectedSubmission(null);
                  }}
                >
                  Close
                </Button>
                {selectedSubmission.status === 'pending' && canApproveSubmissions && (
                  <Button
                    onClick={() => {
                      setShowViewModal(false);
                      handleApprove(selectedSubmission.id);
                    }}
                    disabled={isProcessing}
                  >
                    <Check className="h-4 w-4 mr-2" />
                    Approve
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && selectedSubmission && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Reject Submission</CardTitle>
              <CardDescription>
                Provide a reason for rejecting this submission
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="reject-reason">Reason (Optional)</Label>
                <Textarea
                  id="reject-reason"
                  placeholder="Why is this submission being rejected?"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  rows={4}
                  maxLength={1000}
                />
              </div>

              <div className="flex gap-2 justify-end pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowRejectModal(false);
                    setSelectedSubmission(null);
                    setRejectReason('');
                  }}
                  disabled={isProcessing}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleReject}
                  disabled={isProcessing}
                >
                  <X className="h-4 w-4 mr-2" />
                  Reject
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Bulk Actions Floating Bar */}
      {selectedIds.size > 0 && canApproveSubmissions && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
          <Card className="shadow-lg border-2">
            <CardContent className="py-3 px-4">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium">
                  {selectedIds.size} selected
                </span>
                <div className="h-6 w-px bg-border"></div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={handleBulkApprove}
                    disabled={isProcessing}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    <Check className="h-4 w-4 mr-1" />
                    Approve All
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={handleBulkReject}
                    disabled={isProcessing}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Reject All
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setSelectedIds(new Set())}
                  >
                    Clear
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export { SubmissionsManagementContent };

export default function SubmissionsManagementPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to admin page with submissions tab for consistent UI
    router.replace('/admin?tab=submissions');
  }, [router]);

  return null;
}
