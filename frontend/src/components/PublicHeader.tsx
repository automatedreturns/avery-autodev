import { useEffect, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Logo } from './Logo';
import { Button } from '@/components/ui/button';
import { ArrowRight, Menu } from 'lucide-react';
import { MobileDrawer } from './MobileDrawer';

export const PublicHeader = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
          scrolled
            ? 'bg-background/60 backdrop-blur-xl border-b border-border/50 shadow-lg shadow-black/5'
            : 'bg-transparent'
        }`}
      >
        <div className="w-full md:w-[85%] lg:w-[75%] max-w-6xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <Link to="/">
              <Logo size="md" showText={true} className="hover:opacity-80 transition-opacity" />
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-8">
              <Link to="/contact" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Contact
              </Link>
            </nav>

            {/* Desktop Auth Buttons */}
            <div className="hidden md:flex items-center gap-3">
              {isAuthenticated ? (
                <Button
                  variant="gradient"
                  onClick={() => navigate('/workspaces')}
                  className="h-10 px-5 rounded-xl"
                >
                  Go to Workspaces
                </Button>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    onClick={() => navigate('/signin')}
                    className="h-10 px-5 rounded-xl text-muted-foreground hover:text-foreground"
                  >
                    Sign In
                  </Button>
                  <Button
                    variant="gradient"
                    onClick={() => navigate('/signup')}
                    className="h-10 px-5 rounded-xl"
                  >
                    Get Started
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </>
              )}
            </div>

            {/* Mobile Hamburger Menu */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden h-10 w-10 min-h-[44px] min-w-[44px]"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-6 w-6" />
            </Button>
          </div>
        </div>
      </header>

      {/* Mobile Navigation Drawer */}
      <MobileDrawer
        isOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        isAuthenticated={isAuthenticated}
      />
    </>
  );
};
