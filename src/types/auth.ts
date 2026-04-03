export type RoleName = 'VIEW_ONLY' | 'REPORTER' | 'CTI_USER' | 'ADMIN';

export interface Role {
  id: string;
  name: RoleName;
  description: string;
  permissions: string[];
  created_at: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  role: Role;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

export interface UserWithPermissions extends User {
  permissions: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserWithPermissions;
}

export interface AuthContextType {
  user: UserWithPermissions | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// Permission strings
export const Permission = {
  CASE_VIEW_ANY: 'case:view_any',
  CASE_VIEW_OWN: 'case:view_own',
  CASE_CREATE: 'case:create',
  CASE_UPDATE: 'case:update',
  CASE_DELETE: 'case:delete',
  CASE_SEND_REPORT: 'case:send_report',
  USER_CREATE: 'user:create',
  USER_UPDATE: 'user:update',
  USER_DELETE: 'user:delete',
  USER_VIEW_ANY: 'user:view_any',
  USER_RESET_PASSWORD: 'user:reset_password',
  ROLE_CREATE: 'role:create',
  ROLE_UPDATE: 'role:update',
  ROLE_DELETE: 'role:delete',
  ROLE_VIEW: 'role:view',
  CONFIG_VIEW: 'config:view',
  CONFIG_UPDATE: 'config:update',
  AUDIT_VIEW: 'audit:view',
  EMAIL_TEMPLATE_VIEW: 'email_template:view',
  EMAIL_TEMPLATE_CREATE: 'email_template:create',
  EMAIL_TEMPLATE_UPDATE: 'email_template:update',
  EMAIL_TEMPLATE_DELETE: 'email_template:delete',
  SELF_CHANGE_PASSWORD: 'self:change_password',
  STATS_VIEW: 'stats:view',
  STATS_EXPORT: 'stats:export',
  SUBMISSION_VIEW: 'submission:view',
  SUBMISSION_APPROVE: 'submission:approve',
  SUBMISSION_DELETE: 'submission:delete',
  BLACKLIST_VIEW: 'blacklist:view',
  BLACKLIST_MANAGE: 'blacklist:manage',
} as const;

export type Permission = typeof Permission[keyof typeof Permission];

export const RoleLabels: Record<RoleName, string> = {
  VIEW_ONLY: 'View Only',
  REPORTER: 'Reporter',
  CTI_USER: 'CTI User',
  ADMIN: 'Administrator',
};

export const RoleDescriptions: Record<RoleName, string> = {
  VIEW_ONLY: 'Can view all cases but cannot modify or create new ones',
  REPORTER: 'Can submit URLs for analysis and view their own cases',
  CTI_USER: 'Can view any cases, submit URLs, and send abuse reports',
  ADMIN: 'Full access including user management and configuration',
};
