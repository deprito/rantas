'use client';

import { useState, useCallback, useRef } from 'react';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api } from '@/lib/api';
import { Upload, Download, FileSpreadsheet, AlertCircle, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';

function ImportContent() {
  const { hasPermission } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    imported_count: number;
    skipped_count: number;
    errors: string[];
  } | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const canImport = hasPermission(Permission.STATS_IMPORT);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setImportResult(null);
      } else {
        alert('Please upload a CSV file');
      }
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
      setImportResult(null);
    }
  }, []);

  const handleUpload = async () => {
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setImportResult(null);

    try {
      const result = await api.importHistoricalCases(selectedFile);
      setImportResult(result);
      if (result.success) {
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    } catch (error) {
      setImportResult({
        success: false,
        imported_count: 0,
        skipped_count: 0,
        errors: [error instanceof Error ? error.message : 'Import failed'],
      });
    } finally {
      setIsUploading(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      const blob = await api.downloadImportTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'historical_cases_template.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      alert('Failed to download template');
    }
  };

  if (!canImport) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center">
              <AlertCircle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
              <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
              <p className="text-muted-foreground">
                You don&apos;t have permission to import historical data.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <header className="border-b bg-white/50 dark:bg-slate-950/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Link href="/dashboard" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
              <div className="bg-primary/10 p-2 rounded-lg">
                <FileSpreadsheet className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Import Historical Data</h1>
                <p className="text-xs text-muted-foreground">
                  Import historical case statistics from CSV
                </p>
              </div>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Instructions Card */}
          <Card>
            <CardHeader>
              <CardTitle>Import Instructions</CardTitle>
              <CardDescription>
                Upload a CSV file containing historical case data to include in statistics
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-medium mb-2">Required Columns:</h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li><code className="bg-muted px-1 rounded">url</code> - Phishing URL</li>
                  <li><code className="bg-muted px-1 rounded">created_at</code> - ISO 8601 datetime (e.g., 2024-01-15T10:30:00Z)</li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium mb-2">Optional Columns:</h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li><code className="bg-muted px-1 rounded">status</code> - Case status (default: RESOLVED)</li>
                  <li><code className="bg-muted px-1 rounded">source</code> - internal or public (default: internal)</li>
                  <li><code className="bg-muted px-1 rounded">brand_impacted</code> - Brand name</li>
                  <li><code className="bg-muted px-1 rounded">emails_sent</code> - Number of emails sent (default: 0)</li>
                  <li><code className="bg-muted px-1 rounded">updated_at</code> - ISO 8601 datetime</li>
                  <li><code className="bg-muted px-1 rounded">registrar</code> - Domain registrar</li>
                  <li><code className="bg-muted px-1 rounded">ip</code> - IP address</li>
                </ul>
              </div>
              <Button onClick={downloadTemplate} variant="outline" className="w-full">
                <Download className="h-4 w-4 mr-2" />
                Download CSV Template
              </Button>
            </CardContent>
          </Card>

          {/* Upload Area */}
          <Card>
            <CardHeader>
              <CardTitle>Upload CSV File</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
                  border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
                  ${isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'}
                  ${selectedFile ? 'border-green-500/50 bg-green-500/5' : ''}
                `}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                {isUploading ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">Importing data...</p>
                  </div>
                ) : selectedFile ? (
                  <div className="flex flex-col items-center gap-2">
                    <FileSpreadsheet className="h-8 w-8 text-green-500" />
                    <p className="font-medium">{selectedFile.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(selectedFile.size / 1024).toFixed(2)} KB
                    </p>
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                        setImportResult(null);
                      }}
                      variant="ghost"
                      size="sm"
                      className="mt-2"
                    >
                      Remove
                    </Button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <p className="font-medium">Drop CSV file here or click to browse</p>
                    <p className="text-sm text-muted-foreground">Supports CSV files only</p>
                  </div>
                )}
              </div>

              {selectedFile && !isUploading && (
                <Button
                  onClick={handleUpload}
                  className="w-full mt-4"
                  size="lg"
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Import Historical Data
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Import Result */}
          {importResult && (
            <Alert className={importResult.success ? 'border-green-500/50' : 'border-red-500/50'}>
              {importResult.success ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
              <AlertDescription>
                {importResult.success ? (
                  <div>
                    <p className="font-medium">Import completed successfully!</p>
                    <p className="text-sm mt-1">
                      {importResult.imported_count} records imported
                      {importResult.skipped_count > 0 && ` (${importResult.skipped_count} skipped)`}
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="font-medium">Import failed</p>
                    {importResult.errors.length > 0 && (
                      <ul className="text-sm mt-2 space-y-1">
                        {importResult.errors.slice(0, 10).map((error, i) => (
                          <li key={i} className="text-red-500">{error}</li>
                        ))}
                        {importResult.errors.length > 10 && (
                          <li className="text-muted-foreground">
                            ...and {importResult.errors.length - 10} more errors
                          </li>
                        )}
                      </ul>
                    )}
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* Info Alert */}
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>Note:</strong> Imported data is stored separately and only affects statistics.
              Use the &quot;Include Historical Data&quot; toggle on the dashboard to view statistics
              with or without imported historical data.
            </AlertDescription>
          </Alert>
        </div>
      </main>
    </div>
  );
}

export default function StatsImportPage() {
  return (
    <ProtectedRoute>
      <ImportContent />
    </ProtectedRoute>
  );
}
