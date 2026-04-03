import { Case } from '@/types/case';
import { EmailTemplate } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { AlertCircle, Send, RefreshCw, X, Check } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  isFollowup: boolean;
  case: Case;
  emailTemplates: EmailTemplate[];
  selectedTemplateId: string;
  selectedContacts: Set<string>;
  isSendingReport: boolean;
  onClose: () => void;
  onBack: () => void;
  onSend: () => void;
  onToggleContact: (email: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

export function ConfirmModal({
  isOpen,
  isFollowup,
  case: caze,
  emailTemplates,
  selectedTemplateId,
  selectedContacts,
  isSendingReport,
  onClose,
  onBack,
  onSend,
  onToggleContact,
  onSelectAll,
  onDeselectAll,
}: ConfirmModalProps) {
  if (!isOpen) return null;

  const isSendDisabled = isSendingReport || selectedContacts.size === 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-orange-500" />
            {isFollowup ? 'Send Follow-up' : 'Confirm & Select Recipients'}
          </CardTitle>
          <CardDescription>
            {isFollowup
              ? 'Review the abuse contacts below and select which ones to send the follow-up report to.'
              : 'Review the abuse contacts below and select which ones to send the report to.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ContactSelection
            contacts={caze.abuse_contacts}
            selectedContacts={selectedContacts}
            onToggle={onToggleContact}
            onSelectAll={onSelectAll}
            onDeselectAll={onDeselectAll}
          />
          {selectedContacts.size > 0 && (
            <Summary
              case={caze}
              templates={emailTemplates}
              selectedTemplateId={selectedTemplateId}
              selectedContacts={selectedContacts}
            />
          )}
          <ActionButtons
            isFollowup={isFollowup}
            isSendingReport={isSendingReport}
            isSendDisabled={isSendDisabled}
            selectedCount={selectedContacts.size}
            onBack={onBack}
            onClose={onClose}
            onSend={onSend}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ContactSelection({
  contacts,
  selectedContacts,
  onToggle,
  onSelectAll,
  onDeselectAll,
}: {
  contacts: Case['abuse_contacts'];
  selectedContacts: Set<string>;
  onToggle: (email: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>Select Abuse Contacts</Label>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={onSelectAll}
            className="text-blue-600 hover:underline"
          >
            Select All
          </button>
          <span className="text-muted-foreground">|</span>
          <button
            type="button"
            onClick={onDeselectAll}
            className="text-blue-600 hover:underline"
          >
            Deselect All
          </button>
        </div>
      </div>
      <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
        {contacts.map((contact, idx) => {
          const email = contact.email;
          const isSelected = selectedContacts.has(email);
          return (
            <ContactRow
              key={`${idx}-${email}`}
              email={email}
              type={contact.type}
              isSelected={isSelected}
              onToggle={() => onToggle(email)}
            />
          );
        })}
      </div>
      {selectedContacts.size === 0 && (
        <p className="text-sm text-destructive flex items-center gap-1">
          <AlertCircle className="h-4 w-4" />
          Please select at least one contact
        </p>
      )}
      {selectedContacts.size > 0 && (
        <p className="text-sm text-muted-foreground">
          {selectedContacts.size} contact{selectedContacts.size !== 1 ? 's' : ''} selected
        </p>
      )}
    </div>
  );
}

function ContactRow({
  email,
  type,
  isSelected,
  onToggle,
}: {
  email: string;
  type: string;
  isSelected: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={`flex items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer ${
        isSelected ? 'bg-blue-50/50' : ''
      }`}
    >
      <div className="relative flex items-center">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={onToggle}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500 cursor-pointer"
        />
        {isSelected && (
          <Check className="h-3 w-3 absolute left-0.5 top-0.5 text-white pointer-events-none" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm">{email}</div>
        <div className="text-xs text-muted-foreground capitalize">{type}</div>
      </div>
      <Badge variant="outline" className="shrink-0">
        {type}
      </Badge>
    </label>
  );
}

function Summary({
  case: caze,
  templates,
  selectedTemplateId,
  selectedContacts,
}: {
  case: Case;
  templates: EmailTemplate[];
  selectedTemplateId: string;
  selectedContacts: Set<string>;
}) {
  const templateName = templates.find((t) => t.id === selectedTemplateId)?.name || 'Default';

  return (
    <div className="bg-muted/50 p-3 rounded-md space-y-2">
      <h4 className="text-sm font-medium">Summary</h4>
      <div className="text-sm space-y-1">
        <p>
          <span className="text-muted-foreground">Case:</span> #{caze.id.slice(0, 8)}
        </p>
        <p>
          <span className="text-muted-foreground">Template:</span> {templateName}
        </p>
        <p>
          <span className="text-muted-foreground">Recipients:</span>{' '}
          {Array.from(selectedContacts).join(', ')}
        </p>
      </div>
    </div>
  );
}

function ActionButtons({
  isFollowup,
  isSendingReport,
  isSendDisabled,
  selectedCount,
  onBack,
  onClose,
  onSend,
}: {
  isFollowup: boolean;
  isSendingReport: boolean;
  isSendDisabled: boolean;
  selectedCount: number;
  onBack: () => void;
  onClose: () => void;
  onSend: () => void;
}) {
  return (
    <div className="flex gap-2 justify-end">
      <Button variant="outline" onClick={onBack} disabled={isSendingReport}>
        Back
      </Button>
      <Button variant="outline" onClick={onClose} disabled={isSendingReport}>
        <X className="h-4 w-4 mr-2" />
        Cancel
      </Button>
      <Button onClick={onSend} disabled={isSendDisabled}>
        {isFollowup ? (
          <RefreshCw className={`h-4 w-4 mr-2 ${isSendingReport ? 'animate-spin' : ''}`} />
        ) : (
          <Send className={`h-4 w-4 mr-2 ${isSendingReport ? 'animate-pulse' : ''}`} />
        )}
        {isSendingReport
          ? 'Sending...'
          : `${isFollowup ? 'Send Follow-up' : 'Send'} to ${selectedCount} Recipient${
              selectedCount !== 1 ? 's' : ''
            }`}
      </Button>
    </div>
  );
}
