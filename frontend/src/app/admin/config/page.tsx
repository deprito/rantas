'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api, ConfigResponse, EmailTemplate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Settings,
  RefreshCw,
  Save,
  Mail,
  Clock,
  Globe,
  Shield,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Send,
  X,
  Cloud,
  LogOut,
} from 'lucide-react';

interface SmtpTestDetails {
  to: string;
  from: string;
  subject: string;
  host: string;
  port: number;
  tls: boolean;
}

interface SmtpTestResult {
  success: boolean;
  message: string;
  details?: SmtpTestDetails;
}

interface GraphTestDetails {
  to: string;
  from: string;
  subject: string;
  method: string;
  template?: string;
}

interface GraphTestResult {
  success: boolean;
  message: string;
  details?: GraphTestDetails;
}

function ConfigManagementContent() {
  const router = useRouter();
  const { user } = useAuth();

  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Test SMTP state
  const [testEmail, setTestEmail] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [emailTemplates, setEmailTemplates] = useState<EmailTemplate[]>([]);
  const [isSendingTest, setIsSendingTest] = useState(false);
  const [testResult, setTestResult] = useState<SmtpTestResult | null>(null);
  const [showTestModal, setShowTestModal] = useState(false);

  // Test Graph API state
  const [graphTestEmail, setGraphTestEmail] = useState('');
  const [graphSelectedTemplate, setGraphSelectedTemplate] = useState<string>('');
  const [isSendingGraphTest, setIsSendingGraphTest] = useState(false);
  const [graphTestResult, setGraphTestResult] = useState<GraphTestResult | null>(null);
  const [showGraphTestModal, setShowGraphTestModal] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    smtp_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    smtp_from_email: '',
    smtp_from_name: '',
    smtp_use_tls: true,
    graph_enabled: false,
    graph_tenant_id: '',
    graph_client_id: '',
    graph_client_secret: '',
    graph_from_email: '',
    monitor_interval_default: 21600,
    cors_origins: [] as string[],
    brand_impacted: [] as string[],
    session_timeout_minutes: 30,
  });

  const canUpdateConfig = user?.permissions.includes('*') || user?.permissions.includes(Permission.CONFIG_UPDATE);

  useEffect(() => {
    loadConfig();
  }, []);

  // Close modals on ESC key press
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showTestModal) setShowTestModal(false);
        if (showGraphTestModal) setShowGraphTestModal(false);
      }
    };

    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [showTestModal, showGraphTestModal]);

  const loadConfig = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getConfig();
      setConfig(data);
      setFormData({
        smtp_enabled: data.smtp_enabled,
        smtp_host: data.smtp_host || '',
        smtp_port: data.smtp_port || 587,
        smtp_username: data.smtp_username || '',
        smtp_password: '',
        smtp_from_email: data.smtp_from_email,
        smtp_from_name: data.smtp_from_name,
        smtp_use_tls: data.smtp_use_tls ?? true,
        graph_enabled: data.graph_enabled,
        graph_tenant_id: data.graph_tenant_id || '',
        graph_client_id: data.graph_client_id || '',
        graph_client_secret: '',
        graph_from_email: data.graph_from_email || '',
        monitor_interval_default: data.monitor_interval_default,
        cors_origins: data.cors_origins,
        brand_impacted: data.brand_impacted || [],
        session_timeout_minutes: data.session_timeout_minutes || 30,
      });
      // Also load email templates for testing
      try {
        const templates = await api.listEmailTemplates();
        setEmailTemplates(templates);
      } catch {
        // Ignore if templates fail to load
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestSmtp = async () => {
    if (!testEmail) {
      setError('Please enter a test email address');
      return;
    }

    setIsSendingTest(true);
    setTestResult(null);
    setError(null);

    try {
      const result = await api.testSmtp(testEmail, selectedTemplate || undefined);
      setTestResult(result);
      if (result.success) {
        setSuccess(result.message);
        setTimeout(() => setSuccess(null), 5000);
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send test email');
    } finally {
      setIsSendingTest(false);
    }
  };

  const openTestModal = () => {
    // Set default test email to current user's email
    setTestEmail(user?.email || '');
    setTestResult(null);
    setShowTestModal(true);
  };

  const handleTestGraphApi = async () => {
    if (!graphTestEmail) {
      setError('Please enter a test email address');
      return;
    }

    setIsSendingGraphTest(true);
    setGraphTestResult(null);
    setError(null);

    try {
      const result = await api.testGraphApi(graphTestEmail, graphSelectedTemplate || undefined);
      setGraphTestResult(result);
      if (result.success) {
        setSuccess(result.message);
        setTimeout(() => setSuccess(null), 5000);
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send test email');
    } finally {
      setIsSendingGraphTest(false);
    }
  };

  const openGraphTestModal = () => {
    // Set default test email to current user's email
    setGraphTestEmail(user?.email || '');
    setGraphSelectedTemplate('');
    setGraphTestResult(null);
    setShowGraphTestModal(true);
  };

  const handleSaveConfig = async () => {
    if (!canUpdateConfig) return;

    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updateData: Record<string, unknown> = {};

      if (formData.smtp_enabled !== config?.smtp_enabled) updateData.smtp_enabled = formData.smtp_enabled;
      if (formData.smtp_host !== config?.smtp_host) updateData.smtp_host = formData.smtp_host;
      if (formData.smtp_port !== config?.smtp_port) updateData.smtp_port = formData.smtp_port;
      if (formData.smtp_username !== config?.smtp_username) updateData.smtp_username = formData.smtp_username;
      if (formData.smtp_password) updateData.smtp_password = formData.smtp_password;
      if (formData.smtp_from_email !== config?.smtp_from_email) updateData.smtp_from_email = formData.smtp_from_email;
      if (formData.smtp_from_name !== config?.smtp_from_name) updateData.smtp_from_name = formData.smtp_from_name;
      if (formData.smtp_use_tls !== config?.smtp_use_tls) updateData.smtp_use_tls = formData.smtp_use_tls;
      if (formData.graph_enabled !== config?.graph_enabled) updateData.graph_enabled = formData.graph_enabled;
      if (formData.graph_tenant_id !== config?.graph_tenant_id) updateData.graph_tenant_id = formData.graph_tenant_id;
      if (formData.graph_client_id !== config?.graph_client_id) updateData.graph_client_id = formData.graph_client_id;
      if (formData.graph_client_secret) updateData.graph_client_secret = formData.graph_client_secret;
      if (formData.graph_from_email !== config?.graph_from_email) updateData.graph_from_email = formData.graph_from_email;
      if (formData.monitor_interval_default !== config?.monitor_interval_default) {
        updateData.monitor_interval_default = formData.monitor_interval_default;
      }
      if (JSON.stringify(formData.cors_origins) !== JSON.stringify(config?.cors_origins)) {
        updateData.cors_origins = formData.cors_origins;
      }
      if (JSON.stringify(formData.brand_impacted) !== JSON.stringify(config?.brand_impacted)) {
        console.log('Brands changed - will update:', formData.brand_impacted);
        updateData.brand_impacted = formData.brand_impacted;
      } else {
        console.log('Brands unchanged - no update needed');
      }
      if (formData.session_timeout_minutes !== config?.session_timeout_minutes) {
        updateData.session_timeout_minutes = formData.session_timeout_minutes;
      }

      console.log('Sending update to API:', updateData);
      const result = await api.updateConfig(updateData);
      console.log('API response:', result);
      await loadConfig();
      console.log('After reload - brands:', config);
      setSuccess('Configuration updated successfully');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleInitializeSystem = async () => {
    if (!confirm('This will create default roles and an admin user. Continue?')) return;

    try {
      const result = await api.initializeSystem();

      if (result.users_created.length > 0) {
        const admin = result.users_created[0];
        alert(`System initialized!\n\nAdmin user created:\nUsername: ${admin.username}\nPassword: ${admin.password}\n\nPlease change this password immediately.`);
      } else {
        alert('System already initialized. Roles created: ' + result.roles_created.join(', '));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize system');
    }
  };

  const addCorsOrigin = () => {
    const origin = prompt('Enter CORS origin (e.g., http://localhost:3000):');
    if (origin && !formData.cors_origins.includes(origin)) {
      setFormData({ ...formData, cors_origins: [...formData.cors_origins, origin] });
    }
  };

  const removeCorsOrigin = (index: number) => {
    setFormData({
      ...formData,
      cors_origins: formData.cors_origins.filter((_, i) => i !== index),
    });
  };

  const addBrand = () => {
    const brand = prompt('Enter brand name:');
    if (brand && brand.trim() && !formData.brand_impacted.includes(brand.trim())) {
      setFormData({ ...formData, brand_impacted: [...formData.brand_impacted, brand.trim()] });
    }
  };

  const removeBrand = (index: number) => {
    setFormData({
      ...formData,
      brand_impacted: formData.brand_impacted.filter((_, i) => i !== index),
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Settings className="h-6 w-6" />
            System Configuration
          </h2>
          <p className="text-muted-foreground mt-1">
            Manage system settings and preferences
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleInitializeSystem}>
            <Shield className="h-4 w-4 mr-2" />
            Initialize System
          </Button>
          <Button variant="outline" onClick={loadConfig} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Version Info */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">PhishTrack Version</p>
              <p className="text-lg font-semibold">{config?.version || 'Unknown'}</p>
            </div>
            <Badge variant="outline">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              System Operational
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Messages */}
      {error && (
        <div className="mb-4 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 bg-green-500/10 border border-green-500/20 text-green-600 p-4 rounded-lg flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          {success}
        </div>
      )}

      {/* Email Configurations - Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* SMTP Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              Email Configuration (SMTP)
            </CardTitle>
            <CardDescription>
              Settings for sending abuse reports and notifications
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="smtp_enabled"
                checked={formData.smtp_enabled}
                onChange={(e) => setFormData({ ...formData, smtp_enabled: e.target.checked })}
                disabled={!canUpdateConfig}
              />
              <Label htmlFor="smtp_enabled">Enable SMTP</Label>
              {config?.smtp_has_password && (
                <Badge variant="outline" className="ml-auto">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Password Configured
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="smtp_host">SMTP Host</Label>
                <Input
                  id="smtp_host"
                  value={formData.smtp_host}
                  onChange={(e) => setFormData({ ...formData, smtp_host: e.target.value })}
                  disabled={!canUpdateConfig}
                  placeholder="smtp.gmail.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp_port">SMTP Port</Label>
                <Input
                  id="smtp_port"
                  type="number"
                  value={formData.smtp_port}
                  onChange={(e) => setFormData({ ...formData, smtp_port: parseInt(e.target.value) || 587 })}
                  disabled={!canUpdateConfig}
                  placeholder="587"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp_username">SMTP Username</Label>
              <Input
                id="smtp_username"
                value={formData.smtp_username}
                onChange={(e) => setFormData({ ...formData, smtp_username: e.target.value })}
                disabled={!canUpdateConfig}
                placeholder="your-email@gmail.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp_password">SMTP Password</Label>
              <Input
                id="smtp_password"
                type="password"
                value={formData.smtp_password}
                onChange={(e) => setFormData({ ...formData, smtp_password: e.target.value })}
                disabled={!canUpdateConfig}
                placeholder={config?.smtp_has_password ? '••••••••' : 'Enter new password'}
              />
              <p className="text-xs text-muted-foreground">
                {config?.smtp_has_password ? 'Leave empty to keep existing password' : 'Enter SMTP password'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="smtp_from_email">From Email</Label>
                <Input
                  id="smtp_from_email"
                  type="email"
                  value={formData.smtp_from_email}
                  onChange={(e) => setFormData({ ...formData, smtp_from_email: e.target.value })}
                  disabled={!canUpdateConfig}
                  placeholder="abuse@phishtrack.local"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp_from_name">From Name</Label>
                <Input
                  id="smtp_from_name"
                  value={formData.smtp_from_name}
                  onChange={(e) => setFormData({ ...formData, smtp_from_name: e.target.value })}
                  disabled={!canUpdateConfig}
                  placeholder="PhishTrack Abuse Reporting"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="smtp_use_tls"
                checked={formData.smtp_use_tls}
                onChange={(e) => setFormData({ ...formData, smtp_use_tls: e.target.checked })}
                disabled={!canUpdateConfig}
              />
              <Label htmlFor="smtp_use_tls">Use TLS</Label>
            </div>

            {/* Test SMTP Button */}
            <div className="pt-4 border-t">
              <Button
                variant="outline"
                onClick={openTestModal}
                disabled={!formData.smtp_enabled}
                className="w-full"
              >
                <Send className="h-4 w-4 mr-2" />
                Test SMTP Configuration
              </Button>
              <p className="text-xs text-muted-foreground mt-2">
                Send a test email to verify your SMTP settings are working correctly
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Graph API Configuration */}
        <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cloud className="h-5 w-5" />
            Email Configuration (Microsoft Graph API)
          </CardTitle>
          <CardDescription>
            Send emails via Microsoft Graph API (alternative to SMTP)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="graph_enabled"
              checked={formData.graph_enabled}
              onChange={(e) => setFormData({ ...formData, graph_enabled: e.target.checked })}
              disabled={!canUpdateConfig}
            />
            <Label htmlFor="graph_enabled">Enable Graph API</Label>
            {config?.graph_has_secret && (
              <Badge variant="outline" className="ml-auto">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Secret Configured
              </Badge>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="graph_tenant_id">Tenant ID</Label>
              <Input
                id="graph_tenant_id"
                value={formData.graph_tenant_id || ''}
                onChange={(e) => setFormData({ ...formData, graph_tenant_id: e.target.value })}
                disabled={!canUpdateConfig}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="graph_client_id">Client ID</Label>
              <Input
                id="graph_client_id"
                value={formData.graph_client_id || ''}
                onChange={(e) => setFormData({ ...formData, graph_client_id: e.target.value })}
                disabled={!canUpdateConfig}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="graph_client_secret">Client Secret</Label>
            <Input
              id="graph_client_secret"
              type="password"
              value={formData.graph_client_secret || ''}
              onChange={(e) => setFormData({ ...formData, graph_client_secret: e.target.value })}
              disabled={!canUpdateConfig}
              placeholder={config?.graph_has_secret ? '••••••••' : 'Enter client secret'}
            />
            <p className="text-xs text-muted-foreground">
              {config?.graph_has_secret ? 'Leave empty to keep existing secret' : 'Azure app registration client secret'}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="graph_from_email">From Email</Label>
            <Input
              id="graph_from_email"
              type="email"
              value={formData.graph_from_email || ''}
              onChange={(e) => setFormData({ ...formData, graph_from_email: e.target.value })}
              disabled={!canUpdateConfig}
              placeholder="sender@example.com"
            />
            <p className="text-xs text-muted-foreground">
              Mailbox that will send the emails (must exist in your organization)
            </p>
          </div>

          {/* Test Graph API Button */}
          <div className="pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => openGraphTestModal()}
              disabled={!formData.graph_enabled}
              className="w-full"
            >
              <Send className="h-4 w-4 mr-2" />
              Test Graph API Configuration
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              Send a test email to verify your Graph API settings are working correctly
            </p>
          </div>
        </CardContent>
      </Card>
      </div>

      {/* Monitoring Configuration */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Monitoring Configuration
          </CardTitle>
          <CardDescription>
            Default intervals for URL monitoring
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="monitor_interval">Default Monitor Interval (seconds)</Label>
            <Input
              id="monitor_interval"
              type="number"
              value={formData.monitor_interval_default}
              onChange={(e) => setFormData({ ...formData, monitor_interval_default: parseInt(e.target.value) || 21600 })}
              disabled={!canUpdateConfig}
              min={1800}
              max={86400}
            />
            <p className="text-xs text-muted-foreground">
              Default: {Math.floor(21600 / 3600)} hours ({formData.monitor_interval_default} seconds)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* CORS & Security Configuration - Two Column Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* CORS Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              CORS Configuration
            </CardTitle>
            <CardDescription>
              Allowed origins for cross-origin requests
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {formData.cors_origins.map((origin, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input value={origin} disabled className="font-mono text-sm" />
                  {canUpdateConfig && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeCorsOrigin(index)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              ))}
              {canUpdateConfig && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addCorsOrigin}
                  className="mt-2"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Origin
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Security Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <LogOut className="h-5 w-5" />
              Security Configuration
            </CardTitle>
            <CardDescription>
              Session timeout and authentication settings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Label htmlFor="session_timeout">Session Timeout (minutes)</Label>
              <Input
                id="session_timeout"
                type="number"
                value={formData.session_timeout_minutes}
                onChange={(e) => setFormData({ ...formData, session_timeout_minutes: parseInt(e.target.value) || 30 })}
                disabled={!canUpdateConfig}
                min={5}
                max={1440}
              />
              <p className="text-xs text-muted-foreground">
                Users will be logged out after {formData.session_timeout_minutes} minutes of inactivity.
                (Min: 5, Max: 1440)
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Brand Configuration */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            Brand Impacted Configuration
          </CardTitle>
          <CardDescription>
            Manage brands for abuse reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {formData.brand_impacted.map((brand, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input value={brand} disabled className="font-mono text-sm" />
                {canUpdateConfig && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeBrand(index)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </div>
            ))}
            {canUpdateConfig && (
              <Button
                variant="outline"
                size="sm"
                onClick={addBrand}
                className="mt-2"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Brand
              </Button>
            )}
            <p className="text-xs text-muted-foreground mt-2">
              Brands appear in the dropdown when sending reports
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      {canUpdateConfig && (
        <div className="flex justify-end">
          <Button onClick={handleSaveConfig} disabled={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? 'Saving...' : 'Save Configuration'}
          </Button>
        </div>
      )}

      {!canUpdateConfig && (
        <div className="bg-muted/50 border border-border p-4 rounded-lg text-center">
          <p className="text-muted-foreground">
            You don't have permission to modify configuration.
          </p>
        </div>
      )}

      {/* Test SMTP Modal */}
      {showTestModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Send className="h-5 w-5" />
                  Test SMTP Configuration
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowTestModal(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
              <CardDescription>
                Send a test email to verify your SMTP settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="test_email">Test Email Address</Label>
                <Input
                  id="test_email"
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="test@example.com"
                />
              </div>

              {emailTemplates.length > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="template_select">Email Template (Optional)</Label>
                  <select
                    id="template_select"
                    className="w-full px-3 py-2 border rounded-md"
                    value={selectedTemplate}
                    onChange={(e) => setSelectedTemplate(e.target.value)}
                  >
                    <option value="">Use default test message</option>
                    {emailTemplates.map(t => (
                      <option key={t.id} value={t.id}>
                        {t.name} {t.is_default ? '(Default)' : ''}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Select a template to test with sample data filled in
                  </p>
                </div>
              )}

              {testResult && (
                <div className={`p-3 rounded-md ${testResult.success ? 'bg-green-500/10 border border-green-500/20' : 'bg-destructive/10 border border-destructive/20'}`}>
                  <div className="flex items-start gap-2">
                    {testResult.success ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600 mt-0.5" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                    )}
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${testResult.success ? 'text-green-700' : 'text-destructive'}`}>
                        {testResult.message}
                      </p>
                      {testResult.details && (
                        <div className="mt-2 text-xs text-muted-foreground space-y-1">
                          <p><strong>To:</strong> {testResult.details.to}</p>
                          <p><strong>From:</strong> {testResult.details.from}</p>
                          <p><strong>Subject:</strong> {testResult.details.subject}</p>
                          <p><strong>Server:</strong> {testResult.details.host}:{testResult.details.port}</p>
                          <p><strong>TLS:</strong> {testResult.details.tls ? 'Yes' : 'No'}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setShowTestModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleTestSmtp}
                  disabled={!testEmail || isSendingTest}
                >
                  <Send className={`h-4 w-4 mr-2 ${isSendingTest ? 'animate-pulse' : ''}`} />
                  {isSendingTest ? 'Sending...' : 'Send Test Email'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Test Graph API Modal */}
      {showGraphTestModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Send className="h-5 w-5" />
                  Test Graph API Configuration
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowGraphTestModal(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
              <CardDescription>
                Send a test email to verify your Graph API settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="graph_test_email">Test Email Address</Label>
                <Input
                  id="graph_test_email"
                  type="email"
                  value={graphTestEmail}
                  onChange={(e) => setGraphTestEmail(e.target.value)}
                  placeholder="test@example.com"
                />
              </div>

              {emailTemplates.length > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="graph_template_select">Email Template (Optional)</Label>
                  <select
                    id="graph_template_select"
                    className="w-full px-3 py-2 border rounded-md"
                    value={graphSelectedTemplate}
                    onChange={(e) => setGraphSelectedTemplate(e.target.value)}
                  >
                    <option value="">Use default test message</option>
                    {emailTemplates.map(t => (
                      <option key={t.id} value={t.id}>
                        {t.name} {t.is_default ? '(Default)' : ''}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Select a template to test with sample data filled in
                  </p>
                </div>
              )}

              {graphTestResult && (
                <div className={`p-3 rounded-md ${graphTestResult.success ? 'bg-green-500/10 border border-green-500/20' : 'bg-destructive/10 border border-destructive/20'}`}>
                  <div className="flex items-start gap-2">
                    {graphTestResult.success ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600 mt-0.5" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                    )}
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${graphTestResult.success ? 'text-green-700' : 'text-destructive'}`}>
                        {graphTestResult.message}
                      </p>
                      {graphTestResult.details && (
                        <div className="mt-2 text-xs text-muted-foreground space-y-1">
                          <p><strong>To:</strong> {graphTestResult.details.to}</p>
                          <p><strong>From:</strong> {graphTestResult.details.from}</p>
                          <p><strong>Subject:</strong> {graphTestResult.details.subject}</p>
                          <p><strong>Method:</strong> {graphTestResult.details.method}</p>
                          {graphTestResult.details.template && (
                            <p><strong>Template:</strong> {graphTestResult.details.template}</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setShowGraphTestModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleTestGraphApi}
                  disabled={!graphTestEmail || isSendingGraphTest}
                >
                  <Send className={`h-4 w-4 mr-2 ${isSendingGraphTest ? 'animate-pulse' : ''}`} />
                  {isSendingGraphTest ? 'Sending...' : 'Send Test Email'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export { ConfigManagementContent };

export default function ConfigManagementPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to admin page with config tab for consistent UI
    router.replace('/admin?tab=config');
  }, [router]);

  return null;
}
