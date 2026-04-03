'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Case, statusLabels, statusColors, CaseSource, AbuseContact } from '@/types/case';
import { ProgressPipeline } from './progress-pipeline';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Clock,
  Globe,
  Server,
  Mail,
  AlertTriangle,
  CheckCircle2,
  Eye,
  RefreshCw,
  Send,
  X,
  Users,
  Globe2,
  AlertCircle,
  Check,
  Trash2,
  Pencil,
} from 'lucide-react';
import { api, ApiError, EmailTemplate } from '@/lib/api';

interface CaseCardProps {
  case: Case;
  onReanalyze?: (caseId: string) => Promise<void>;
  onUpdated?: () => void;
  onDeleted?: () => void;
  canSendReport?: boolean;
  canDeleteCase?: boolean;
}

function maskUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.hostname}[...]${parsed.pathname}`;
  } catch {
    return url.substring(0, 30) + '[...]';
  }
}

function getSourceBadgeColor(source: CaseSource): string {
  switch (source) {
    case 'public':
      return 'bg-purple-500 text-white border-purple-500';
    case 'internal':
    default:
      return 'bg-slate-500 text-white border-slate-500';
  }
}

function getSourceIcon(source: CaseSource) {
  switch (source) {
    case 'public':
      return <Globe2 className="h-3 w-3" />;
    case 'internal':
    default:
      return <Users className="h-3 w-3" />;
  }
}

function HistoryIcon({ type }: { type: string }) {
  switch (type) {
    case 'dns_check':
      return <Server className="h-4 w-4" />;
    case 'http_check':
      return <Eye className="h-4 w-4" />;
    case 'email_sent':
      return <Mail className="h-4 w-4 text-blue-500" />;
    case 'email_received':
      return <Mail className="h-4 w-4 text-green-500" />;
    default:
      return <Clock className="h-4 w-4" />;
  }
}

export function CaseCard({ case: caze, onReanalyze, onUpdated, onDeleted, canSendReport = true, canDeleteCase = false }: CaseCardProps) {
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [isSendingReport, setIsSendingReport] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showBrandEditModal, setShowBrandEditModal] = useState(false);
  const [emailTemplates, setEmailTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [selectedBrand, setSelectedBrand] = useState<string>('');
  const [editingBrand, setEditingBrand] = useState<string>('');
  const [brandOptions, setBrandOptions] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isFollowup, setIsFollowup] = useState(false); // Track if we're sending a follow-up
  const [isUpdatingBrand, setIsUpdatingBrand] = useState(false);

  // Is case currently being analyzed
  const isAnalyzing = caze.status === 'ANALYZING';

  useEffect(() => {
    // Load email templates and config (for brand options) when any modal is opened
    if (showTemplateModal || showBrandEditModal) {
      api.listEmailTemplates()
        .then(setEmailTemplates)
        .catch(() => setEmailTemplates([]));

      // Load config to get brand_impacted options
      api.getConfig()
        .then(config => setBrandOptions(config.brand_impacted || []))
        .catch(() => setBrandOptions([]));
    }
  }, [showTemplateModal, showBrandEditModal]);

  const handleReanalyze = useCallback(async () => {
    setIsReanalyzing(true);
    setActionError(null);
    try {
      if (onReanalyze) {
        await onReanalyze(caze.id);
      } else {
        await api.reanalyzeCase(caze.id);
      }
      onUpdated?.();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Failed to re-analyze case';
      setActionError(message);
    } finally {
      setIsReanalyzing(false);
    }
  }, [caze.id, onReanalyze, onUpdated]);

  const handleSendReport = useCallback(async (templateId?: string, selectedContactsList?: string[]) => {
    setIsSendingReport(true);
    setActionError(null);
    setShowConfirmModal(false);
    setShowTemplateModal(false);
    try {
      if (isFollowup) {
        await api.sendFollowup(caze.id, selectedBrand, templateId, selectedContactsList);
      } else {
        await api.sendReport(caze.id, selectedBrand, templateId, selectedContactsList);
      }
      onUpdated?.();
      setIsFollowup(false); // Reset follow-up state
      setSelectedBrand(''); // Reset brand selection
    } catch (error) {
      const message = error instanceof ApiError ? error.message : isFollowup ? 'Failed to send follow-up' : 'Failed to send report';
      setActionError(message);
    } finally {
      setIsSendingReport(false);
    }
  }, [caze.id, onUpdated, isFollowup, selectedBrand]);

  const handleDelete = useCallback(async () => {
    setIsDeleting(true);
    setActionError(null);
    try {
      await api.deleteCase(caze.id);
      setShowDeleteModal(false);
      onDeleted?.();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Failed to delete case';
      setActionError(message);
      setShowDeleteModal(false);
    } finally {
      setIsDeleting(false);
    }
  }, [caze.id, onDeleted]);

  const handleUpdateBrand = useCallback(async () => {
    setIsUpdatingBrand(true);
    setActionError(null);
    try {
      await api.updateCase(caze.id, { brand_impacted: editingBrand });
      setShowBrandEditModal(false);
      onUpdated?.();
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Failed to update brand';
      setActionError(message);
    } finally {
      setIsUpdatingBrand(false);
    }
  }, [caze.id, onUpdated, editingBrand]);

  const openBrandEditModal = useCallback(() => {
    setEditingBrand(caze.brand_impacted || '');
    setShowBrandEditModal(true);
  }, [caze.brand_impacted]);

  const handleProceedToConfirm = useCallback(() => {
    // Clear any previous error state when opening delete modal
    setActionError(null);
    // Set default template as selected
    const defaultTemplate = emailTemplates.find(t => t.is_default);
    setSelectedTemplateId(defaultTemplate?.id || '');
    setShowTemplateModal(false);
    setShowConfirmModal(true);
  }, [emailTemplates]);

  const toggleContact = useCallback((email: string) => {
    setSelectedContacts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(email)) {
        newSet.delete(email);
      } else {
        newSet.add(email);
      }
      return newSet;
    });
  }, []);

  const selectAllContacts = useCallback(() => {
    setSelectedContacts(new Set(caze.abuse_contacts.map(c => c.email)));
  }, [caze.abuse_contacts]);

  const deselectAllContacts = useCallback(() => {
    setSelectedContacts(new Set());
  }, []);

  const openSendReportModal = useCallback(() => {
    // Initialize with all contacts selected by default (user can deselect)
    setSelectedContacts(new Set(caze.abuse_contacts.map(c => c.email)));
    setIsFollowup(false); // Reset to initial report mode
    // Pre-select the case's existing brand (or 'Unknown' if not set)
    setSelectedBrand(caze.brand_impacted || 'Unknown');
    setShowTemplateModal(true);
  }, [caze.abuse_contacts, caze.brand_impacted]);

  const openSendFollowupModal = useCallback(() => {
    // Initialize with all contacts selected by default (user can deselect)
    setSelectedContacts(new Set(caze.abuse_contacts.map(c => c.email)));
    setIsFollowup(true); // Set to follow-up mode
    // Pre-select the case's existing brand
    setSelectedBrand(caze.brand_impacted || '');
    setShowTemplateModal(true);
  }, [caze.abuse_contacts, caze.brand_impacted]);

  // Show "Send Report" button when:
  // 1. Analysis is complete (has domain_info)
  // 2. Has abuse contacts
  // 3. Status is READY_TO_REPORT or FAILED
  // 4. User has permission
  const showSendReport = useMemo(
    () => caze.domain_info !== null &&
      caze.abuse_contacts.length > 0 &&
      (caze.status === 'READY_TO_REPORT' || caze.status === 'FAILED') &&
      canSendReport,
    [caze.domain_info, caze.abuse_contacts.length, caze.status, canSendReport]
  );

  // Show "Send Follow-up" button when:
  // 1. Analysis is complete (has domain_info)
  // 2. Has abuse contacts
  // 3. Status is MONITORING or REPORTED
  const showSendFollowup = useMemo(
    () => caze.domain_info !== null &&
      caze.abuse_contacts.length > 0 &&
      (caze.status === 'MONITORING' || caze.status === 'REPORTED') &&
      canSendReport,
    [caze.domain_info, caze.abuse_contacts.length, caze.status, canSendReport]
  );

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1 flex-1">
            <CardTitle className="text-lg flex items-center gap-2">
              <div className="relative">
                <AlertTriangle className="h-5 w-5 text-orange-500" />
              </div>
              Case #{caze.id.slice(0, 8)}
            </CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={statusColors[caze.status]}>
                {statusLabels[caze.status]}
              </Badge>
              <Badge
                className="bg-blue-500 text-white cursor-pointer hover:bg-blue-600 transition-colors"
                onClick={openBrandEditModal}
                title="Click to edit brand"
              >
                {caze.brand_impacted}
              </Badge>
              <Badge className={getSourceBadgeColor(caze.source)} variant="outline">
                {getSourceIcon(caze.source)}
                {caze.source === 'public' ? 'Public' : 'Internal'}
              </Badge>
              <span className="text-xs text-muted-foreground">
                Created: {new Date(caze.created_at).toLocaleString()}
              </span>
              {caze.created_by_username && (
                <Badge className="bg-gray-500 text-white" variant="outline" title={`Created by: ${caze.created_by_username}`}>
                  By: {caze.created_by_username}
                </Badge>
              )}
            </div>
            {actionError && (
              <p className="text-xs text-destructive">{actionError}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {caze.status === 'RESOLVED' && (
              <CheckCircle2 className="h-6 w-6 text-green-500" />
            )}
            {showSendReport && (
              <Button
                variant="default"
                size="sm"
                onClick={openSendReportModal}
                disabled={isSendingReport}
                className="gap-1"
              >
                <Send className={`h-4 w-4 ${isSendingReport ? 'animate-pulse' : ''}`} />
                {isSendingReport ? 'Sending...' : 'Send Report'}
              </Button>
            )}
            {showSendFollowup && (
              <Button
                variant="secondary"
                size="sm"
                onClick={openSendFollowupModal}
                disabled={isSendingReport}
                className="gap-1"
              >
                <RefreshCw className={`h-4 w-4 ${isSendingReport ? 'animate-spin' : ''}`} />
                {isSendingReport ? 'Sending...' : 'Send Follow-up'}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleReanalyze}
              disabled={isReanalyzing}
              className="gap-1"
            >
              <RefreshCw className={`h-4 w-4 ${isReanalyzing ? 'animate-spin' : ''}`} />
              {isReanalyzing ? 'Analyzing...' : 'Re-analyze'}
            </Button>
            {canDeleteCase && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDeleteModal(true)}
                disabled={isDeleting}
                className="gap-1"
              >
                <Trash2 className={`h-4 w-4 ${isDeleting ? 'animate-pulse' : ''}`} />
                {isDeleting ? 'Deleting...' : 'Delete'}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Progress Pipeline */}
        <div>
          <h3 className="text-sm font-medium mb-3">Takedown Progress</h3>
          <ProgressPipeline status={caze.status} />
        </div>

        {/* URL Display - Masked for Security */}
        <div>
          <h3 className="text-sm font-medium mb-2">Target URL</h3>
          <code className="text-sm bg-muted px-3 py-2 rounded-md block break-all text-orange-600">
            {maskUrl(caze.url)}
          </code>
          <p className="text-xs text-muted-foreground mt-1">
            <i>Link masked to prevent accidental clicks</i>
          </p>
        </div>

        {/* Domain Info */}
        {caze.domain_info ? (
          <div>
            <h3 className="text-sm font-medium mb-3">Domain Intelligence</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <InfoCard
                icon={<Globe className="h-4 w-4" />}
                label="Registrar"
                value={caze.domain_info.registrar}
              />
              <InfoCard
                icon={<Server className="h-4 w-4" />}
                label="IP Address"
                value={caze.domain_info.ip}
              />
              <InfoCard
                icon={<Clock className="h-4 w-4" />}
                label="Domain Age"
                value={`${caze.domain_info.age_days} days`}
              />
              <InfoCard
                icon={<Server className="h-4 w-4" />}
                label="ASN"
                value={caze.domain_info.asn}
              />
            </div>
            {caze.domain_info.ns_records.length > 0 && (
              <div className="mt-3">
                <span className="text-xs text-muted-foreground">Nameservers: </span>
                <span className="text-xs font-mono">
                  {caze.domain_info.ns_records.join(', ')}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <Skeleton className="h-20 w-full" />
          </div>
        )}

        {/* Abuse Contacts */}
        {caze.abuse_contacts.length > 0 && (
          <div>
            <h3 className="text-sm font-medium mb-2">Abuse Contacts</h3>
            <div className="flex flex-wrap gap-2">
              {caze.abuse_contacts.map((contact, idx) => (
                <Badge key={idx} variant="outline" className="gap-1">
                  <Mail className="h-3 w-3" />
                  {contact.type}: {contact.email}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* History */}
        {caze.history.length > 0 && (
          <div>
            {/* Desktop: Always expanded */}
            <div className="hidden md:block">
              <h3 className="text-sm font-medium mb-3">Activity Log</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {caze.history.map((entry, idx) => (
                  <div
                    key={`${entry.id}-${idx}`}
                    className="flex items-start gap-2 text-sm p-2 bg-muted/50 rounded"
                  >
                    <HistoryIcon type={entry.type} />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between gap-2">
                        <span className="font-medium truncate">{entry.message}</span>
                        {entry.status !== undefined && (
                          <Badge
                            variant={
                              entry.status >= 200 && entry.status < 300
                                ? 'default'
                                : entry.status >= 400 && entry.status < 500
                                  ? 'destructive'
                                  : 'secondary'
                            }
                            className="shrink-0"
                          >
                            {entry.status}
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(entry.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Mobile: Collapsible */}
            <details className="md:hidden group">
              <summary className="cursor-pointer list-none">
                <h3 className="text-sm font-medium mb-2 flex items-center gap-1">
                  Activity Log
                  <span className="transform group-open:rotate-180 transition-transform">
                    ▼
                  </span>
                </h3>
              </summary>
              <div className="space-y-2 max-h-48 overflow-y-auto mt-2">
                {caze.history.map((entry, idx) => (
                  <div
                    key={`${entry.id}-${idx}`}
                    className="flex items-start gap-2 text-sm p-2 bg-muted/50 rounded"
                  >
                    <HistoryIcon type={entry.type} />
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-col justify-between gap-1">
                        <span className="font-medium truncate">{entry.message}</span>
                        {entry.status !== undefined && (
                          <Badge
                            variant={
                              entry.status >= 200 && entry.status < 300
                                ? 'default'
                                : entry.status >= 400 && entry.status < 500
                                  ? 'destructive'
                                  : 'secondary'
                            }
                            className="shrink-0"
                          >
                            {entry.status}
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(entry.timestamp).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </CardContent>

      {/* Template Selection Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>{isFollowup ? 'Follow-up Report' : 'Select Email Template'}</CardTitle>
              <CardDescription>
                {isFollowup
                  ? 'Choose an email template to use for the follow-up report'
                  : 'Choose an email template to use for sending the abuse report'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="template-select">Email Template</Label>
                <select
                  id="template-select"
                  className="w-full px-3 py-2 border rounded-md"
                  value={selectedTemplateId}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                >
                  {emailTemplates.length === 0 ? (
                    <option value="">No templates available</option>
                  ) : (
                    <>
                      <option value="">Use default template</option>
                      {emailTemplates.map(t => (
                        <option key={t.id} value={t.id}>
                          {t.name} {t.is_default ? '(Default)' : ''}
                        </option>
                      ))}
                    </>
                  )}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="brand-select">Brand Impacted *</Label>
                <select
                  id="brand-select"
                  className="w-full px-3 py-2 border rounded-md"
                  value={selectedBrand}
                  onChange={(e) => setSelectedBrand(e.target.value)}
                  required
                >
                  <option value="">-- Select a brand --</option>
                  {brandOptions.map((brand) => (
                    <option key={brand} value={brand}>
                      {brand}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  Select the brand being impersonated by this phishing site (required)
                </p>
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setShowTemplateModal(false)}
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
                <Button
                  onClick={handleProceedToConfirm}
                  disabled={isSendingReport || emailTemplates.length === 0 || !selectedBrand}
                >
                  Next
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Confirmation & Contact Selection Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-orange-500" />
                {isFollowup ? 'Send Follow-up' : 'Confirm & Select Recipients'}
              </CardTitle>
              <CardDescription>
                {isFollowup
                  ? 'Review the abuse contacts below and select which ones to send the follow-up report to.'
                  : 'Review the abuse contacts below and select which ones to send the report to.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Contact Selection */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Select Abuse Contacts</Label>
                  <div className="flex gap-2 text-xs">
                    <button
                      type="button"
                      onClick={selectAllContacts}
                      className="text-blue-600 hover:underline"
                    >
                      Select All
                    </button>
                    <span className="text-muted-foreground">|</span>
                    <button
                      type="button"
                      onClick={deselectAllContacts}
                      className="text-blue-600 hover:underline"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>
                <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
                  {caze.abuse_contacts.map((contact, idx) => {
                    const email = contact.email;
                    const isSelected = selectedContacts.has(email);
                    return (
                      <label
                        key={`${idx}-${email}`}
                        className={`flex items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer ${
                          isSelected ? 'bg-blue-50/50' : ''
                        }`}
                      >
                        <div className="relative flex items-center">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleContact(email)}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500 cursor-pointer"
                          />
                          {isSelected && (
                            <Check className="h-3 w-3 absolute left-0.5 top-0.5 text-white pointer-events-none" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-sm">{email}</div>
                          <div className="text-xs text-muted-foreground capitalize">{contact.type}</div>
                        </div>
                        <Badge variant="outline" className="shrink-0">
                          {contact.type}
                        </Badge>
                      </label>
                    );
                  })}
                </div>
                {selectedContacts.size === 0 && (
                  <p className="text-sm text-destructive flex items-center gap-1">
                    <AlertCircle className="h-4 w-4" />
                    Please select at least one contact
                  </p>
                )}
                {selectedContacts.size > 0 && (
                  <p className="text-sm text-muted-foreground">
                    {selectedContacts.size} contact{selectedContacts.size !== 1 ? 's' : ''} selected
                  </p>
                )}
              </div>

              {/* Summary */}
              {selectedContacts.size > 0 && (
                <div className="bg-muted/50 p-3 rounded-md space-y-2">
                  <h4 className="text-sm font-medium">Summary</h4>
                  <div className="text-sm space-y-1">
                    <p><span className="text-muted-foreground">Case:</span> #{caze.id.slice(0, 8)}</p>
                    <p><span className="text-muted-foreground">Template:</span> {
                      emailTemplates.find(t => t.id === selectedTemplateId)?.name || 'Default'
                    }</p>
                    <p><span className="text-muted-foreground">Recipients:</span> {Array.from(selectedContacts).join(', ')}</p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowConfirmModal(false);
                    setShowTemplateModal(true);
                  }}
                  disabled={isSendingReport}
                >
                  Back
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowConfirmModal(false)}
                  disabled={isSendingReport}
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
                <Button
                  onClick={() => handleSendReport(
                    selectedTemplateId || undefined,
                    Array.from(selectedContacts)
                  )}
                  disabled={isSendingReport || selectedContacts.size === 0}
                >
                  {isFollowup ? (
                    <RefreshCw className={`h-4 w-4 mr-2 ${isSendingReport ? 'animate-spin' : ''}`} />
                  ) : (
                    <Send className={`h-4 w-4 mr-2 ${isSendingReport ? 'animate-pulse' : ''}`} />
                  )}
                  {isSendingReport
                    ? 'Sending...'
                    : `${isFollowup ? 'Send Follow-up' : 'Send'} to ${selectedContacts.size} Recipient${selectedContacts.size !== 1 ? 's' : ''}`}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Brand Edit Modal */}
      {showBrandEditModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pencil className="h-5 w-5 text-blue-500" />
                Edit Brand Impacted
              </CardTitle>
              <CardDescription>
                Select the brand being impersonated by this phishing site
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="brand-select">Brand Impacted</Label>
                <select
                  id="brand-select"
                  className="w-full px-3 py-2 border rounded-md"
                  value={editingBrand}
                  onChange={(e) => setEditingBrand(e.target.value)}
                >
                  <option value="">-- Select a brand --</option>
                  {brandOptions.map((brand) => (
                    <option key={brand} value={brand}>
                      {brand}
                    </option>
                  ))}
                </select>
              </div>
              {actionError && showBrandEditModal && (
                <p className="text-sm text-destructive flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" />
                  {actionError}
                </p>
              )}
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setShowBrandEditModal(false)}
                  disabled={isUpdatingBrand}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleUpdateBrand}
                  disabled={isUpdatingBrand || !editingBrand}
                >
                  {isUpdatingBrand ? 'Updating...' : 'Update Brand'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trash2 className="h-5 w-5 text-destructive" />
                Delete Case
              </CardTitle>
              <CardDescription>
                Are you sure you want to delete this case? This action cannot be undone.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-muted/50 p-3 rounded-md space-y-2">
                <p className="text-sm"><span className="text-muted-foreground">Case:</span> {caze.id.slice(0, 13)}</p>
                <p className="text-sm"><span className="text-muted-foreground">Status:</span> {statusLabels[caze.status]}</p>
                <p className="text-sm"><span className="text-muted-foreground">URL:</span> {maskUrl(caze.url)}</p>
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteModal(false)}
                  disabled={isDeleting}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={isDeleting}
                >
                  <Trash2 className={`h-4 w-4 mr-2 ${isDeleting ? 'animate-pulse' : ''}`} />
                  {isDeleting ? 'Deleting...' : 'Delete Case'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </Card>
  );
}

function InfoCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number | undefined;
}) {
  return (
    <div className="bg-muted/50 p-3 rounded-lg space-y-1">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <p className="text-sm font-medium truncate" title={String(value ?? 'N/A')}>
        {value ?? <span className="text-muted-foreground">N/A</span>}
      </p>
    </div>
  );
}

export function CaseCardSkeleton() {
  return (
    <Card className="w-full">
      <CardHeader>
        <div className="space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-5 w-32" />
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <div className="grid grid-cols-4 gap-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      </CardContent>
    </Card>
  );
}
