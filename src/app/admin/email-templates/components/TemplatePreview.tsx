'use client';

import { EmailTemplate } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Mail } from 'lucide-react';

interface TemplatePreviewProps {
  template: EmailTemplate;
  onClose: () => void;
}

// Sample data for preview
const sampleData = {
  case_id: '12345678-1234-1234-1234-123456789abc',
  target_url: 'http://example-phishing-site.com/login',
  domain: 'example-phishing-site.com',
  ip: '192.0.2.1',
  organization: 'Hosting Provider',
  reporter_email: 'abuse@example.com',
  reported_date: new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC',
};

function renderTemplate(template: string, data: Record<string, string>): string {
  let rendered = template;
  for (const [key, value] of Object.entries(data)) {
    const variable = `{{ ${key} }}`;
    const variableWithoutBraces = `{${key}}`;
    rendered = rendered.replace(new RegExp(variable, 'g'), value);
    rendered = rendered.replace(new RegExp(variableWithoutBraces, 'g'), value);
  }
  return rendered;
}

export function TemplatePreview({ template, onClose }: TemplatePreviewProps) {
  const renderedSubject = renderTemplate(template.subject, sampleData);
  const renderedBody = renderTemplate(template.body, sampleData);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Email Preview: {template.name}
              </CardTitle>
              <CardDescription>
                Preview with sample data - variables have been replaced with example values
              </CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Subject */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-medium">Subject:</span>
              <Badge variant="outline" className="font-mono text-xs">
                {renderedSubject}
              </Badge>
            </div>
          </div>

          {/* CC */}
          {template.cc && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">CC:</span>
                <Badge variant="outline" className="font-mono text-xs">
                  {template.cc}
                </Badge>
              </div>
            </div>
          )}

          {/* Body */}
          <div>
            <span className="text-sm font-medium mb-2 block">Body:</span>
            <div className="bg-muted p-4 rounded-md">
              <pre className="whitespace-pre-wrap font-sans text-sm text-foreground">
                {renderedBody}
              </pre>
            </div>
          </div>

          {/* Sample Data Reference */}
          <div>
            <span className="text-sm font-medium mb-2 block">Sample Data Used:</span>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {Object.entries(sampleData).map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <span className="font-mono text-muted-foreground">{key}:</span>
                  <span className="font-mono">{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <Button variant="outline" onClick={onClose}>
              Close Preview
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
