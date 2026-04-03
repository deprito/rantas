'use client';

import { useState, useMemo } from 'react';
import { Permission, PermissionCategory } from '@/types/auth';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ChevronDown, ChevronRight, Search, Check } from 'lucide-react';

interface PermissionMultiSelectProps {
  value: string[];
  onChange: (permissions: string[]) => void;
  disabled?: boolean;
}

const PERMISSION_CATEGORIES: PermissionCategory[] = [
  {
    name: 'Case Management',
    permissions: [
      { value: Permission.CASE_VIEW_ANY, label: 'View Any Cases', description: 'View all cases in the system' },
      { value: Permission.CASE_VIEW_OWN, label: 'View Own Cases', description: 'View only own cases' },
      { value: Permission.CASE_CREATE, label: 'Create Cases', description: 'Create new cases' },
      { value: Permission.CASE_UPDATE, label: 'Update Cases', description: 'Edit case details' },
      { value: Permission.CASE_DELETE, label: 'Delete Cases', description: 'Remove cases' },
      { value: Permission.CASE_SEND_REPORT, label: 'Send Reports', description: 'Send abuse reports' },
    ],
  },
  {
    name: 'User Management',
    permissions: [
      { value: Permission.USER_CREATE, label: 'Create Users', description: 'Add new users' },
      { value: Permission.USER_UPDATE, label: 'Update Users', description: 'Edit user details' },
      { value: Permission.USER_DELETE, label: 'Delete Users', description: 'Remove users' },
      { value: Permission.USER_VIEW_ANY, label: 'View Users', description: 'View all users' },
      { value: Permission.USER_RESET_PASSWORD, label: 'Reset Password', description: 'Reset user passwords' },
    ],
  },
  {
    name: 'Role Management',
    permissions: [
      { value: Permission.ROLE_CREATE, label: 'Create Roles', description: 'Create new roles' },
      { value: Permission.ROLE_UPDATE, label: 'Update Roles', description: 'Edit role permissions' },
      { value: Permission.ROLE_DELETE, label: 'Delete Roles', description: 'Remove roles' },
      { value: Permission.ROLE_VIEW, label: 'View Roles', description: 'View all roles' },
    ],
  },
  {
    name: 'System Configuration',
    permissions: [
      { value: Permission.CONFIG_VIEW, label: 'View Config', description: 'View system configuration' },
      { value: Permission.CONFIG_UPDATE, label: 'Update Config', description: 'Modify system configuration' },
      { value: Permission.AUDIT_VIEW, label: 'View Audit Log', description: 'View audit history' },
    ],
  },
  {
    name: 'Email Templates',
    permissions: [
      { value: Permission.EMAIL_TEMPLATE_VIEW, label: 'View Templates', description: 'View email templates' },
      { value: Permission.EMAIL_TEMPLATE_CREATE, label: 'Create Templates', description: 'Create email templates' },
      { value: Permission.EMAIL_TEMPLATE_UPDATE, label: 'Update Templates', description: 'Edit email templates' },
      { value: Permission.EMAIL_TEMPLATE_DELETE, label: 'Delete Templates', description: 'Remove email templates' },
    ],
  },
  {
    name: 'Submissions & Blacklist',
    permissions: [
      { value: Permission.SUBMISSION_VIEW, label: 'View Submissions', description: 'View public submissions' },
      { value: Permission.SUBMISSION_APPROVE, label: 'Approve Submissions', description: 'Approve public submissions' },
      { value: Permission.SUBMISSION_DELETE, label: 'Delete Submissions', description: 'Reject public submissions' },
      { value: Permission.BLACKLIST_VIEW, label: 'View Blacklist', description: 'View blacklist entries' },
      { value: Permission.BLACKLIST_MANAGE, label: 'Manage Blacklist', description: 'Manage blacklist entries' },
    ],
  },
  {
    name: 'Statistics & Reports',
    permissions: [
      { value: Permission.STATS_VIEW, label: 'View Statistics', description: 'View system statistics' },
      { value: Permission.STATS_EXPORT, label: 'Export Data', description: 'Export statistics and reports' },
    ],
  },
  {
    name: 'Evidence',
    permissions: [
      { value: Permission.EVIDENCE_VIEW, label: 'View Evidence', description: 'View evidence files' },
      { value: Permission.EVIDENCE_CREATE, label: 'Create Evidence', description: 'Create evidence records' },
      { value: Permission.EVIDENCE_DELETE, label: 'Delete Evidence', description: 'Delete evidence files' },
    ],
  },
];

