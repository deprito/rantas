'use client';

import { useState, useEffect } from 'react';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';
import { Permission } from '@/types/auth';
import { api, BlacklistSource, WhitelistEntry } from '@/lib/api';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Ban,
  Plus,
  Trash2,
  RefreshCw,
  Shield,
  CheckCircle,
  XCircle,
  Globe,
  FileText,
  Cloud,
  Edit,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export function BlacklistManagementContent() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission(Permission.BLACKLIST_MANAGE);
  const canView = hasPermission(Permission.BLACKLIST_VIEW);

  const [sources, setSources] = useState<BlacklistSource[]>([]);
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);

  // Add source dialog
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const [newSource, setNewSource] = useState({
    name: '',
    source_type: 'manual' as 'local' | 'remote' | 'manual',
    url: '',
    file_path: '',
    threat_category: '',
    sync_interval_hours: 24,
    is_active: true,
  });

  // Add domain dialog
  const [addDomainOpen, setAddDomainOpen] = useState(false);
  const [newDomain, setNewDomain] = useState({
    domain: '',
    threat_category: '',
    is_wildcard: false,
  });

  // Add whitelist entry dialog
  const [addWhitelistOpen, setAddWhitelistOpen] = useState(false);
  const [newWhitelistEntry, setNewWhitelistEntry] = useState({
    domain: '',
    reason: '',
  });

  const [notification, setNotification] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sourcesData, whitelistData] = await Promise.all([
        api.getBlacklistSources(),
        api.getWhitelist(),
      ]);
      setSources(sourcesData);
      setWhitelist(whitelistData.entries);
    } catch (error) {
      showNotification('error', 'Failed to load blacklist data');
    } finally {
      setLoading(false);
    }
  };

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000);
  };

  const handleAddSource = async () => {
    if (!newSource.name) return;

    try {
      await api.createBlacklistSource(newSource);
      setAddSourceOpen(false);
      setNewSource({
        name: '',
        source_type: 'manual',
        url: '',
        file_path: '',
        threat_category: '',
        sync_interval_hours: 24,
        is_active: true,
      });
      showNotification('success', 'Blacklist source created');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to create source');
    }
  };

  const handleDeleteSource = async (id: string) => {
    if (!confirm('Are you sure you want to delete this source?')) return;

    try {
      await api.deleteBlacklistSource(id);
      showNotification('success', 'Source deleted');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to delete source');
    }
  };

  const handleSyncSource = async (id: string) => {
    setSyncing(id);
    try {
      await api.syncBlacklistSource(id);
      showNotification('success', 'Sync task started');
    } catch (error) {
      showNotification('error', 'Failed to start sync');
    } finally {
      setSyncing(null);
    }
  };

  const handleToggleActive = async (source: BlacklistSource) => {
    try {
      await api.updateBlacklistSource(source.id, {
        is_active: !source.is_active,
      });
      showNotification('success', 'Source updated');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to update source');
    }
  };

  const handleAddDomain = async () => {
    if (!newDomain.domain) return;

    try {
      await api.addBlacklistDomain(
        newDomain.domain,
        newDomain.threat_category || undefined,
        newDomain.is_wildcard,
      );
      setAddDomainOpen(false);
      setNewDomain({ domain: '', threat_category: '', is_wildcard: false });
      showNotification('success', 'Domain added to blacklist');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to add domain');
    }
  };

  const handleRemoveDomain = async (domain: string) => {
    if (!confirm(`Remove ${domain} from blacklist?`)) return;

    try {
      await api.removeBlacklistDomain(domain);
      showNotification('success', 'Domain removed from blacklist');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to remove domain');
    }
  };

  const handleAddWhitelist = async () => {
    if (!newWhitelistEntry.domain) return;

    try {
      await api.addToWhitelist(
        newWhitelistEntry.domain,
        newWhitelistEntry.reason || undefined,
      );
      setAddWhitelistOpen(false);
      setNewWhitelistEntry({ domain: '', reason: '' });
      showNotification('success', 'Domain added to whitelist');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to add to whitelist');
    }
  };

  const handleRemoveWhitelist = async (id: string, domain: string) => {
    if (!confirm(`Remove ${domain} from whitelist?`)) return;

    try {
      await api.removeFromWhitelist(id);
      showNotification('success', 'Domain removed from whitelist');
      loadData();
    } catch (error) {
      showNotification('error', 'Failed to remove from whitelist');
    }
  };

  const getSourceTypeIcon = (type: string) => {
    switch (type) {
      case 'local':
        return <FileText className="h-4 w-4" />;
      case 'remote':
        return <Cloud className="h-4 w-4" />;
      case 'manual':
        return <Edit className="h-4 w-4" />;
      default:
        return <Globe className="h-4 w-4" />;
    }
  };

  const getSourceTypeLabel = (type: string) => {
    switch (type) {
      case 'local':
        return 'Local File';
      case 'remote':
        return 'Remote URL';
      case 'manual':
        return 'Manual Entry';
      default:
        return type;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Notification */}
      {notification && (
        <div
          className={`p-4 rounded-lg flex items-center gap-2 ${
            notification.type === 'success'
              ? 'bg-green-50 dark:bg-green-950/20 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-900'
              : 'bg-red-50 dark:bg-red-950/20 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-900'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <AlertCircle className="h-5 w-5" />
          )}
          <p className="text-sm">{notification.message}</p>
        </div>
      )}

      <Tabs defaultValue="sources" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="sources">Blacklist Sources</TabsTrigger>
          <TabsTrigger value="whitelist">Whitelist</TabsTrigger>
        </TabsList>

        {/* Blacklist Sources Tab */}
        <TabsContent value="sources" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Ban className="h-5 w-5" />
                    Blacklist Sources
                  </CardTitle>
                  <CardDescription>
                    Manage domain blacklist sources for pre-filtering submissions
                  </CardDescription>
                </div>
                {canManage && (
                  <Dialog open={addSourceOpen} onOpenChange={setAddSourceOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        Add Source
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Add Blacklist Source</DialogTitle>
                        <DialogDescription>
                          Add a new source for blacklist domains
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="source-name">Name</Label>
                          <Input
                            id="source-name"
                            value={newSource.name}
                            onChange={(e) =>
                              setNewSource({ ...newSource, name: e.target.value })
                            }
                            placeholder="e.g., PhishTank Feed"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="source-type">Source Type</Label>
                          <Select
                            value={newSource.source_type}
                            onValueChange={(value: any) =>
                              setNewSource({ ...newSource, source_type: value })
                            }
                          >
                            <SelectTrigger id="source-type">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="manual">Manual Entry</SelectItem>
                              <SelectItem value="local">Local File</SelectItem>
                              <SelectItem value="remote">Remote URL</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {newSource.source_type === 'remote' && (
                          <div className="space-y-2">
                            <Label htmlFor="source-url">URL</Label>
                            <Input
                              id="source-url"
                              value={newSource.url}
                              onChange={(e) =>
                                setNewSource({ ...newSource, url: e.target.value })
                              }
                              placeholder="https://example.com/blacklist.txt"
                            />
                          </div>
                        )}
                        {newSource.source_type === 'local' && (
                          <div className="space-y-2">
                            <Label htmlFor="source-path">File Path</Label>
                            <Input
                              id="source-path"
                              value={newSource.file_path}
                              onChange={(e) =>
                                setNewSource({ ...newSource, file_path: e.target.value })
                              }
                              placeholder="/app/data/blacklist.txt"
                            />
                          </div>
                        )}
                        <div className="space-y-2">
                          <Label htmlFor="threat-category">Threat Category (Optional)</Label>
                          <Input
                            id="threat-category"
                            value={newSource.threat_category}
                            onChange={(e) =>
                              setNewSource({ ...newSource, threat_category: e.target.value })
                            }
                            placeholder="e.g., phishing, malware"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="sync-interval">Sync Interval (Hours)</Label>
                          <Input
                            id="sync-interval"
                            type="number"
                            min={1}
                            max={168}
                            value={newSource.sync_interval_hours}
                            onChange={(e) =>
                              setNewSource({
                                ...newSource,
                                sync_interval_hours: parseInt(e.target.value) || 24,
                              })
                            }
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setAddSourceOpen(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleAddSource}>Create Source</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {sources.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>No blacklist sources configured</p>
                  <p className="text-sm">
                    Add a source to start filtering domains
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Location</TableHead>
                      <TableHead>Entries</TableHead>
                      <TableHead>Last Synced</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sources.map((source) => (
                      <TableRow key={source.id}>
                        <TableCell className="font-medium">{source.name}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getSourceTypeIcon(source.source_type)}
                            <span className="text-sm">
                              {getSourceTypeLabel(source.source_type)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {source.source_type === 'remote'
                            ? source.url
                            : source.source_type === 'local'
                            ? source.file_path
                            : '-'}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{source.entry_count}</Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {source.last_synced_at
                            ? new Date(source.last_synced_at).toLocaleString()
                            : 'Never'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {source.is_active ? (
                              <Badge className="bg-green-600">Active</Badge>
                            ) : (
                              <Badge variant="secondary">Inactive</Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            {canManage && source.source_type !== 'manual' && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSyncSource(source.id)}
                                disabled={syncing === source.id}
                              >
                                {syncing === source.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <RefreshCw className="h-4 w-4" />
                                )}
                              </Button>
                            )}
                            {canManage && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleToggleActive(source)}
                              >
                                {source.is_active ? (
                                  <XCircle className="h-4 w-4 text-red-500" />
                                ) : (
                                  <CheckCircle className="h-4 w-4 text-green-500" />
                                )}
                              </Button>
                            )}
                            {canManage && (
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleDeleteSource(source.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Manual Domain Entry */}
          {canManage && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Add Domain Manually</CardTitle>
                <CardDescription>
                  Add a specific domain to the blacklist immediately
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-4">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="manual-domain">Domain</Label>
                    <Input
                      id="manual-domain"
                      value={newDomain.domain}
                      onChange={(e) =>
                        setNewDomain({ ...newDomain, domain: e.target.value })
                      }
                      placeholder="e.g., malicious-site.com or *.example.com"
                    />
                  </div>
                  <div className="w-40 space-y-2">
                    <Label htmlFor="domain-category">Category</Label>
                    <Input
                      id="domain-category"
                      value={newDomain.threat_category}
                      onChange={(e) =>
                        setNewDomain({ ...newDomain, threat_category: e.target.value })
                      }
                      placeholder="phishing"
                    />
                  </div>
                  <div className="flex items-center space-x-2 pb-2">
                    <Switch
                      id="wildcard"
                      checked={newDomain.is_wildcard}
                      onCheckedChange={(checked) =>
                        setNewDomain({ ...newDomain, is_wildcard: checked })
                      }
                    />
                    <Label htmlFor="wildcard">Wildcard</Label>
                  </div>
                  <Button onClick={handleAddDomain}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Domain
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Whitelist Tab */}
        <TabsContent value="whitelist" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-green-600" />
                    Whitelist
                  </CardTitle>
                  <CardDescription>
                    Domains that override blacklist matches
                  </CardDescription>
                </div>
                {canManage && (
                  <Dialog open={addWhitelistOpen} onOpenChange={setAddWhitelistOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline">
                        <Plus className="h-4 w-4 mr-2" />
                        Add to Whitelist
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Add Domain to Whitelist</DialogTitle>
                        <DialogDescription>
                          Whitelisted domains will never be blocked
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="whitelist-domain">Domain</Label>
                          <Input
                            id="whitelist-domain"
                            value={newWhitelistEntry.domain}
                            onChange={(e) =>
                              setNewWhitelistEntry({
                                ...newWhitelistEntry,
                                domain: e.target.value,
                              })
                            }
                            placeholder="e.g., trusted-site.com"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="whitelist-reason">Reason (Optional)</Label>
                          <Input
                            id="whitelist-reason"
                            value={newWhitelistEntry.reason}
                            onChange={(e) =>
                              setNewWhitelistEntry({
                                ...newWhitelistEntry,
                                reason: e.target.value,
                              })
                            }
                            placeholder="e.g., Legitimate business domain"
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setAddWhitelistOpen(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleAddWhitelist}>Add to Whitelist</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {whitelist.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>No whitelisted domains</p>
                  <p className="text-sm">
                    Add trusted domains to override blacklist matches
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Domain</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Added At</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {whitelist.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="font-medium">{entry.domain}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {entry.reason || '-'}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(entry.added_at).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right">
                          {canManage && (
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() =>
                                handleRemoveWhitelist(entry.id, entry.domain)
                              }
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function BlacklistManagementPage() {
  return (
    <ProtectedRoute>
      <BlacklistManagementContent />
    </ProtectedRoute>
  );
}
