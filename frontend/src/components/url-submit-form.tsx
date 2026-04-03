'use client';

import { useState, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { AlertCircle, Loader2 } from 'lucide-react';

interface UrlSubmitFormProps {
  onSubmit: (url: string) => void;
  isSubmitting?: boolean;
}

export function UrlSubmitForm({ onSubmit, isSubmitting = false }: UrlSubmitFormProps) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  const isValidUrl = useCallback((str: string): boolean => {
    try {
      const parsed = new URL(str);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  }, []);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!url.trim()) {
      setError('Please enter a URL');
      return;
    }

    if (!isValidUrl(url)) {
      setError('Please enter a valid URL (e.g., https://example.com)');
      return;
    }

    onSubmit(url.trim());
  }, [url, isValidUrl, onSubmit]);

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-orange-500" />
          Submit Phishing Site for Takedown
        </CardTitle>
        <CardDescription>
          Enter a suspicious URL to initiate automated OSINT analysis and abuse reporting
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="url">Suspicious URL</Label>
            <Input
              id="url"
              type="url"
              placeholder="https://example.com/suspicious-page"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isSubmitting}
              className="font-mono"
            />
            {error && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {error}
              </p>
            )}
          </div>

          <div className="bg-muted/50 p-3 rounded-lg text-sm text-muted-foreground">
            <p className="font-medium mb-1">What happens next:</p>
            <ol className="list-decimal list-inside space-y-1 text-xs">
              <li>Domain OSINT (age, registrar, IP, abuse contacts)</li>
              <li>Generate and send takedown notice to registrar/host</li>
              <li>Monitor URL for removal (HTTP status checks)</li>
              <li>Track responses via email webhook integration</li>
            </ol>
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>Start Investigation</>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
