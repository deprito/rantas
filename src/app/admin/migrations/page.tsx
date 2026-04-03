'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
    Database,
    RefreshCw,
    ArrowUp,
    ArrowDown,
    CheckCircle2,
    AlertCircle,
    Clock,
    AlertTriangle,
} from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface MigrationInfo {
    revision: string;
    description: string;
    is_head: boolean;
    is_current: boolean;
}

interface MigrationStatus {
    current_revision: string | null;
    head_revision: string | null;
    is_up_to_date: boolean;
    pending_count: number;
    migrations: MigrationInfo[];
}

interface MigrationResult {
    success: boolean;
    message: string;
    output: string;
    from_revision: string | null;
    to_revision: string | null;
}

function MigrationsManagementContent() {
    const [status, setStatus] = useState<MigrationStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isUpgrading, setIsUpgrading] = useState(false);
    const [isDowngrading, setIsDowngrading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [lastResult, setLastResult] = useState<MigrationResult | null>(null);
    const [showConfirmDowngrade, setShowConfirmDowngrade] = useState(false);

    useEffect(() => {
        loadStatus();
    }, []);

    const loadStatus = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_URL}/admin/migrations`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('phishtrack_token')}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to load migration status');
            }

            const data = await response.json();
            setStatus(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load migration status');
        } finally {
            setIsLoading(false);
        }
    };

    const handleUpgrade = async () => {
        setIsUpgrading(true);
        setError(null);
        setSuccess(null);
        setLastResult(null);

        try {
            const response = await fetch(`${API_URL}/admin/migrations/upgrade`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('phishtrack_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ revision: 'head' }),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Migration failed');
            }

            setLastResult(result);
            setSuccess(result.message);
            await loadStatus();
            setTimeout(() => setSuccess(null), 5000);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Migration failed');
        } finally {
            setIsUpgrading(false);
        }
    };

    const handleDowngrade = async () => {
        setShowConfirmDowngrade(false);
        setIsDowngrading(true);
        setError(null);
        setSuccess(null);
        setLastResult(null);

        try {
            const response = await fetch(`${API_URL}/admin/migrations/downgrade`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('phishtrack_token')}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ revision: '-1' }),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Downgrade failed');
            }

            setLastResult(result);
            setSuccess(result.message);
            await loadStatus();
            setTimeout(() => setSuccess(null), 5000);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Downgrade failed');
        } finally {
            setIsDowngrading(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-16">
                <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        <Database className="h-6 w-6" />
                        Database Migrations
                    </h2>
                    <p className="text-muted-foreground mt-1">
                        Manage database schema migrations
                    </p>
                </div>
                <Button variant="outline" onClick={loadStatus} disabled={isLoading}>
                    <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </div>

            {/* Status Badge */}
            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-muted-foreground">Current Status</p>
                            <p className="text-lg font-semibold font-mono">
                                {status?.current_revision || 'No migrations applied'}
                            </p>
                        </div>
                        {status?.is_up_to_date ? (
                            <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/30">
                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                Up to Date
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600 border-yellow-500/30">
                                <Clock className="h-3 w-3 mr-1" />
                                {status?.pending_count || 0} Pending
                            </Badge>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Messages */}
            {error && (
                <div className="mb-4 bg-destructive/10 border border-destructive/20 text-destructive p-4 rounded-lg flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    {error}
                </div>
            )}

            {success && (
                <div className="mb-4 bg-green-500/10 border border-green-500/20 text-green-600 p-4 rounded-lg flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                    {success}
                </div>
            )}

            {/* Actions */}
            <Card className="mb-6">
                <CardHeader>
                    <CardTitle>Migration Actions</CardTitle>
                    <CardDescription>
                        Apply or rollback database migrations
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex gap-4">
                        <Button
                            onClick={handleUpgrade}
                            disabled={isUpgrading || isDowngrading || status?.is_up_to_date}
                            className="flex-1"
                        >
                            <ArrowUp className={`h-4 w-4 mr-2 ${isUpgrading ? 'animate-bounce' : ''}`} />
                            {isUpgrading ? 'Applying...' : 'Apply Migrations'}
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => setShowConfirmDowngrade(true)}
                            disabled={isUpgrading || isDowngrading || !status?.current_revision}
                            className="flex-1"
                        >
                            <ArrowDown className={`h-4 w-4 mr-2 ${isDowngrading ? 'animate-bounce' : ''}`} />
                            {isDowngrading ? 'Rolling back...' : 'Rollback'}
                        </Button>
                    </div>

                    {status?.is_up_to_date && (
                        <p className="text-sm text-muted-foreground text-center">
                            Database is up to date. No pending migrations.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Last Result */}
            {lastResult && (
                <Card className="mb-6">
                    <CardHeader>
                        <CardTitle className="text-sm">Last Operation Output</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <pre className="bg-muted p-4 rounded-lg text-xs overflow-x-auto font-mono">
                            {lastResult.output || 'No output'}
                        </pre>
                    </CardContent>
                </Card>
            )}

            {/* Migration History */}
            <Card>
                <CardHeader>
                    <CardTitle>Migration History</CardTitle>
                    <CardDescription>
                        List of all available migrations
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {status?.migrations && status.migrations.length > 0 ? (
                        <div className="space-y-2">
                            {status.migrations.map((migration, index) => (
                                <div
                                    key={migration.revision}
                                    className={`flex items-center justify-between p-3 rounded-lg border ${migration.is_current
                                        ? 'bg-primary/5 border-primary/30'
                                        : 'bg-muted/50 border-border'
                                        }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`w-2 h-2 rounded-full ${migration.is_current ? 'bg-primary' : 'bg-muted-foreground/30'
                                            }`} />
                                        <div>
                                            <p className="font-mono text-sm font-medium">
                                                {migration.revision}
                                            </p>
                                            {migration.description && (
                                                <p className="text-xs text-muted-foreground">
                                                    {migration.description}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {migration.is_current && (
                                            <Badge variant="outline" className="text-xs">
                                                Current
                                            </Badge>
                                        )}
                                        {migration.is_head && (
                                            <Badge variant="secondary" className="text-xs">
                                                Head
                                            </Badge>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No migrations found</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Confirm Downgrade Modal */}
            {showConfirmDowngrade && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <Card className="w-full max-w-md">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-yellow-600">
                                <AlertTriangle className="h-5 w-5" />
                                Confirm Rollback
                            </CardTitle>
                            <CardDescription>
                                This action may result in data loss and cannot be undone.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="bg-yellow-500/10 border border-yellow-500/20 p-4 rounded-lg">
                                <p className="text-sm text-yellow-700">
                                    Rolling back will revert the database to the previous migration.
                                    Any data added by the current migration may be lost.
                                </p>
                            </div>
                            <div className="flex gap-2 justify-end">
                                <Button
                                    variant="outline"
                                    onClick={() => setShowConfirmDowngrade(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    variant="destructive"
                                    onClick={handleDowngrade}
                                >
                                    <ArrowDown className="h-4 w-4 mr-2" />
                                    Confirm Rollback
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}

export { MigrationsManagementContent };

export default function MigrationsPage() {
    const router = useRouter();

    useEffect(() => {
        // Redirect to admin page with migrations tab for consistent UI
        router.replace('/admin?tab=migrations');
    }, [router]);

    return null;
}
