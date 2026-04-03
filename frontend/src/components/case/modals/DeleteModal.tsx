import { Case, statusLabels } from '@/types/case';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Trash2, AlertTriangle } from 'lucide-react';

interface DeleteModalProps {
  isOpen: boolean;
  case: Case;
  isDeleting: boolean;
  onClose: () => void;
  onDelete: () => void;
}

function maskUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.hostname}[...]${parsed.pathname}`;
  } catch {
    return url.substring(0, 30) + '[...]';
  }
}

export function DeleteModal({
  isOpen,
  case: caze,
  isDeleting,
  onClose,
  onDelete,
}: DeleteModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Delete Case
          </CardTitle>
          <CardDescription>
            Are you sure you want to delete this case? This action cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-muted/50 p-3 rounded-md space-y-2">
            <p className="text-sm">
              <span className="text-muted-foreground">Case:</span> {caze.id.slice(0, 13)}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">Status:</span> {statusLabels[caze.status]}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">URL:</span> {maskUrl(caze.url)}
            </p>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onClose} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={onDelete} disabled={isDeleting}>
              <Trash2 className={`h-4 w-4 mr-2 ${isDeleting ? 'animate-pulse' : ''}`} />
              {isDeleting ? 'Deleting...' : 'Delete Case'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
