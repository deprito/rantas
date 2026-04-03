'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api, EmailTemplate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Mail,
  Plus,
  RefreshCw,
  Edit,
  Trash2,
  Star,
  StarOff,
  Eye,
} from 'lucide-react';
import { ApiError } from '@/lib/api';
import { TemplateForm } from './components/TemplateForm';
import { TemplatePreview } from './components/TemplatePreview';

function EmailTemplatesContent() {
  const { hasPermission } = useAuth();

  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);

  const canCreateTemplate = hasPermission(Permission.EMAIL_TEMPLATE_CREATE);
  const canUpdateTemplate = hasPermission(Permission.EMAIL_TEMPLATE_UPDATE);
  const canDeleteTemplate = hasPermission(Permission.EMAIL_TEMPLATE_DELETE);

  useEffect(() => {
    loadTemplates();
  }, []);

  // Close modals on ESC key press
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showCreateModal) setShowCreateModal(false);
        if (showEditModal) setShowEditModal(false);
        if (showPreviewModal) setShowPreviewModal(false);
      }
    };

    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [showCreateModal, showEditModal, showPreviewModal]);

  const loadTemplates = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.listEmailTemplates();
      setTemplates(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load email templates');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTemplate = async (data: { name: string; subject: string; body: string; html_body?: string; cc?: string; prefer_xarf?: boolean; xarf_reporter_ref_template?: string }) => {
    if (!canCreateTemplate) return;

    try {
      await api.createEmailTemplate(data);
      setShowCreateModal(false);
      loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create email template');
    }
  };

  const handleUpdateTemplate = async (id: string, data: { name?: string; subject?: string; body?: string; html_body?: string; cc?: string; is_default?: boolean; prefer_xarf?: boolean; xarf_reporter_ref_template?: string }) => {
    if (!canUpdateTemplate) return;

    try {
      await api.updateEmailTemplate(id, data);
      setShowEditModal(false);
      setSelectedTemplate(null);
      loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update email template');
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    if (!canDeleteTemplate) return;

    if (!confirm('Are you sure you want to delete this email template?')) return;

    try {
      await api.deleteEmailTemplate(id);
      loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete email template');
    }
  };

  const handleSetDefault = async (id: string) => {
    if (!canUpdateTemplate) return;

    try {
      await api.setDefaultEmailTemplate(id);
      loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set default template');
    }
  };

  const openEditModal = (template: EmailTemplate) => {
    setSelectedTemplate(template);
    setShowEditModal(true);
  };

  const openPreviewModal = (template: EmailTemplate) => {
    setSelectedTemplate(template);
    setShowPreviewModal(true);
  };

  // Available template variables
  const templateVariables = [
    { name: '{{ case_id }}', description: 'Case ID' },
    { name: '{{ target_url }}', description: 'Target URL' },
    { name: '{{ domain }}', description: 'Domain name' },
    { name: '{{ ip }}', description: 'IP address' },
    { name: '{{ organization }}', description: 'Organization name (registrar/hosting/dns)' },
    { name: '{{ reporter_email }}', description: 'Reporter email' },
    { name: '{{ reported_date }}', description: 'Report date' },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Mail className="h-6 w-6" />
            Email Templates
          </h2>
          <p className="text-muted-foreground mt-1">
            Manage email templates for abuse reports
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadTemplates} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {canCreateTemplate && (
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Template
            </Button>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg">
          {error}
        </div>
      )}

      {/* Template Variables Reference */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm">Available Template Variables</CardTitle>
          <CardDescription>
            Use these variables in your email subject and body. They will be replaced with actual values when sending reports.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {templateVariables.map((v) => (
              <Badge key={v.name} variant="outline" className="font-mono text-xs">
                {v.name}
                <span className="text-muted-foreground ml-1">({v.description})</span>
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Templates Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>CC</TableHead>
                <TableHead>XARF</TableHead>
                <TableHead>Default</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto" />
                  </TableCell>
                </TableRow>
              ) : templates.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    No email templates found. Create your first template to get started.
                  </TableCell>
                </TableRow>
              ) : (
                templates.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell className="max-w-xs truncate">{t.subject}</TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                      {t.cc || '-'}
                    </TableCell>
                    <TableCell>
                      {t.prefer_xarf ? (
                        <Badge variant="default" className="bg-blue-600">
                          XARF
                        </Badge>
                      ) : (
                        <Badge variant="outline">No</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {t.is_default ? (
                        <Badge className="bg-primary">
                          <Star className="h-3 w-3 mr-1" />
                          Default
                        </Badge>
                      ) : (
                        <Badge variant="outline">No</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(t.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openPreviewModal(t)}
                          title="Preview"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {canUpdateTemplate && !t.is_default && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSetDefault(t.id)}
                            title="Set as Default"
                          >
                            <Star className="h-4 w-4" />
                          </Button>
                        )}
                        {canUpdateTemplate && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditModal(t)}
                            title="Edit"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                        )}
                        {canDeleteTemplate && !t.is_default && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteTemplate(t.id)}
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create Template Modal */}
      {showCreateModal && (
        <TemplateForm
          onSubmit={handleCreateTemplate}
          onCancel={() => setShowCreateModal(false)}
        />
      )}

      {/* Edit Template Modal */}
      {showEditModal && selectedTemplate && (
        <TemplateForm
          template={selectedTemplate}
          onSubmit={(data) => handleUpdateTemplate(selectedTemplate.id, data)}
          onCancel={() => { setShowEditModal(false); setSelectedTemplate(null); }}
        />
      )}

      {/* Preview Modal */}
      {showPreviewModal && selectedTemplate && (
        <TemplatePreview
          template={selectedTemplate}
          onClose={() => { setShowPreviewModal(false); setSelectedTemplate(null); }}
        />
      )}
    </div>
  );
}

export { EmailTemplatesContent };

export default function EmailTemplatesPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to admin page with email-templates tab for consistent UI
    router.replace('/admin?tab=email-templates');
  }, [router]);

  return null;
}
