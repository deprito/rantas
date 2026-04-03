'use client';

import { useRouter } from 'next/navigation';
import { RoleManagementContent } from '@/components/admin/roles/RoleManagementContent';

export default function RolesPage() {
  const router = useRouter();

  return <RoleManagementContent />;
}

export { RoleManagementContent };
