import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Pencil, AlertCircle } from 'lucide-react';

interface BrandEditModalProps {
  isOpen: boolean;
  brandOptions: string[];
  editingBrand: string;
  isUpdatingBrand: boolean;
  actionError: string | null;
  onClose: () => void;
  onUpdate: () => void;
  onBrandChange: (brand: string) => void;
}

export function BrandEditModal({
  isOpen,
  brandOptions,
  editingBrand,
  isUpdatingBrand,
  actionError,
  onClose,
  onUpdate,
  onBrandChange,
}: BrandEditModalProps) {
  if (!isOpen) return null;

  const isUpdateDisabled = isUpdatingBrand || !editingBrand;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Pencil className="h-5 w-5 text-blue-500" />
            Edit Brand Impacted
          </CardTitle>
          <CardDescription>
            Select the brand being impersonated by this phishing site
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="brand-select">Brand Impacted</Label>
            <select
              id="brand-select"
              className="w-full px-3 py-2 border rounded-md"
              value={editingBrand}
              onChange={(e) => onBrandChange(e.target.value)}
            >
              <option value="">-- Select a brand --</option>
              {brandOptions.map((brand) => (
                <option key={brand} value={brand}>
                  {brand}
                </option>
              ))}
            </select>
          </div>
          {actionError && (
            <p className="text-sm text-destructive flex items-center gap-1">
              <AlertCircle className="h-4 w-4" />
              {actionError}
            </p>
          )}
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={isUpdatingBrand}
            >
              Cancel
            </Button>
            <Button onClick={onUpdate} disabled={isUpdateDisabled}>
              {isUpdatingBrand ? 'Updating...' : 'Update Brand'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
