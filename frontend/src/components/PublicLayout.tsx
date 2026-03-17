import { Outlet } from 'react-router-dom';
import { PublicHeader } from './PublicHeader';

export const PublicLayout = () => {
  return (
    <div className="min-h-screen bg-background relative">
      {/* Animated background gradients */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute top-0 -left-1/4 w-1/2 h-1/2 bg-gradient-to-br from-primary/20 via-primary/5 to-transparent rounded-full blur-3xl animate-pulse"
          style={{ animationDuration: '8s' }}
        />
        <div
          className="absolute bottom-0 -right-1/4 w-1/2 h-1/2 bg-gradient-to-tl from-accent/20 via-accent/5 to-transparent rounded-full blur-3xl animate-pulse"
          style={{ animationDuration: '10s', animationDelay: '2s' }}
        />
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1/3 h-1/3 bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10 rounded-full blur-3xl animate-pulse"
          style={{ animationDuration: '12s', animationDelay: '4s' }}
        />
      </div>

      <PublicHeader />

      {/* Main content with padding for fixed header - responsive width */}
      <main className="relative w-full md:w-[85%] lg:w-[75%] max-w-6xl mx-auto px-4 sm:px-6 pt-20 sm:pt-24">
        <Outlet />
      </main>
    </div>
  );
};
