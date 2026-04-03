'use client';

import { useState, useEffect } from 'react';
import { Role, RoleCreate, RoleUpdate } from '@/types/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { PermissionMultiSelect } from './PermissionMultiSelect';
import { X } from 'lucide-react';

interface RoleFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: RoleCreate | RoleUpdate) => Promise<void>;
  role?: Role;
  mode: 'create' | 'edit';
  isLoading?: boolean;
  error?: string | null;
}

const DEFAULT_ROLE_NAMES = ['ADMIN', 'CTI_USER', 'REPORTER', 'VIEW_ONLY'];

export function RoleForm({
  isOpen,
  onClose,
  onSubmit,
  role,
  mode,
  isLoading = false,
  error = null,
}: RoleFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    permissions: [] as string[],
  });

  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Reset form when modal opens or role changes
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: role?.name || '',
        description: role?.description || '',
        permissions: role?.permissions || [],
      });
      setValidationErrors({});
    }
  }, [isOpen, role]);

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    // Name validation (only for create mode)
    if (mode === 'create') {
      if (!formData.name.trim()) {
        errors.name = 'Role name is required';
      } else if (formData.name.length < 3) {
        errors.name = 'Role name must be at least 3 characters';
      } else if (!/^[A-Z0-9_]+$/.test(formData.name)) {
        errors.name = 'Role name must be uppercase alphanumeric with underscores only';
      } else if (DEFAULT_ROLE_NAMES.includes(formData.name)) {
        errors.name = 'This role name is reserved for system roles';
      }
    }

    // Description validation
    if (!formData.description.trim()) {
      errors.description = 'Description is required';
    } else if (formData.description.length > 255) {
      errors.description = 'Description must not exceed 255 characters';
    }

    // Permissions validation
    if (formData.permissions.length === 0) {
      errors.permissions = 'At least one permission is required';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    const submitData: RoleCreate | RoleUpdate =
      mode === 'create'
        ? {
            name: formData.name.toUpperCase(),
            description: formData.description,
            permissions: formData.permissions,
          }
        : {
            description: formData.description,
            permissions: formData.permissions,
          };

    await onSubmit(submitData);
  };

  const isDefaultRole = role && DEFAULT_ROLE_NAMES.includes(role.name);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>
                {mode === 'create' ? 'Create New Role' : 'Edit Role'}
              </CardTitle>
              <CardDescription>
                {mode === 'create'
                  ? 'Define a custom role with specific permissions'
                  : 'Modify role permissions and description'}
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              disabled={isLoading}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name field - only for create mode */}
            {mode === 'create' && (
              <div className="space-y-2">
                <Label htmlFor="role-name">
                  Role Name *
                  <span className="text-muted-foreground font-normal ml-2">
                    (uppercase, alphanumeric + underscores)
                  </span>
                </Label>
                <Input
                  id="role-name"
                  value={formData.name}
                  onChange={(e) => {
                    const value = e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '');
                    setFormData({ ...formData, name: value });
                  }}
                  placeholder="e.g., ANALYST"
                  maxLength={50}
                  className="font-mono"
                />
                {validationErrors.name && (
                  <p className="text-sm text-destructive">{validationErrors.name}</p>
                )}
              </div>
            )}

            {/* Show name (disabled) for edit mode */}
            {mode === 'edit' && role && (
              <div className="space-y-2">
                <Label htmlFor="role-name-display">Role Name</Label>
                <Input
                  id="role-name-display"
                  value={role.name}
                  disabled
                  className="font-mono bg-muted"
                />
                {isDefaultRole && (
                  <p className="text-sm text-muted-foreground">
                    This is a default system role. You can modify its permissions and description.
                  </p>
                )}
              </div>
            )}

            {/* Description field */}
            <div className="space-y-2">
              <Label htmlFor="role-description">Description *</Label>
              <Textarea
                id="role-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Describe the purpose of this role..."
                rows={3}
                maxLength={255}
              />
              <div className="flex justify-between">
                {validationErrors.description ? (
                  <p className="text-sm text-destructive">{validationErrors.description}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {formData.description.length}/255 characters
                  </p>
                )}
              </div>
            </div>

            {/* Permissions */}
            <div className="space-y-2">
              <Label>Permissions *</Label>
              <PermissionMultiSelect
                value={formData.permissions}
                onChange={(permissions) =>
                  setFormData({ ...formData, permissions })
                }
              />
            </div>

            {/* Error display */}
            {error && (
              <div className="bg-destructive/10 border border-destructive/20 text-destructive p-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 justify-end pt-4 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isLoading}
              >
                Cancel
              </Button>
              {mode === 'create' && (
                <Button type="submit" disabled={isLoading}>
                  {isLoading ? 'Creating...' : 'Create Role'}
                </Button>
              )}
              {mode === 'edit' && (
                <Button type="submit" disabled={isLoading}>
                  {isLoading ? 'Saving...' : 'Save Changes'}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
