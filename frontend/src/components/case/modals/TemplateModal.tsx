import { useState } from 'react';
import { EmailTemplate } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { X } from 'lucide-react';

interface TemplateModalProps {
  isOpen: boolean;
  isFollowup: boolean;
  emailTemplates: EmailTemplate[];
  brandOptions: string[];
  selectedTemplateId: string;
  selectedBrand: string;
  isSendingReport: boolean;
  onClose: () => void;
  onNext: () => void;
  onTemplateChange: (id: string) => void;
  onBrandChange: (brand: string) => void;
}

export function TemplateModal({
  isOpen,
  isFollowup,
  emailTemplates,
  brandOptions,
  selectedTemplateId,
  selectedBrand,
  isSendingReport,
  onClose,
  onNext,
  onTemplateChange,
  onBrandChange,
}: TemplateModalProps) {
  if (!isOpen) return null;

  const isNextDisabled = isSendingReport || emailTemplates.length === 0 || !selectedBrand;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{isFollowup ? 'Follow-up Report' : 'Select Email Template'}</CardTitle>
          <CardDescription>
            {isFollowup
              ? 'Choose an email template to use for the follow-up report'
              : 'Choose an email template to use for sending the abuse report'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <TemplateSelect
            templates={emailTemplates}
            selectedId={selectedTemplateId}
            onChange={onTemplateChange}
          />
          <BrandSelect
            brands={brandOptions}
            selectedBrand={selectedBrand}
            onChange={onBrandChange}
          />
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onClose}>
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
            <Button onClick={onNext} disabled={isNextDisabled}>
              Next
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function TemplateSelect({
  templates,
  selectedId,
  onChange,
}: {
  templates: EmailTemplate[];
  selectedId: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="template-select">Email Template</Label>
      <select
        id="template-select"
        className="w-full px-3 py-2 border rounded-md"
        value={selectedId}
        onChange={(e) => onChange(e.target.value)}
      >
        {templates.length === 0 ? (
          <option value="">No templates available</option>
        ) : (
          <>
            <option value="">Use default template</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} {t.is_default ? '(Default)' : ''}
              </option>
            ))}
          </>
        )}
      </select>
    </div>
  );
}

function BrandSelect({
  brands,
  selectedBrand,
  onChange,
}: {
  brands: string[];
  selectedBrand: string;
  onChange: (brand: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="brand-select">Brand Impacted *</Label>
      <select
        id="brand-select"
        className="w-full px-3 py-2 border rounded-md"
        value={selectedBrand}
        onChange={(e) => onChange(e.target.value)}
        required
      >
        <option value="">-- Select a brand --</option>
        {brands.map((brand) => (
          <option key={brand} value={brand}>
            {brand}
          </option>
        ))}
      </select>
      <p className="text-xs text-muted-foreground">
        Select the brand being impersonated by this phishing site (required)
      </p>
    </div>
  );
}
