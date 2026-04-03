'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Download, FileSpreadsheet, FileJson, Loader2 } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { CaseStatus, CaseSource, type ExportFormat } from '@/types/case';

interface CaseExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onExportComplete?: (result: { exportId: string; downloadUrl: string }) => void;
}

const statusOptions = [
  { value: 'all', label: 'Any Status' },
  { value: 'ANALYZING', label: 'Analyzing' },
  { value: 'READY_TO_REPORT', label: 'Ready to Report' },
  { value: 'REPORTING', label: 'Sending Report' },
  { value: 'REPORTED', label: 'Report Sent' },
  { value: 'MONITORING', label: 'Monitoring' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'FAILED', label: 'Failed' },
];

const sourceOptions = [
  { value: 'all', label: 'Any Source' },
  { value: 'internal', label: 'Internal' },
  { value: 'public', label: 'Public' },
];

export function CaseExportDialog({ open, onOpenChange, onExportComplete }: CaseExportDialogProps) {
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [source, setSource] = useState<string>('all');
  const [sendToTeams, setSendToTeams] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<{ exportId: string; downloadUrl: string; format: string } | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    setExportResult(null);

    try {
      const result = await api.exportCases({
        format,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        status: status !== 'all' ? (status as CaseStatus) : undefined,
        source: source !== 'all' ? (source as CaseSource) : undefined,
        send_to_teams: sendToTeams,
      });

      setExportResult({
        exportId: result.export_id,
        downloadUrl: result.download_url,
        format: result.format,
      });

      // Auto-download the file
      await api.downloadExport(result.export_id);

      // Call callback if provided
      if (onExportComplete) {
        onExportComplete({ exportId: result.export_id, downloadUrl: result.download_url });
      }

      // Reset form after successful export
      setTimeout(() => {
        setStartDate('');
        setEndDate('');
        setStatus('all');
        setSource('all');
        setSendToTeams(true);
        setExportResult(null);
        onOpenChange(false);
      }, 2000);

    } catch (err) {
      console.error('Export failed:', err);
      setError(err instanceof Error ? err.message : 'Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const handleDownloadAgain = async () => {
    if (exportResult) {
      try {
        await api.downloadExport(exportResult.exportId);
      } catch (err) {
        console.error('Download failed:', err);
        setError('Failed to download file. Please try again.');
      }
    }
  };

  const handleClose = () => {
    if (!isExporting) {
      setStartDate('');
      setEndDate('');
      setStatus('all');
      setSource('all');
      setSendToTeams(true);
      setError(null);
      setExportResult(null);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Export Cases
          </DialogTitle>
          <DialogDescription>
            Export cases to CSV or JSON format with optional filters.
          </DialogDescription>
        </DialogHeader>

        {exportResult ? (
          <div className="space-y-4 py-4">
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/20 mb-4">
                {format === 'csv' ? (
                  <FileSpreadsheet className="h-6 w-6 text-green-600 dark:text-green-400" />
                ) : (
                  <FileJson className="h-6 w-6 text-green-600 dark:text-green-400" />
                )}
              </div>
              <h3 className="text-lg font-semibold">Export Complete!</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Your file has been downloaded automatically.
              </p>
            </div>

            <Button
              variant="outline"
              className="w-full"
              onClick={handleDownloadAgain}
            >
              <Download className="h-4 w-4 mr-2" />
              Download Again
            </Button>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {/* Format Selection */}
            <div className="space-y-2">
              <Label>Format</Label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="format"
                    value="csv"
                    checked={format === 'csv'}
                    onChange={() => setFormat('csv')}
                    className="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
                  />
                  <FileSpreadsheet className="h-4 w-4 text-green-600" />
                  <span className="text-sm">CSV</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="format"
                    value="json"
                    checked={format === 'json'}
                    onChange={() => setFormat('json')}
                    className="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
                  />
                  <FileJson className="h-4 w-4 text-blue-600" />
                  <span className="text-sm">JSON</span>
                </label>
              </div>
            </div>

            {/* Date Range Filters */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start-date">Start Date</Label>
                <Input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end-date">End Date</Label>
                <Input
                  id="end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>

            {/* Status Filter */}
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger id="status" className="w-full">
                  <SelectValue placeholder="Any status" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Source Filter */}
            <div className="space-y-2">
              <Label htmlFor="source">Source</Label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger id="source" className="w-full">
                  <SelectValue placeholder="Any source" />
                </SelectTrigger>
                <SelectContent>
                  {sourceOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Send to Teams */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="send-to-teams">Send to Teams</Label>
                <p className="text-xs text-muted-foreground">
                  Send notification when export is ready
                </p>
              </div>
              <Switch
                id="send-to-teams"
                checked={sendToTeams}
                onCheckedChange={setSendToTeams}
              />
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-destructive/10 border border-destructive/20 text-destructive p-3 rounded-md text-sm">
                {error}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isExporting}
          >
            {exportResult ? 'Close' : 'Cancel'}
          </Button>
          {!exportResult && (
            <Button
              onClick={handleExport}
              disabled={isExporting}
            >
              {isExporting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
