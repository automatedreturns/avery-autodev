import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../context/AuthContext';
import { Logo } from '../components/Logo';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Mail, ArrowRight, Sparkles } from 'lucide-react';
import { requestMagicLink } from '../api/auth';

const signInSchema = z.object({
  email: z.string().email('Invalid email address'),
});

type SignInFormData = z.infer<typeof signInSchema>;

const SignInPage = () => {
  const { loginWithGoogle } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInFormData>({
    resolver: zodResolver(signInSchema),
  });

  const onSubmit = async (data: SignInFormData) => {
    setIsLoading(true);
    setApiError('');
    setSuccessMessage('');

    try {
      const response = await requestMagicLink(data.email);
      setSuccessMessage(response.message);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Failed to send magic link');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="py-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-primary/30 to-accent/30 rounded-2xl blur-xl scale-150 animate-pulse" style={{ animationDuration: '4s' }} />
              <div className="relative p-4 rounded-2xl bg-gradient-to-br from-card to-card/50 border border-border/50 shadow-xl">
                <Logo size="lg" showText={false} />
              </div>
            </div>
          </div>

          <h1 className="text-3xl font-bold text-foreground tracking-tight mb-2">
            Welcome back
          </h1>
          <p className="text-muted-foreground">
            Don't have an account?{' '}
            <Link to="/signup" className="font-semibold text-primary hover:text-primary/80 transition-colors">
              Sign up
            </Link>
          </p>
        </div>

        {/* Form Card */}
        <div className="rounded-2xl border border-border/50 bg-card/50 p-8">
          <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
            {apiError && (
              <Alert variant="destructive" className="rounded-xl border-destructive/20 bg-destructive/5">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{apiError}</AlertDescription>
              </Alert>
            )}

            {successMessage && (
              <Alert className="rounded-xl border-emerald-500/20 bg-emerald-500/5">
                <Mail className="h-4 w-4 text-emerald-500" />
                <AlertDescription className="text-emerald-600 dark:text-emerald-400">
                  {successMessage}
                </AlertDescription>
              </Alert>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
                Email address
              </label>
              <input
                {...register('email')}
                type="email"
                placeholder="you@example.com"
                className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
              />
              {errors.email && (
                <p className="mt-2 text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>

            <Button
              type="submit"
              variant="gradient"
              disabled={isLoading}
              className="w-full h-12 rounded-xl font-semibold group"
            >
              {isLoading ? (
                'Sending...'
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Send Magic Link
                  <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border/50"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-card/50 text-muted-foreground">Or continue with</span>
            </div>
          </div>

          {/* Google Sign In */}
          <Button
            type="button"
            variant="outline"
            className="w-full h-12 rounded-xl border-border/50 hover:bg-muted/50 hover:border-border transition-all duration-300 font-medium"
            onClick={loginWithGoogle}
          >
            <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Sign in with Google
          </Button>
        </div>

        {/* Footer */}
        <p className="mt-8 text-center text-sm text-muted-foreground">
          By signing in, you agree to our{' '}
          <Link to="/terms" className="text-primary hover:text-primary/80 font-medium transition-colors">
            Terms of Service
          </Link>{' '}
          and{' '}
          <Link to="/privacy" className="text-primary hover:text-primary/80 font-medium transition-colors">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
};

export default SignInPage;
