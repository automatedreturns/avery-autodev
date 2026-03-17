import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { verifyMagicLink } from '../api/auth';
import { saveToken } from '../utils/storage';
import { useAuth } from '../context/AuthContext';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

const MagicLinkVerifyPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { checkAuth } = useAuth();
  const [isVerifying, setIsVerifying] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const verifyToken = async () => {
      const token = searchParams.get('token');

      if (!token) {
        setError('Invalid or missing token');
        setIsVerifying(false);
        return;
      }

      try {
        const response = await verifyMagicLink(token);
        saveToken(response.access_token);
        // Update auth context with the new token
        await checkAuth();
        // Redirect to workspaces page
        navigate('/workspaces', { replace: true });
      } catch (error) {
        setError(error instanceof Error ? error.message : 'Failed to verify magic link');
        setIsVerifying(false);
      }
    };

    verifyToken();
  }, [searchParams, navigate, checkAuth]);

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-card py-8 px-4 shadow sm:rounded-lg sm:px-10 border border-border">
          {isVerifying ? (
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary mb-4" />
              <h2 className="text-xl font-semibold text-card-foreground">Verifying your magic link...</h2>
              <p className="mt-2 text-sm text-muted-foreground">Please wait while we sign you in</p>
            </div>
          ) : (
            <div>
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
              <div className="text-center">
                <h2 className="text-xl font-semibold text-card-foreground mb-4">Verification Failed</h2>
                <p className="text-sm text-muted-foreground mb-6">
                  The magic link may have expired or is invalid. Please request a new one.
                </p>
                <Button
                  onClick={() => navigate('/signin')}
                  className="w-full"
                  size="lg"
                >
                  Back to Sign In
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MagicLinkVerifyPage;
