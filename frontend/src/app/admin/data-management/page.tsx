'use client';

import { useState } from 'react';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api } from '@/lib/api';
import { CaseExportDialog } from '@/components/case';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Database,
  Download,
  Trash2,
  AlertTriangle,
  FileSpreadsheet,
  BarChart3,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

const CLEAR_CONFIRM_TEXT = 'DELETE ALL CASES';

function DataManagementContent() {
  const { hasPermission } = useAuth();

  const [isClearDialogOpen, setIsClearDialogOpen] = useState(false);
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canDeleteCases = hasPermission(Permission.CASE_DELETE);
  const canExportCases = hasPermission(Permission.STATS_VIEW);

  const confirmClearCases = async () => {
    if (confirmText !== CLEAR_CONFIRM_TEXT) return;

    setIsDeleting(true);
    setError(null);
    setSuccess(null);

    try {
      await api.deleteAllCases();
      setSuccess('All cases have been deleted successfully.');
      setTimeout(() => setSuccess(null), 5000);
      setIsClearDialogOpen(false);
      setConfirmText('');
    } catch (err) {
      console.error('Failed to delete all cases:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete all cases.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6" />
            Data Management
          </h2>
          <p className="text-muted-foreground mt-1">
            Export and manage case data
          </p>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert className="mb-4 border-green-500/20 text-green-700">
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Data Management Options */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Export Cases */}
        <Card className={canExportCases ? '' : 'opacity-50 pointer-events-none'}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <div className="bg-green-100 dark:bg-green-900/20 p-2 rounded-lg">
                <Download className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              Export Cases
            </CardTitle>
            <CardDescription>
              Download all cases or a filtered subset as CSV or JSON
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3 text-sm text-muted-foreground">
                <FileSpreadsheet className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium text-foreground">CSV Format</p>
                  <p>Spreadsheet-compatible with all case details</p>
                </div>
              </div>
              <div className="flex items-start gap-3 text-sm text-muted-foreground">
                <BarChart3 className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium text-foreground">JSON Format</p>
                  <p>Machine-readable data for analysis</p>
                </div>
              </div>
              <div className="pt-4 border-t">
                <p className="text-xs text-muted-foreground mb-3">
                  Filter by date range, status, or source before exporting
                </p>
                <Button
                  onClick={() => setIsExportDialogOpen(true)}
                  disabled={!canExportCases}
                  className="w-full"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Open Export Dialog
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Delete All Cases */}
        <Card className={canDeleteCases ? '' : 'opacity-50 pointer-events-none'}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <div className="bg-red-100 dark:bg-red-900/20 p-2 rounded-lg">
                <Trash2 className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              Delete All Cases
            </CardTitle>
            <CardDescription>
              Permanently remove all cases from the database
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  <strong>Warning:</strong> This action cannot be undone. All cases will be permanently deleted.
                </AlertDescription>
              </Alert>
              <div className="text-sm text-muted-foreground space-y-1">
                <p>• Deletes all cases regardless of status</p>
                <p>• Removes all associated history and metadata</p>
                <p>• Cannot be recovered once deleted</p>
              </div>
              <Button
                variant="destructive"
                onClick={() => setIsClearDialogOpen(true)}
                disabled={!canDeleteCases}
                className="w-full"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete All Cases
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Permissions Notice */}
      {!canDeleteCases && !canExportCases && (
        <Card className="mt-6">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">
              You don't have permission to perform data management operations.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Delete All Cases Confirmation Dialog */}
      <Dialog open={isClearDialogOpen} onOpenChange={setIsClearDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Confirm Delete All Cases
            </DialogTitle>
            <DialogDescription>
              This will permanently delete all cases. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                Type <code className="font-mono bg-background px-1 py-0.5 rounded">{CLEAR_CONFIRM_TEXT}</code> to confirm.
              </AlertDescription>
            </Alert>
            <Input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={CLEAR_CONFIRM_TEXT}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsClearDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmClearCases}
              disabled={confirmText !== CLEAR_CONFIRM_TEXT || isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete All Cases'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Export Dialog */}
      <CaseExportDialog
        open={isExportDialogOpen}
        onOpenChange={setIsExportDialogOpen}
        onExportComplete={(result) => {
          console.log('Export completed:', result);
          setSuccess('Export completed successfully!');
          setTimeout(() => setSuccess(null), 5000);
        }}
      />
    </div>
  );
}

export { DataManagementContent };

export default function DataManagementPage() {
  return (
    <ProtectedRoute>
      <DataManagementContent />
    </ProtectedRoute>
  );
}
