import { Case, statusColors, statusLabels, CaseSource } from '@/types/case';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Send,
  Trash2,
} from 'lucide-react';

interface CaseHeaderProps {
  case: Case;
  isReanalyzing: boolean;
  isSendingReport: boolean;
  isDeleting: boolean;
  showSendReport: boolean;
  showSendFollowup: boolean;
  canDeleteCase: boolean;
  actionError: string | null;
  onReanalyze: () => void;
  onOpenSendReport: () => void;
  onOpenSendFollowup: () => void;
  onOpenBrandEdit: () => void;
  onOpenDelete: () => void;
}

export function CaseHeader({
  case: caze,
  isReanalyzing,
  isSendingReport,
  isDeleting,
  showSendReport,
  showSendFollowup,
  canDeleteCase,
  actionError,
  onReanalyze,
  onOpenSendReport,
  onOpenSendFollowup,
  onOpenBrandEdit,
  onOpenDelete,
}: CaseHeaderProps) {
  return (
    <div className="flex items-start justify-between">
      <div className="space-y-1 flex-1">
        <CardTitle case={caze} onOpenBrandEdit={onOpenBrandEdit} />
        <Badges
          case={caze}
          onOpenBrandEdit={onOpenBrandEdit}
          actionError={actionError}
        />
      </div>
      <ActionButtons
        isReanalyzing={isReanalyzing}
        isSendingReport={isSendingReport}
        isDeleting={isDeleting}
        showSendReport={showSendReport}
        showSendFollowup={showSendFollowup}
        canDeleteCase={canDeleteCase}
        caseStatus={caze.status}
        onReanalyze={onReanalyze}
        onOpenSendReport={onOpenSendReport}
        onOpenSendFollowup={onOpenSendFollowup}
        onOpenDelete={onOpenDelete}
      />
    </div>
  );
}

function CardTitle({
  case: caze,
  onOpenBrandEdit,
}: {
  case: Case;
  onOpenBrandEdit: () => void;
}) {
  return (
    <h3 className="text-lg flex items-center gap-2 font-semibold">
      <div className="relative">
        <AlertTriangle className="h-5 w-5 text-orange-500" />
      </div>
      Case #{caze.id.slice(0, 8)}
    </h3>
  );
}

function Badges({
  case: caze,
  onOpenBrandEdit,
  actionError,
}: {
  case: Case;
  onOpenBrandEdit: () => void;
  actionError: string | null;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Badge className={statusColors[caze.status]}>
        {statusLabels[caze.status]}
      </Badge>
      <BrandBadge brand={caze.brand_impacted} onClick={onOpenBrandEdit} />
      <SourceBadge source={caze.source} />
      <span className="text-xs text-muted-foreground">
        Created: {new Date(caze.created_at).toLocaleString()}
        {caze.created_by_username && ` by ${caze.created_by_username}`}
      </span>
      {actionError && (
        <p className="text-xs text-destructive">{actionError}</p>
      )}
    </div>
  );
}

function BrandBadge({
  brand,
  onClick,
}: {
  brand: string;
  onClick: () => void;
}) {
  return (
    <Badge
      className="bg-blue-500 text-white cursor-pointer hover:bg-blue-600 transition-colors"
      onClick={onClick}
      title="Click to edit brand"
    >
      {brand}
    </Badge>
  );
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

function SourceBadge({ source }: { source: CaseSource }) {
  return (
    <Badge className={getSourceBadgeColor(source)} variant="outline">
      {getSourceIcon(source)}
      {source === 'public' ? 'Public' : 'Internal'}
    </Badge>
  );
}

function ActionButtons({
  isReanalyzing,
  isSendingReport,
  isDeleting,
  showSendReport,
  showSendFollowup,
  canDeleteCase,
  caseStatus,
  onReanalyze,
  onOpenSendReport,
  onOpenSendFollowup,
  onOpenDelete,
}: {
  isReanalyzing: boolean;
  isSendingReport: boolean;
  isDeleting: boolean;
  showSendReport: boolean;
  showSendFollowup: boolean;
  canDeleteCase: boolean;
  caseStatus: string;
  onReanalyze: () => void;
  onOpenSendReport: () => void;
  onOpenSendFollowup: () => void;
  onOpenDelete: () => void;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2">
      {caseStatus === 'RESOLVED' && (
        <CheckCircle2 className="h-6 w-6 text-green-500" />
      )}
      {showSendReport && (
        <Button
          variant="default"
          size="sm"
          onClick={onOpenSendReport}
          disabled={isSendingReport}
          className="gap-1 w-full sm:w-auto"
        >
          <Send className={`h-4 w-4 ${isSendingReport ? 'animate-pulse' : ''}`} />
          {isSendingReport ? 'Sending...' : 'Send Report'}
        </Button>
      )}
      {showSendFollowup && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onOpenSendFollowup}
          disabled={isSendingReport}
          className="gap-1 w-full sm:w-auto"
        >
          <RefreshCw className={`h-4 w-4 ${isSendingReport ? 'animate-spin' : ''}`} />
          {isSendingReport ? 'Sending...' : 'Send Follow-up'}
        </Button>
      )}
      <Button
        variant="outline"
        size="sm"
        onClick={onReanalyze}
        disabled={isReanalyzing}
        className="gap-1 w-full sm:w-auto"
      >
        <RefreshCw className={`h-4 w-4 ${isReanalyzing ? 'animate-spin' : ''}`} />
        {isReanalyzing ? 'Analyzing...' : 'Re-analyze'}
      </Button>
      {canDeleteCase && (
        <Button
          variant="destructive"
          size="sm"
          onClick={onOpenDelete}
          disabled={isDeleting}
          className="gap-1 w-full sm:w-auto"
        >
          <Trash2 className={`h-4 w-4 ${isDeleting ? 'animate-pulse' : ''}`} />
          {isDeleting ? 'Deleting...' : 'Delete'}
        </Button>
      )}
    </div>
  );
}

import { Globe2, Users } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/card';
