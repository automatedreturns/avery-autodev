import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { AlertCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface AlertModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  type?: 'info' | 'error' | 'warning' | 'success';
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  onCancel?: () => void;
  showCancel?: boolean;
}

export default function AlertModal({
  isOpen,
  title,
  message,
  type = 'info',
  confirmText = 'OK',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  showCancel = false,
}: AlertModalProps) {
  const handleConfirm = () => {
    onConfirm();
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    }
  };

  // Get icon and variant based on type
  const getIconAndVariant = () => {
    switch (type) {
      case 'error':
        return {
          icon: <AlertCircle className="h-5 w-5 text-destructive" />,
          variant: 'destructive' as const,
        };
      case 'warning':
        return {
          icon: <AlertTriangle className="h-5 w-5 text-destructive" />,
          variant: 'destructive' as const,
        };
      case 'success':
        return {
          icon: <CheckCircle className="h-5 w-5 text-primary" />,
          variant: 'default' as const,
        };
      default: // info
        return {
          icon: <Info className="h-5 w-5 text-primary" />,
          variant: 'default' as const,
        };
    }
  };

  const { icon, variant } = getIconAndVariant();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleCancel()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-3">
            {icon}
            <DialogTitle>{title}</DialogTitle>
          </div>
        </DialogHeader>
        <DialogDescription className="whitespace-pre-wrap">
          {message}
        </DialogDescription>
        <DialogFooter>
          {showCancel && (
            <Button
              variant="outline"
              onClick={handleCancel}
            >
              {cancelText}
            </Button>
          )}
          <Button
            variant={variant}
            onClick={handleConfirm}
          >
            {confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
