import { useEffect, useRef } from 'react';

interface VersionInfo {
  version: string;
  buildTime: string;
}

/**
 * Hook to check for new deployments and auto-reload the page
 * Checks every 5 minutes for a new version
 */
export function useVersionCheck() {
  const currentVersionRef = useRef<string | null>(null);
  const checkIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkVersion = async () => {
    try {
      // Add cache-busting parameter to ensure we get the latest version
      const response = await fetch(`/version.json?t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache',
        },
      });

      if (!response.ok) {
        console.warn('Failed to fetch version info');
        return;
      }

      const versionInfo: VersionInfo = await response.json();

      // Store the initial version
      if (currentVersionRef.current === null) {
        currentVersionRef.current = versionInfo.version;
        console.log('Current app version:', versionInfo.version);
        return;
      }

      // Check if version has changed
      if (versionInfo.version !== currentVersionRef.current) {
        console.log(
          `New version detected: ${versionInfo.version} (current: ${currentVersionRef.current})`
        );

        // Show a notification before reloading (optional)
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('Update Available', {
            body: 'A new version is available. The page will reload automatically.',
            icon: '/favicon.ico',
          });
        }

        // Wait a bit to let the user see any changes, then reload
        setTimeout(() => {
          console.log('Reloading page to load new version...');
          window.location.reload();
        }, 2000);
      }
    } catch (error) {
      console.error('Error checking version:', error);
    }
  };

  useEffect(() => {
    // Only run in production builds
    if (import.meta.env.DEV) {
      console.log('Version check disabled in development mode');
      return;
    }

    // Initial check
    checkVersion();

    // Check every 5 minutes (300000ms)
    checkIntervalRef.current = setInterval(checkVersion, 5 * 60 * 1000);

    // Cleanup on unmount
    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
      }
    };
  }, []);
}
