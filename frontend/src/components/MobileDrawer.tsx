import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Logo } from './Logo';
import { ThemeSwitcher } from './ThemeSwitcher';
import { X, ArrowRight, DollarSign, Mail, LogIn, UserPlus, LayoutGrid } from 'lucide-react';

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  isAuthenticated: boolean;
}

export const MobileDrawer = ({ isOpen, onClose, isAuthenticated }: MobileDrawerProps) => {
  const navigate = useNavigate();
  const drawerRef = useRef<HTMLDivElement>(null);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Handle touch swipe to close
  useEffect(() => {
    const drawer = drawerRef.current;
    if (!drawer || !isOpen) return;

    let startX = 0;
    let currentX = 0;

    const handleTouchStart = (e: TouchEvent) => {
      startX = e.touches[0].clientX;
    };

    const handleTouchMove = (e: TouchEvent) => {
      currentX = e.touches[0].clientX;
      const diff = currentX - startX;
      if (diff > 0) {
        drawer.style.transform = `translateX(${diff}px)`;
      }
    };

    const handleTouchEnd = () => {
      const diff = currentX - startX;
      if (diff > 100) {
        onClose();
      }
      drawer.style.transform = '';
      startX = 0;
      currentX = 0;
    };

    drawer.addEventListener('touchstart', handleTouchStart);
    drawer.addEventListener('touchmove', handleTouchMove);
    drawer.addEventListener('touchend', handleTouchEnd);

    return () => {
      drawer.removeEventListener('touchstart', handleTouchStart);
      drawer.removeEventListener('touchmove', handleTouchMove);
      drawer.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isOpen, onClose]);

  const handleNavigation = (path: string) => {
    onClose();
    navigate(path);
  };

  const navLinks = [
    { path: '/pricing', label: 'Pricing', icon: DollarSign },
    { path: '/contact', label: 'Contact', icon: Mail },
  ];

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-50 bg-black/50 backdrop-blur-sm transition-opacity duration-300 md:hidden ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`fixed top-0 right-0 z-50 h-full w-[85%] max-w-sm bg-card border-l border-border shadow-xl transform transition-transform duration-300 ease-out md:hidden ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <Logo size="sm" showText={true} />
          <div className="flex items-center gap-2">
            <ThemeSwitcher />
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-10 w-10 min-h-[44px] min-w-[44px]"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Drawer Content */}
        <nav className="flex flex-col p-4 space-y-2">
          {navLinks.map((link) => (
            <button
              key={link.path}
              onClick={() => handleNavigation(link.path)}
              className="flex items-center gap-3 w-full px-4 py-3 min-h-[48px] text-left text-base font-medium text-foreground hover:bg-muted rounded-lg transition-colors"
            >
              <link.icon className="h-5 w-5 text-muted-foreground" />
              {link.label}
            </button>
          ))}
        </nav>

        {/* Auth Section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border bg-card safe-area-bottom">
          {isAuthenticated ? (
            <Button
              variant="gradient"
              onClick={() => handleNavigation('/workspaces')}
              className="w-full h-12 min-h-[48px] rounded-xl text-base font-medium"
            >
              <LayoutGrid className="w-5 h-5 mr-2" />
              Go to Workspaces
            </Button>
          ) : (
            <div className="space-y-3">
              <Button
                variant="outline"
                onClick={() => handleNavigation('/signin')}
                className="w-full h-12 min-h-[48px] rounded-xl text-base font-medium"
              >
                <LogIn className="w-5 h-5 mr-2" />
                Sign In
              </Button>
              <Button
                variant="gradient"
                onClick={() => handleNavigation('/signup')}
                className="w-full h-12 min-h-[48px] rounded-xl text-base font-medium"
              >
                <UserPlus className="w-5 h-5 mr-2" />
                Get Started
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
