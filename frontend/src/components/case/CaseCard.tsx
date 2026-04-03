'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Case } from '@/types/case';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { ProgressPipeline } from '@/components/progress-pipeline';
import { api, ApiError, EmailTemplate } from '@/lib/api';

import { CaseHeader } from './CaseHeader';
import { CaseHistory } from './CaseHistory';
import { CaseDomainInfo } from './CaseDomainInfo';
import { TemplateModal } from './modals/TemplateModal';
import { ConfirmModal } from './modals/ConfirmModal';
import { BrandEditModal } from './modals/BrandEditModal';
import { DeleteModal } from './modals/DeleteModal';

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

export function CaseCard({
  case: caze,
  onReanalyze,
  onUpdated,
  onDeleted,
  canSendReport = true,
  canDeleteCase = false,
}: CaseCardProps) {
  // Modal states
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showBrandEditModal, setShowBrandEditModal] = useState(false);

  // Loading states
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [isSendingReport, setIsSendingReport] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpdatingBrand, setIsUpdatingBrand] = useState(false);

  // Data states
  const [emailTemplates, setEmailTemplates] = useState<EmailTemplate[]>([]);
  const [brandOptions, setBrandOptions] = useState<string[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [selectedBrand, setSelectedBrand] = useState<string>('');
  const [editingBrand, setEditingBrand] = useState<string>('');
  const [isFollowup, setIsFollowup] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Load email templates and config when any modal is opened
  useEffect(() => {
    if (showTemplateModal || showBrandEditModal) {
      api.listEmailTemplates()
        .then(setEmailTemplates)
        .catch(() => setEmailTemplates([]));

      api.getConfig()
        .then((config) => setBrandOptions(config.brand_impacted || []))
        .catch(() => setBrandOptions([]));
    }
  }, [showTemplateModal, showBrandEditModal]);

  // Close modals on ESC key press
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showTemplateModal) setShowTemplateModal(false);
        if (showConfirmModal) setShowConfirmModal(false);
        if (showDeleteModal) setShowDeleteModal(false);
        if (showBrandEditModal) setShowBrandEditModal(false);
      }
    };

    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [showTemplateModal, showConfirmModal, showDeleteModal, showBrandEditModal]);

  // Computed values
  const showSendReport = useMemo(
    () =>
      caze.domain_info !== null &&
      caze.abuse_contacts.length > 0 &&
      (caze.status === 'READY_TO_REPORT' || caze.status === 'FAILED') &&
      canSendReport,
    [caze.domain_info, caze.abuse_contacts.length, caze.status, canSendReport]
  );

  const showSendFollowup = useMemo(
    () =>
      caze.domain_info !== null &&
      caze.abuse_contacts.length > 0 &&
      (caze.status === 'MONITORING' || caze.status === 'REPORTED') &&
      canSendReport,
    [caze.domain_info, caze.abuse_contacts.length, caze.status, canSendReport]
  );

  // Handlers
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

  const handleSendReport = useCallback(
    async (templateId?: string, selectedContactsList?: string[]) => {
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
        setIsFollowup(false);
        setSelectedBrand('');
      } catch (error) {
        const message =
          error instanceof ApiError ? error.message : isFollowup ? 'Failed to send follow-up' : 'Failed to send report';
        setActionError(message);
      } finally {
        setIsSendingReport(false);
      }
    },
    [caze.id, onUpdated, isFollowup, selectedBrand]
  );

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
    setActionError(null);
    const defaultTemplate = emailTemplates.find((t) => t.is_default);
    setSelectedTemplateId(defaultTemplate?.id || '');
    setShowTemplateModal(false);
    setShowConfirmModal(true);
  }, [emailTemplates]);

  const toggleContact = useCallback((email: string) => {
    setSelectedContacts((prev) => {
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
    setSelectedContacts(new Set(caze.abuse_contacts.map((c) => c.email)));
  }, [caze.abuse_contacts]);

  const deselectAllContacts = useCallback(() => {
    setSelectedContacts(new Set());
  }, []);

  const openSendReportModal = useCallback(() => {
    setSelectedContacts(new Set(caze.abuse_contacts.map((c) => c.email)));
    setIsFollowup(false);
    setSelectedBrand(caze.brand_impacted || 'Unknown');
    setShowTemplateModal(true);
  }, [caze.abuse_contacts, caze.brand_impacted]);

  const openSendFollowupModal = useCallback(() => {
    setSelectedContacts(new Set(caze.abuse_contacts.map((c) => c.email)));
    setIsFollowup(true);
    setSelectedBrand(caze.brand_impacted || '');
    setShowTemplateModal(true);
  }, [caze.abuse_contacts, caze.brand_impacted]);

  return (
    <Card className="w-full">
      <CardHeader>
        <CaseHeader
          case={caze}
          isReanalyzing={isReanalyzing}
          isSendingReport={isSendingReport}
          isDeleting={isDeleting}
          showSendReport={showSendReport}
          showSendFollowup={showSendFollowup}
          canDeleteCase={canDeleteCase}
          actionError={actionError}
          onReanalyze={handleReanalyze}
          onOpenSendReport={openSendReportModal}
          onOpenSendFollowup={openSendFollowupModal}
          onOpenBrandEdit={openBrandEditModal}
          onOpenDelete={() => setShowDeleteModal(true)}
        />
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

        {/* Domain Info & Abuse Contacts */}
        <CaseDomainInfo domainInfo={caze.domain_info} abuseContacts={caze.abuse_contacts} />

        {/* History */}
        <CaseHistory history={caze.history} />
      </CardContent>

      {/* Modals */}
      <TemplateModal
        isOpen={showTemplateModal}
        isFollowup={isFollowup}
        emailTemplates={emailTemplates}
        brandOptions={brandOptions}
        selectedTemplateId={selectedTemplateId}
        selectedBrand={selectedBrand}
        isSendingReport={isSendingReport}
        onClose={() => setShowTemplateModal(false)}
        onNext={handleProceedToConfirm}
        onTemplateChange={setSelectedTemplateId}
        onBrandChange={setSelectedBrand}
      />

      <ConfirmModal
        isOpen={showConfirmModal}
        isFollowup={isFollowup}
        case={caze}
        emailTemplates={emailTemplates}
        selectedTemplateId={selectedTemplateId}
        selectedContacts={selectedContacts}
        isSendingReport={isSendingReport}
        onClose={() => setShowConfirmModal(false)}
        onBack={() => {
          setShowConfirmModal(false);
          setShowTemplateModal(true);
        }}
        onSend={() => handleSendReport(selectedTemplateId || undefined, Array.from(selectedContacts))}
        onToggleContact={toggleContact}
        onSelectAll={selectAllContacts}
        onDeselectAll={deselectAllContacts}
      />

      <BrandEditModal
        isOpen={showBrandEditModal}
        brandOptions={brandOptions}
        editingBrand={editingBrand}
        isUpdatingBrand={isUpdatingBrand}
        actionError={actionError}
        onClose={() => setShowBrandEditModal(false)}
        onUpdate={handleUpdateBrand}
        onBrandChange={setEditingBrand}
      />

      <DeleteModal
        isOpen={showDeleteModal}
        case={caze}
        isDeleting={isDeleting}
        onClose={() => setShowDeleteModal(false)}
        onDelete={handleDelete}
      />
    </Card>
  );
}

// Re-export skeleton from same location
export { CaseCardSkeleton } from './CaseCardSkeleton';
