'use client';

import { useState, FormEvent, useEffect } from 'react';
import { api, QuickAnalysisResponse } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Shield,
  ShieldAlert,
  Link as LinkIcon,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Mail,
  FileText,
  ExternalLink,
  X,
  Flame,
  Radar,
  Activity,
  Globe,
  Server,
} from 'lucide-react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

export default function PublicSubmitPage() {
  const [url, setUrl] = useState('');
  const [email, setEmail] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [submission, setSubmission] = useState<{ id: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<QuickAnalysisResponse | null>(null);
  const [hasChecked, setHasChecked] = useState(false);

  const isValidUrl = (urlString: string): boolean => {
    try {
      const url = new URL(urlString);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
      return false;
    }
  };

  // Auto-check URL when user stops typing
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (url.trim() && isValidUrl(url.trim())) {
        await performUrlCheck(url.trim());
      } else {
        setAnalysis(null);
        setHasChecked(false);
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [url]);

  const performUrlCheck = async (urlToCheck: string) => {
    setIsChecking(true);
    setError(null);
    try {
      // Use the new deep analyzer
      const result = await api.analyzeUrl(urlToCheck, true);
      setAnalysis(result);
      setHasChecked(true);
    } catch (err) {
      // Don't show error for check failures, just clear analysis
      setAnalysis(null);
      setHasChecked(true);
    } finally {
      setIsChecking(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate URL
    if (!url.trim()) {
      setError('Please enter a URL');
      return;
    }

    if (!isValidUrl(url.trim())) {
      setError('Please enter a valid URL (starting with http:// or https://)');
      return;
    }

    // Validate Email
    if (!email.trim()) {
      setError('Please enter your email');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setError('Please enter a valid email address');
      return;
    }

    // Validate corporate email domain
    const corporateEmailRegex = /^[^@]+@example\.com$/;
    if (!corporateEmailRegex.test(email.trim())) {
      setError('Please use your corporate email to submit');
      return;
    }

    // Check analysis if available
    if (analysis && !analysis.can_submit) {
      setError(analysis.message);
      return;
    }

    setIsSubmitting(true);

    try {
      const data: { url: string; email: string; notes?: string } = {
        url: url.trim(),
        email: email.trim(),
      };

      if (notes.trim()) {
        data.notes = notes.trim();
      }

      const result = await api.publicSubmitUrl(data);
      setSubmission({ id: result.id });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit URL');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setUrl('');
    setEmail('');
    setNotes('');
    setSubmission(null);
    setError(null);
    setAnalysis(null);
    setHasChecked(false);
  };

  const getRiskColor = () => {
    if (!analysis) return '';

    switch (analysis.risk_level) {
      case 'safe':
        return 'text-green-600 dark:text-green-400';
      case 'low':
        return 'text-lime-600 dark:text-lime-400';
      case 'medium':
        return 'text-amber-600 dark:text-amber-400';
      case 'high':
        return 'text-orange-600 dark:text-orange-400';
      case 'critical':
        return 'text-red-600 dark:text-red-400';
    }
  };

  const getRiskBgColor = () => {
    if (!analysis) return '';

    switch (analysis.risk_level) {
      case 'safe':
        return 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-900';
      case 'low':
        return 'bg-lime-50 dark:bg-lime-950/20 border-lime-200 dark:border-lime-900';
      case 'medium':
        return 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900';
      case 'high':
        return 'bg-orange-50 dark:bg-orange-950/20 border-orange-200 dark:border-orange-900';
      case 'critical':
        return 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-900';
    }
  };

  const getRiskIcon = () => {
    if (!analysis) return null;

    switch (analysis.risk_level) {
      case 'safe':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'low':
        return <Shield className="h-5 w-5 text-lime-600" />;
      case 'medium':
        return <AlertTriangle className="h-5 w-5 text-amber-600" />;
      case 'high':
        return <AlertTriangle className="h-5 w-5 text-orange-600" />;
      case 'critical':
        return <Flame className="h-5 w-5 text-red-600" />;
    }
  };

  const getRiskLabel = () => {
    if (!analysis) return '';

    const labels = {
      safe: 'SAFE - Cannot Submit',
      low: 'LOW RISK - Minor Concerns',
      medium: 'MEDIUM RISK - Can Submit',
      high: 'HIGH RISK - Can Submit',
      critical: 'CRITICAL - Submit Immediately',
    };
    return labels[analysis.risk_level] || '';
  };

  const getRiskBadgeColor = () => {
    if (!analysis) return '';

    switch (analysis.risk_level) {
      case 'safe':
        return 'bg-green-600 text-white';
      case 'low':
        return 'bg-lime-600 text-white';
      case 'medium':
        return 'bg-amber-600 text-white';
      case 'high':
        return 'bg-orange-600 text-white';
      case 'critical':
        return 'bg-red-600 text-white';
    }
  };

  const getScoreColor = () => {
    if (!analysis) return 'bg-gray-200';
    const score = analysis.score;
    if (score < 20) return 'bg-green-500';
    if (score < 40) return 'bg-lime-500';
    if (score < 60) return 'bg-amber-500';
    if (score < 80) return 'bg-orange-500';
    return 'bg-red-500';
  };

  const isSubmitDisabled = () => {
    if (isSubmitting || isChecking) return true;
    if (hasChecked && analysis && !analysis.can_submit) return true;
    return false;
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <header className="border-b bg-white/80 dark:bg-slate-950/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-blue-600" />
            <span className="font-bold text-xl">PhishTrack</span>
          </div>
          <Link href="/login">
            <Button variant="outline" size="sm">
              Staff Login
            </Button>
          </Link>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12 max-w-2xl">
        {/* Success State */}
        {submission ? (
          <Card className="border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/20">
            <CardHeader className="text-center">
              <div className="mx-auto w-16 h-16 bg-green-500 rounded-full flex items-center justify-center mb-4">
                <CheckCircle className="h-8 w-8 text-white" />
              </div>
              <CardTitle className="text-green-800 dark:text-green-400">
                Submission Received
              </CardTitle>
              <CardDescription className="text-green-700 dark:text-green-500">
                Your report has been submitted and will be reviewed by our team
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-white dark:bg-slate-900 rounded-lg p-4 border">
                <p className="text-sm text-muted-foreground mb-1">Submission ID</p>
                <p className="text-xl font-mono font-bold">{submission.id}</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-4 border border-blue-200 dark:border-blue-900">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  <strong>What happens next?</strong>
                </p>
                <ul className="mt-2 space-y-1 text-sm text-blue-700 dark:text-blue-400">
                  <li>• Our team will review the submitted URL</li>
                  <li>• If verified as malicious, we will initiate the takedown process</li>
                  <li>• You can check the status using your Submission ID</li>
                </ul>
              </div>
              <div className="flex gap-2 justify-center pt-4">
                <Button variant="outline" onClick={handleReset}>
                  Submit Another URL
                </Button>
                <Link href="/">
                  <Button variant="ghost">
                    Return Home
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Page Header */}
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full mb-4">
                <ShieldAlert className="h-8 w-8 text-red-600 dark:text-red-400" />
              </div>
              <h1 className="text-3xl font-bold mb-2">Report a Phishing Site</h1>
              <p className="text-muted-foreground">
                Advanced URL analysis with real-time threat detection
              </p>
            </div>

            {/* Analysis Result */}
            {hasChecked && analysis && (
              <Card className={`mb-6 ${getRiskBgColor()} border-2`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="flex items-start gap-3 flex-1">
                      {getRiskIcon()}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-lg">{getRiskLabel()}</h3>
                          <Badge className={getRiskBadgeColor()}>
                            Risk Score: {analysis.score}/100
                          </Badge>
                        </div>
                        <p className="text-sm mb-2">{analysis.message}</p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => {
                        setAnalysis(null);
                        setHasChecked(false);
                      }}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Risk Score Bar */}
                  <div className="mb-4">
                    <div className="flex justify-between text-xs mb-1">
                      <span>Risk Score</span>
                      <span className="font-semibold">{analysis.score}/100</span>
                    </div>
                    <Progress value={analysis.score} className="h-2" />
                  </div>

                  {/* Detected Flags */}
                  {analysis.quick_flags.length > 0 && (
                    <div className="bg-white/50 dark:bg-black/10 rounded-lg p-3">
                      <p className="text-xs font-semibold mb-2 flex items-center gap-1">
                        <Radar className="h-3 w-3" />
                        Detected Indicators
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {analysis.quick_flags.slice(0, 6).map((flag, i) => (
                          <Badge key={i} variant="outline" className="text-xs py-0 px-2">
                            {flag}
                          </Badge>
                        ))}
                        {analysis.quick_flags.length > 6 && (
                          <Badge variant="outline" className="text-xs py-0 px-2">
                            +{analysis.quick_flags.length - 6} more
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Submission Form */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <LinkIcon className="h-5 w-5" />
                  Submit Suspicious URL
                </CardTitle>
                <CardDescription>
                  Our advanced analyzer will perform deep security checks including
                  DNS analysis, SSL verification, domain age checks, and reputation lookups.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* URL Input */}
                  <div className="space-y-2">
                    <Label htmlFor="url" className="flex items-center gap-2">
                      URL <span className="text-destructive">*</span>
                      {isChecking && (
                        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary" />
                      )}
                    </Label>
                    <div className="relative">
                      <Input
                        id="url"
                        type="url"
                        placeholder="https://example.com/suspicious-page"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        disabled={isSubmitting}
                        required
                        className={hasChecked && analysis && !analysis.can_submit ? 'border-destructive' : ''}
                      />
                      {isChecking && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                          <Activity className="h-4 w-4 animate-pulse text-muted-foreground" />
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Enter the full URL. We'll automatically analyze it for security threats.
                    </p>
                  </div>

                  {/* Email Input */}
                  <div className="space-y-2">
                    <Label htmlFor="email" className="flex items-center gap-1">
                      <Mail className="h-4 w-4" />
                      Email <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="your.name@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={isSubmitting}
                      required
                    />

                  </div>

                  {/* Notes Input */}
                  <div className="space-y-2">
                    <Label htmlFor="notes" className="flex items-center gap-1">
                      <FileText className="h-4 w-4" />
                      Additional Notes (Optional)
                    </Label>
                    <Textarea
                      id="notes"
                      placeholder="Describe why you believe this site is suspicious..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      disabled={isSubmitting}
                      rows={4}
                      maxLength={2000}
                    />
                    <p className="text-xs text-muted-foreground">
                      Any additional information that may help with our investigation
                    </p>
                  </div>

                  {/* Error Display */}
                  {error && (
                    <div className="bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg flex items-start gap-2">
                      <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                      <p className="text-sm">{error}</p>
                    </div>
                  )}

                  {/* Info message for submittable URLs */}
                  {hasChecked && analysis && analysis.can_submit && analysis.risk_level !== 'safe' && (
                    <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900 p-3 rounded-lg">
                      <p className="text-sm text-blue-800 dark:text-blue-300">
                        <strong>This URL can be submitted.</strong> Risk score: {analysis.score}/100 ({analysis.risk_level.toUpperCase()}).
                      </p>
                    </div>
                  )}

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isSubmitDisabled()}
                  >
                    {isSubmitting ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                        Submitting...
                      </>
                    ) : hasChecked && analysis && !analysis.can_submit ? (
                      <>
                        <X className="h-4 w-4 mr-2" />
                        Cannot Submit - URL Appears Safe
                      </>
                    ) : (
                      <>
                        <ShieldAlert className="h-4 w-4 mr-2" />
                        Submit Report
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Analysis Features */}
            <Card className="mt-6 bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Radar className="h-5 w-5" />
                  Advanced URL Analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="flex items-start gap-2">
                    <Globe className="h-4 w-4 mt-0.5 text-blue-500" />
                    <div>
                      <p className="font-medium text-foreground">Static Analysis</p>
                      <p className="text-xs">URL structure, TLD checks, keyword detection</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Server className="h-4 w-4 mt-0.5 text-green-500" />
                    <div>
                      <p className="font-medium text-foreground">Domain Intelligence</p>
                      <p className="text-xs">WHOIS data, domain age, DNS records</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Activity className="h-4 w-4 mt-0.5 text-amber-500" />
                    <div>
                      <p className="font-medium text-foreground">Behavior Analysis</p>
                      <p className="text-xs">HTTP redirects, SSL certificate, status codes</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Shield className="h-4 w-4 mt-0.5 text-purple-500" />
                    <div>
                      <p className="font-medium text-foreground">Reputation Check</p>
                      <p className="text-xs">Blacklists, threat feeds, security vendors</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-sm text-muted-foreground">
          <p>
            Powered by{' '}
            <Link href="/" className="text-blue-600 hover:underline flex items-center justify-center gap-1">
              PhishTrack <ExternalLink className="h-3 w-3" />
            </Link>
          </p>
        </footer>
      </main>
    </div>
  );
}