export function PermissionMultiSelect({ value, onChange, disabled = false }: PermissionMultiSelectProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set());

  const toggleCategory = (categoryName: string) => {
    const newOpenCategories = new Set(openCategories);
    if (newOpenCategories.has(categoryName)) {
      newOpenCategories.delete(categoryName);
    } else {
      newOpenCategories.add(categoryName);
    }
    setOpenCategories(newOpenCategories);
  };

  const isCategoryFullySelected = (category: PermissionCategory): boolean => {
    return category.permissions.every(p => value.includes(p.value));
  };

  const isCategoryPartiallySelected = (category: PermissionCategory): boolean => {
    return category.permissions.some(p => value.includes(p.value)) && !isCategoryFullySelected(category);
  };

  const handleCategoryToggle = (category: PermissionCategory) => {
    const categoryPermissions = category.permissions.map(p => p.value);
    const isFullySelected = isCategoryFullySelected(category);

    if (isFullySelected) {
      // Deselect all in category
      onChange(value.filter(v => !categoryPermissions.includes(v)));
    } else {
      // Select all in category
      const newPermissions = [...new Set([...value, ...categoryPermissions])];
      onChange(newPermissions);
    }
  };

  const handlePermissionToggle = (permissionValue: string) => {
    if (value.includes(permissionValue)) {
      onChange(value.filter(v => v !== permissionValue));
    } else {
      onChange([...value, permissionValue]);
    }
  };

  // Filter categories and permissions based on search
  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return PERMISSION_CATEGORIES;

    return PERMISSION_CATEGORIES.map(category => ({
      ...category,
      permissions: category.permissions.filter(p =>
        p.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.value.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    })).filter(category => category.permissions.length > 0);
  }, [searchQuery]);

  // Auto-expand categories when searching
  useMemo(() => {
    if (searchQuery.trim()) {
      const allOpen = new Set(filteredCategories.map(c => c.name));
      setOpenCategories(allOpen);
    }
  }, [searchQuery, filteredCategories]);

  return (
    <div className={`space-y-2 ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
      {/* Selected permissions badges */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1 p-2 bg-muted/30 rounded-md min-h-[40px]">
          {value.map(v => {
            const perm = PERMISSION_CATEGORIES.flatMap(c => c.permissions).find(p => p.value === v);
            return (
              <Badge
                key={v}
                variant="secondary"
                className="cursor-pointer hover:bg-destructive/20"
                onClick={() => !disabled && handlePermissionToggle(v)}
              >
                {perm?.label || v}
                <span className="ml-1 text-xs opacity-70">×</span>
              </Badge>
            );
          })}
          <span className="text-sm text-muted-foreground px-2">
            {value.length} permission{value.length !== 1 ? 's' : ''} selected
          </span>
        </div>
      )}

      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search permissions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Categories */}
      <div className="h-64 border rounded-md p-2 overflow-y-auto">
        <div className="space-y-1 pr-4">
          {filteredCategories.map(category => (
            <div key={category.name} className="space-y-1">
              {/* Category header */}
              <button
                type="button"
                onClick={() => toggleCategory(category.name)}
                className="w-full flex items-center justify-between p-2 rounded hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {openCategories.has(category.name) ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="font-medium text-sm">{category.name}</span>
                  <Badge variant="outline" className="text-xs h-5">
                    {category.permissions.filter(p => value.includes(p.value)).length}/{category.permissions.length}
                  </Badge>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCategoryToggle(category);
                  }}
                  className="p-1 rounded hover:bg-muted"
                  title={isCategoryFullySelected(category) ? 'Deselect all' : 'Select all'}
                >
                  <Check
                    className={`h-4 w-4 ${
                      isCategoryFullySelected(category)
                        ? 'text-primary'
                        : isCategoryPartiallySelected(category)
                        ? 'text-primary/50'
                        : 'text-muted-foreground'
                    }`}
                  />
                </button>
              </button>

              {/* Permissions */}
              {openCategories.has(category.name) && (
                <div className="ml-6 space-y-1">
                  {category.permissions.map(permission => (
                    <label
                      key={permission.value}
                      className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-colors ${
                        value.includes(permission.value) ? 'bg-primary/10' : 'hover:bg-muted/30'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={value.includes(permission.value)}
                        onChange={() => handlePermissionToggle(permission.value)}
                        className="mt-0.5"
                        disabled={disabled}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium">{permission.label}</div>
                        <div className="text-xs text-muted-foreground">{permission.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Validation hint */}
      {value.length === 0 && (
        <p className="text-sm text-muted-foreground">At least one permission is required</p>
      )}
    </div>
  );
}
