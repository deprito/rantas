import { Case } from '@/types/case';
import { InfoCard } from './InfoCard';
import { Globe, Server, Clock } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

interface CaseDomainInfoProps {
  domainInfo: Case['domain_info'] | null;
  abuseContacts: Case['abuse_contacts'];
}

export function CaseDomainInfo({ domainInfo, abuseContacts }: CaseDomainInfoProps) {
  return (
    <>
      {/* Domain Info */}
      {domainInfo ? (
        <div>
          <h3 className="text-sm font-medium mb-3">Domain Intelligence</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <InfoCard
              icon={<Globe className="h-4 w-4" />}
              label="Registrar"
              value={domainInfo.registrar}
            />
            <InfoCard
              icon={<Server className="h-4 w-4" />}
              label="IP Address"
              value={domainInfo.ip}
            />
            <InfoCard
              icon={<Clock className="h-4 w-4" />}
              label="Domain Age"
              value={`${domainInfo.age_days} days`}
            />
            <InfoCard
              icon={<Server className="h-4 w-4" />}
              label="ASN"
              value={domainInfo.asn}
            />
          </div>
          {domainInfo.ns_records.length > 0 && (
            <div className="mt-3">
              <span className="text-xs text-muted-foreground">Nameservers: </span>
              <span className="text-xs font-mono">
                {domainInfo.ns_records.join(', ')}
              </span>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <Skeleton className="h-20 w-full" />
        </div>
      )}

      {/* Abuse Contacts */}
      {abuseContacts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2">Abuse Contacts</h3>
          <div className="flex flex-wrap gap-2">
            {abuseContacts.map((contact, idx) => (
              <ContactBadge key={idx} contact={contact} />
            ))}
          </div>
        </div>
      )}
    </>
  );
}

import { Badge } from '@/components/ui/badge';
import { Mail } from 'lucide-react';

function ContactBadge({ contact }: { contact: { type: string; email: string } }) {
  return (
    <Badge variant="outline" className="gap-1">
      <Mail className="h-3 w-3" />
      {contact.type}: {contact.email}
    </Badge>
  );
}
