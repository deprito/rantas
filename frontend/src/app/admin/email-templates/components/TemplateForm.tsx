'use client';

import { useState, useEffect } from 'react';
import { EmailTemplate } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RichTextEditor } from '@/components/editor';
import { Switch } from '@/components/ui/switch';

interface TemplateFormProps {
  template?: EmailTemplate;
  onSubmit: (data: { name: string; subject: string; body: string; html_body?: string; cc?: string; prefer_xarf?: boolean; xarf_reporter_ref_template?: string }) => void;
  onCancel: () => void;
}

export function TemplateForm({ template, onSubmit, onCancel }: TemplateFormProps) {
  const [name, setName] = useState(template?.name || '');
  const [subject, setSubject] = useState(template?.subject || '');
  const [cc, setCc] = useState(template?.cc || '');
  const [body, setBody] = useState(template?.body || '');
  const [htmlBody, setHtmlBody] = useState(template?.html_body || '');
  const [preferXarf, setPreferXarf] = useState(template?.prefer_xarf || false);
  const [xarfReporterRefTemplate, setXarfReporterRefTemplate] = useState(template?.xarf_reporter_ref_template || '');
  const [editorMode, setEditorMode] = useState<'plain' | 'rich'>('rich');

  const isEditing = !!template;

  // Helper to strip HTML tags for plain text fallback
  const stripHtml = (html: string): string => {
    if (typeof window === 'undefined') return html;
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    return tempDiv.textContent || tempDiv.innerText || '';
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Check the correct field based on editor mode
    const hasBodyContent = editorMode === 'rich'
      ? htmlBody.trim().length > 0
      : body.trim().length > 0;

    if (!name.trim() || !subject.trim() || !hasBodyContent) {
      return;
    }

    // For rich mode, generate plain text fallback if body is empty
    let finalBody = body;
    if (editorMode === 'rich' && htmlBody.trim()) {
      if (!body.trim()) {
        finalBody = stripHtml(htmlBody);
      }
    }

    // Only include html_body if in rich mode and there's content
    const finalHtmlBody = editorMode === 'rich' && htmlBody.trim() ? htmlBody : undefined;

    onSubmit({
      name,
      subject,
      body: finalBody,
      html_body: finalHtmlBody,
      cc: cc.trim() || undefined,
      prefer_xarf: preferXarf,
      xarf_reporter_ref_template: xarfReporterRefTemplate.trim() || undefined,
    });
  };

  // Available template variables
  const templateVariables = [
    { name: '{{ case_id }}', description: 'Case ID' },
    { name: '{{ target_url }}', description: 'Target URL' },
    { name: '{{ domain }}', description: 'Domain name' },
    { name: '{{ ip }}', description: 'IP address' },
    { name: '{{ organization }}', description: 'Organization name' },
    { name: '{{ reporter_email }}', description: 'Reporter email' },
    { name: '{{ reported_date }}', description: 'Report date' },
  ];

  const insertVariable = (variable: string) => {
    // Insert at cursor position or append to the end
    const textarea = document.getElementById('template-body') as HTMLTextAreaElement;
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const newValue = body.substring(0, start) + variable + body.substring(end);
      setBody(newValue);
      // Set cursor position after inserted variable
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + variable.length;
        textarea.focus();
      }, 0);
    } else {
      setBody(body + variable);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>{isEditing ? 'Edit Email Template' : 'Create Email Template'}</CardTitle>
          <CardDescription>
            {isEditing
              ? 'Modify the email template settings'
              : 'Create a new email template for abuse reports'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="template-name">Name *</Label>
              <Input
                id="template-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Standard Takedown Notice"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-subject">Subject *</Label>
              <Input
                id="template-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g., [Case-ID: {{ case_id }}] URGENT: Phishing Takedown Request - {{ domain }}"
                required
              />
              <p className="text-xs text-muted-foreground">
                Use template variables to dynamically insert values
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-cc">CC (Carbon Copy)</Label>
              <Input
                id="template-cc"
                type="text"
                value={cc}
                onChange={(e) => setCc(e.target.value)}
                placeholder="e.g., manager@example.com, team@example.com"
              />
              <p className="text-xs text-muted-foreground">
                Optional comma-separated email addresses to receive a copy of all emails sent using this template
              </p>
            </div>

            {/* XARF Format Configuration */}
            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center justify-between">
                <Label htmlFor="prefer-xarf" className="cursor-pointer">XARF Format Support</Label>
                <Switch
                  id="prefer-xarf"
                  checked={preferXarf}
                  onCheckedChange={(checked) => setPreferXarf(checked)}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                XARF (eXtended Abuse Reporting Format) is a JSON-based standard used by providers like DigitalOcean Abuse.
                When enabled, a XARF JSON file will be attached to abuse report emails.
              </p>
              {preferXarf && (
                <div className="space-y-2">
                  <Label htmlFor="xarf-reporter-ref">Reporter Reference Template (Optional)</Label>
                  <Input
                    id="xarf-reporter-ref"
                    type="text"
                    value={xarfReporterRefTemplate}
                    onChange={(e) => setXarfReporterRefTemplate(e.target.value)}
                    placeholder="e.g., {{ case_id }}"
                  />
                  <p className="text-xs text-muted-foreground">
                    Optional reference template for the XARF reporter field. Use template variables like {'{{ case_id }}'}.
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Body *</Label>
              <Tabs value={editorMode} onValueChange={(v) => setEditorMode(v as 'plain' | 'rich')} className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="rich">Rich Text Editor</TabsTrigger>
                  <TabsTrigger value="plain">Plain Text</TabsTrigger>
                </TabsList>
                <TabsContent value="rich" className="mt-2">
                  <RichTextEditor
                    content={htmlBody}
                    onChange={setHtmlBody}
                    placeholder="Enter email content in rich text format..."
                    templateVariables={templateVariables}
                  />
                  <p className="text-xs text-muted-foreground mt-2">
                    Rich text format with HTML. Use toolbar buttons for formatting and template variable buttons to insert placeholders.
                  </p>
                </TabsContent>
                <TabsContent value="plain" className="mt-2 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {templateVariables.map((v) => (
                        <button
                          key={v.name}
                          type="button"
                          onClick={() => insertVariable(v.name)}
                          className="text-xs"
                        >
                          <Badge variant="outline" className="cursor-pointer hover:bg-accent">
                            + {v.name}
                          </Badge>
                        </button>
                      ))}
                    </div>
                  </div>
                  <Textarea
                    id="template-body"
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder={`IMPORTANT: ABUSE NOTICE - CASE ID: {{ case_id }}

{{ organization }} Abuse Team,

We are writing to report active phishing infrastructure hosted on your network.

**Phishing URL:** {{ target_url }}
**Domain:** {{ domain }}
**IP Address:** {{ ip }}
**Reported:** {{ reported_date }}

...`}
                    rows={15}
                    className="font-mono text-sm"
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Plain text format (fallback for email clients that don't support HTML). Click on a variable above to insert it.
                  </p>
                </TabsContent>
              </Tabs>
            </div>

            <div className="flex gap-2 justify-end pt-4">
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              {/* Check body for plain mode, htmlBody for rich mode */}
              <Button type="submit" disabled={
                !name.trim() ||
                !subject.trim() ||
                (editorMode === 'rich' ? !htmlBody.trim() : !body.trim())
              }>
                {isEditing ? 'Save Changes' : 'Create Template'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
