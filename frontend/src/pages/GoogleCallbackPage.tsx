import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { saveToken } from '../utils/storage';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

const GoogleCallbackPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const token = searchParams.get('token');
      const errorParam = searchParams.get('error');

      if (errorParam) {
        const errorMessage = errorParam.replace(/_/g, ' ');
        setError(`Google authentication failed: ${errorMessage}`);
        setTimeout(() => navigate('/signin'), 3000);
        return;
      }

      if (!token) {
        setError('Missing access token');
        setTimeout(() => navigate('/signin'), 3000);
        return;
      }

      try {
        // Save the token to local storage
        saveToken(token);
        // Redirect to workspaces page
        navigate('/workspaces');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Authentication failed');
        setTimeout(() => navigate('/signin'), 3000);
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-card py-8 px-4 shadow sm:rounded-lg sm:px-10 border border-border">
          {error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : (
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              <p className="mt-4 text-foreground">Completing sign in with Google...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GoogleCallbackPage;
