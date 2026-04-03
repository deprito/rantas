'use client';

import { useState } from 'react';
import { Download, FileText, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { DateRangeFilter } from '@/types/stats';

interface ExportControlsProps {
  dateRange: DateRangeFilter;
  hasExportPermission: boolean;
}

export function ExportControls({ dateRange, hasExportPermission }: ExportControlsProps) {
  const [isExportingCsv, setIsExportingCsv] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [pdfMessage, setPdfMessage] = useState<string | null>(null);

  const handleExportCsv = async () => {
    if (!hasExportPermission) return;

    setIsExportingCsv(true);
    try {
      const blob = await api.exportCsv({
        start_date: dateRange.startDate || undefined,
        end_date: dateRange.endDate || undefined,
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `phishtrack_cases_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export CSV:', error);
      alert('Failed to export CSV. Please try again.');
    } finally {
      setIsExportingCsv(false);
    }
  };

  const handleExportPdf = async () => {
    if (!hasExportPermission) return;

    setIsExportingPdf(true);
    setPdfMessage(null);
    try {
      const response = await api.exportPdf({
        start_date: dateRange.startDate || undefined,
        end_date: dateRange.endDate || undefined,
      });
      setPdfMessage(response.message);
    } catch (error) {
      console.error('Failed to generate PDF:', error);
      setPdfMessage('Failed to generate PDF. Please try again.');
    } finally {
      setIsExportingPdf(false);
    }
  };

  if (!hasExportPermission) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={handleExportCsv}
        disabled={isExportingCsv}
      >
        {isExportingCsv ? (
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        ) : (
          <Download className="h-4 w-4 mr-2" />
        )}
        Export CSV
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={handleExportPdf}
        disabled={isExportingPdf}
      >
        {isExportingPdf ? (
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        ) : (
          <FileText className="h-4 w-4 mr-2" />
        )}
        Generate PDF
      </Button>
      {pdfMessage && (
        <span className="text-sm text-muted-foreground">{pdfMessage}</span>
      )}
    </div>
  );
}
