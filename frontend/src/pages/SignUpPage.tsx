import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../context/AuthContext';
import { Logo } from '../components/Logo';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Mail, ArrowRight, Rocket, Eye, EyeOff } from 'lucide-react';
import { requestMagicLink, register as registerUser } from '../api/auth';

const passwordSignUpSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Must contain an uppercase letter')
    .regex(/[a-z]/, 'Must contain a lowercase letter')
    .regex(/[0-9]/, 'Must contain a number')
    .regex(/[^A-Za-z0-9]/, 'Must contain a special character'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ['confirmPassword'],
});

const magicLinkSchema = z.object({
  email: z.string().email('Invalid email address'),
});

type PasswordSignUpData = z.infer<typeof passwordSignUpSchema>;
type MagicLinkData = z.infer<typeof magicLinkSchema>;

const SignUpPage = () => {
  const { loginWithGoogle, authFeatures, checkAuth } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [useMagicLink, setUseMagicLink] = useState(false);

  const passwordForm = useForm<PasswordSignUpData>({
    resolver: zodResolver(passwordSignUpSchema),
  });

  const magicLinkForm = useForm<MagicLinkData>({
    resolver: zodResolver(magicLinkSchema),
  });

  const onPasswordSubmit = async (data: PasswordSignUpData) => {
    setIsLoading(true);
    setApiError('');

    try {
      const response = await registerUser(data.email, data.password);
      // Save token and redirect
      const { saveToken } = await import('../utils/storage');
      saveToken(response.access_token);
      await checkAuth();
      navigate('/workspaces');
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  const onMagicLinkSubmit = async (data: MagicLinkData) => {
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

  const showMagicLink = authFeatures?.magic_link ?? false;
  const showGoogle = authFeatures?.google ?? false;
  const passwordEnabled = authFeatures?.password ?? true;
  const hasAlternatives = showMagicLink || showGoogle;

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
            Create your account
          </h1>
          <p className="text-muted-foreground">
            Already have an account?{' '}
            <Link to="/signin" className="font-semibold text-primary hover:text-primary/80 transition-colors">
              Sign in
            </Link>
          </p>
        </div>

        {/* Form Card */}
        <div className="rounded-2xl border border-border/50 bg-card/50 p-8">
          {apiError && (
            <Alert variant="destructive" className="rounded-xl border-destructive/20 bg-destructive/5 mb-5">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{apiError}</AlertDescription>
            </Alert>
          )}

          {successMessage && (
            <Alert className="rounded-xl border-emerald-500/20 bg-emerald-500/5 mb-5">
              <Mail className="h-4 w-4 text-emerald-500" />
              <AlertDescription className="text-emerald-600 dark:text-emerald-400">
                {successMessage}
              </AlertDescription>
            </Alert>
          )}

          {/* Password Registration Form (default) */}
          {passwordEnabled && !useMagicLink && (
            <form className="space-y-5" onSubmit={passwordForm.handleSubmit(onPasswordSubmit)}>
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
                  Email address
                </label>
                <input
                  {...passwordForm.register('email')}
                  type="email"
                  placeholder="you@example.com"
                  className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
                />
                {passwordForm.formState.errors.email && (
                  <p className="mt-2 text-sm text-destructive">{passwordForm.formState.errors.email.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-foreground mb-2">
                  Password
                </label>
                <div className="relative">
                  <input
                    {...passwordForm.register('password')}
                    type={passwordVisible ? 'text' : 'password'}
                    placeholder="Create a password"
                    className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setPasswordVisible(!passwordVisible)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {passwordVisible ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                {passwordForm.formState.errors.password && (
                  <p className="mt-2 text-sm text-destructive">{passwordForm.formState.errors.password.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-foreground mb-2">
                  Confirm password
                </label>
                <input
                  {...passwordForm.register('confirmPassword')}
                  type="password"
                  placeholder="Confirm your password"
                  className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
                />
                {passwordForm.formState.errors.confirmPassword && (
                  <p className="mt-2 text-sm text-destructive">{passwordForm.formState.errors.confirmPassword.message}</p>
                )}
              </div>

              <Button
                type="submit"
                variant="gradient"
                disabled={isLoading}
                className="w-full h-12 rounded-xl font-semibold group"
              >
                {isLoading ? (
                  'Creating account...'
                ) : (
                  <>
                    <Rocket className="w-4 h-4 mr-2" />
                    Get Started
                    <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </Button>
            </form>
          )}

          {/* Magic Link Form */}
          {showMagicLink && useMagicLink && (
            <form className="space-y-5" onSubmit={magicLinkForm.handleSubmit(onMagicLinkSubmit)}>
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-foreground mb-2">
                  Email address
                </label>
                <input
                  {...magicLinkForm.register('email')}
                  type="email"
                  placeholder="you@example.com"
                  className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
                />
                {magicLinkForm.formState.errors.email && (
                  <p className="mt-2 text-sm text-destructive">{magicLinkForm.formState.errors.email.message}</p>
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
                    <Rocket className="w-4 h-4 mr-2" />
                    Get Started
                    <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </Button>
            </form>
          )}

          {/* Alternative Methods */}
          {hasAlternatives && (
            <>
              <div className="relative my-8">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border/50"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-card/50 text-muted-foreground">Or continue with</span>
                </div>
              </div>

              <div className="space-y-3">
                {/* Toggle between password and magic link */}
                {showMagicLink && passwordEnabled && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full h-12 rounded-xl border-border/50 hover:bg-muted/50 hover:border-border transition-all duration-300 font-medium"
                    onClick={() => {
                      setUseMagicLink(!useMagicLink);
                      setApiError('');
                      setSuccessMessage('');
                    }}
                  >
                    {useMagicLink ? (
                      <>
                        <Rocket className="w-5 h-5 mr-3" />
                        Sign up with Password
                      </>
                    ) : (
                      <>
                        <Mail className="w-5 h-5 mr-3" />
                        Sign up with Magic Link
                      </>
                    )}
                  </Button>
                )}

                {/* Google Sign Up */}
                {showGoogle && (
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
                    Sign up with Google
                  </Button>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <p className="mt-8 text-center text-sm text-muted-foreground">
          By signing up, you agree to our{' '}
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

export default SignUpPage;
