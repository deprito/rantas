import { Case } from '@/types/case';

interface CaseHistoryProps {
  history: Case['history'];
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

export function CaseHistory({ history }: CaseHistoryProps) {
  if (history.length === 0) return null;

  return (
    <div>
      {/* Desktop: Always expanded */}
      <div className="hidden md:block">
        <h3 className="text-sm font-medium mb-3">Activity Log</h3>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {history.map((entry, idx) => (
            <HistoryEntry key={`${entry.id}-${idx}`} entry={entry} />
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
          {history.map((entry, idx) => (
            <HistoryEntry key={`${entry.id}-${idx}`} entry={entry} />
          ))}
        </div>
      </details>
    </div>
  );
}

interface HistoryEntryProps {
  entry: Case['history'][number];
}

function HistoryEntry({ entry }: HistoryEntryProps) {
  return (
    <div className="flex items-start gap-2 text-sm p-2 bg-muted/50 rounded">
      <HistoryIcon type={entry.type} />
      <div className="flex-1 min-w-0">
        <div className="flex justify-between gap-2">
          <span className="font-medium truncate">{entry.message}</span>
          {entry.status !== undefined && (
            <StatusBadge status={entry.status} />
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(entry.timestamp).toLocaleString()}
        </span>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: number }) {
  let variant: 'default' | 'destructive' | 'secondary' = 'secondary';

  if (status >= 200 && status < 300) variant = 'default';
  else if (status >= 400 && status < 500) variant = 'destructive';

  return (
    <Badge variant={variant} className="shrink-0">
      {status}
    </Badge>
  );
}

// Import icons
import { Server, Eye, Mail, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
