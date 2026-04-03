'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Permission, Role, RoleCreate, RoleUpdate } from '@/types/auth';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  Shield,
  Plus,
  Search,
  RefreshCw,
  Edit,
  Trash2,
  Users as UsersIcon,
  CheckCircle,
  XCircle,
  AlertCircle,
} from 'lucide-react';
import { RoleForm } from './RoleForm';

const DEFAULT_ROLE_NAMES = ['ADMIN', 'CTI_USER', 'REPORTER', 'VIEW_ONLY'];

function RoleManagementContent() {
  const { hasPermission } = useAuth();

  const [roles, setRoles] = useState<Role[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canCreateRole = hasPermission(Permission.ROLE_CREATE);
  const canUpdateRole = hasPermission(Permission.ROLE_UPDATE);
  const canDeleteRole = hasPermission(Permission.ROLE_DELETE);

  useEffect(() => {
    loadRoles();
  }, []);

  // Close modals on ESC key press
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showCreateModal) setShowCreateModal(false);
        if (showEditModal) setShowEditModal(false);
        if (showDeleteConfirm) setShowDeleteConfirm(false);
      }
    };

    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [showCreateModal, showEditModal, showDeleteConfirm]);

  const loadRoles = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const rolesList = await api.listRoles();
      setRoles(rolesList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load roles');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateRole = async (data: RoleCreate | RoleUpdate) => {
    if (!canCreateRole) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await api.createRole(data as RoleCreate);
      setShowCreateModal(false);
      loadRoles();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRole = async (data: RoleCreate | RoleUpdate) => {
    if (!canUpdateRole || !selectedRole) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await api.updateRole(selectedRole.id, data as RoleUpdate);
      setShowEditModal(false);
      setSelectedRole(null);
      loadRoles();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to update role');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!canDeleteRole || !selectedRole) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await api.deleteRole(selectedRole.id);
      setShowDeleteConfirm(false);
      setSelectedRole(null);
      loadRoles();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to delete role');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openEditModal = (role: Role) => {
    setSelectedRole(role);
    setShowEditModal(true);
  };

  const openDeleteConfirm = (role: Role) => {
    setSelectedRole(role);
    setShowDeleteConfirm(true);
  };

  const getRoleBadgeColor = (roleName: string) => {
    switch (roleName) {
      case 'ADMIN':
        return 'bg-red-500';
      case 'CTI_USER':
        return 'bg-blue-500';
      case 'REPORTER':
        return 'bg-green-500';
      case 'VIEW_ONLY':
        return 'bg-gray-500';
      default:
        return 'bg-purple-500';
    }
  };

  const getRoleLabel = (roleName: string) => {
    switch (roleName) {
      case 'ADMIN':
        return 'Administrator';
      case 'CTI_USER':
        return 'CTI User';
      case 'REPORTER':
        return 'Reporter';
      case 'VIEW_ONLY':
        return 'View Only';
      default:
        // Convert SCREAMING_CASE to Title Case
        return roleName
          .split('_')
          .map(word => word.charAt(0) + word.slice(1).toLowerCase())
          .join(' ');
    }
  };

  const isDefaultRole = (roleName: string) => {
    return DEFAULT_ROLE_NAMES.includes(roleName);
  };

  const filteredRoles = roles.filter(
    (role) =>
      role.name.toLowerCase().includes(search.toLowerCase()) ||
      role.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6" />
            Role Management
          </h2>
          <p className="text-muted-foreground mt-1">
            Manage roles and their permissions
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadRoles} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {canCreateRole && (
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Role
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

      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Roles Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Role Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Permissions</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto" />
                  </TableCell>
                </TableRow>
              ) : filteredRoles.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    {search ? 'No roles found matching your search' : 'No roles found'}
                  </TableCell>
                </TableRow>
              ) : (
                filteredRoles.map((role) => (
                  <TableRow key={role.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Badge className={getRoleBadgeColor(role.name)}>
                          {getRoleLabel(role.name)}
                        </Badge>
                        {isDefaultRole(role.name) && (
                          <Badge variant="outline" className="text-xs">
                            Default
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-md truncate">
                      {role.description}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <UsersIcon className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm">{role.permissions.length}</span>
                        {role.permissions.includes('*') && (
                          <Badge variant="secondary" className="ml-1 text-xs">
                            All
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(role.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {canUpdateRole && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditModal(role)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                        )}
                        {canDeleteRole && !isDefaultRole(role.name) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDeleteConfirm(role)}
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

      {/* Create Role Modal */}
      <RoleForm
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setSubmitError(null);
        }}
        onSubmit={handleCreateRole}
        mode="create"
        isLoading={isSubmitting}
        error={submitError}
      />

      {/* Edit Role Modal */}
      <RoleForm
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setSelectedRole(null);
          setSubmitError(null);
        }}
        onSubmit={handleUpdateRole}
        role={selectedRole ?? undefined}
        mode="edit"
        isLoading={isSubmitting}
        error={submitError}
      />

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && selectedRole && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-destructive" />
                Delete Role
              </CardTitle>
              <CardDescription>
                Are you sure you want to delete the role{' '}
                <span className="font-semibold">{selectedRole.name}</span>?
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 rounded-lg p-3">
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  <strong>Warning:</strong> This action cannot be undone. If users are assigned to this role,
                  the deletion will fail.
                </p>
              </div>

              {submitError && (
                <div className="bg-destructive/10 border border-destructive/20 text-destructive p-3 rounded-lg text-sm">
                  {submitError}
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setSelectedRole(null);
                    setSubmitError(null);
                  }}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDeleteRole}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Deleting...' : 'Delete Role'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export { RoleManagementContent };
