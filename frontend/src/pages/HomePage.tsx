import { Link, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Logo } from '../components/Logo';
import { Button } from '@/components/ui/button';
import { Bot, GitBranch, Code, Lock, Zap, Users, ArrowRight, Sparkles, MousePointer2 } from 'lucide-react';

const HomePage = () => {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  // Redirect logged-in users to workspaces
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/workspaces');
    }
  }, [isAuthenticated, navigate]);

  const features = [
    {
      icon: <Bot className="h-5 w-5" />,
      title: 'Autonomous Agents',
      description: 'AI agents that write, test, and commit code automatically.',
      gradient: 'from-violet-500 to-purple-500',
    },
    {
      icon: <GitBranch className="h-5 w-5" />,
      title: 'GitHub Native',
      description: 'Seamless integration with repos, issues, and PRs.',
      gradient: 'from-emerald-500 to-teal-500',
    },
    {
      icon: <Code className="h-5 w-5" />,
      title: 'Real-time Collab',
      description: 'Interactive chat with instant code updates.',
      gradient: 'from-blue-500 to-cyan-500',
    },
    {
      icon: <Lock className="h-5 w-5" />,
      title: 'Enterprise Security',
      description: 'Bank-grade encryption and authentication.',
      gradient: 'from-rose-500 to-pink-500',
    },
    {
      icon: <Zap className="h-5 w-5" />,
      title: 'Lightning Fast',
      description: 'Optimized for peak developer experience.',
      gradient: 'from-amber-500 to-orange-500',
    },
    {
      icon: <Users className="h-5 w-5" />,
      title: 'Team Workspaces',
      description: 'Collaborate with role-based access control.',
      gradient: 'from-indigo-500 to-blue-500',
    },
  ];

  return (
    <>
      {/* Hero Section */}
      <section className="pt-8 pb-20 md:pt-16 md:pb-28">
        <div className="text-center">
          {/* Floating badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-8 animate-fade-in">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-primary">AI-Powered Development</span>
          </div>

          {/* Logo */}
          <div className="flex justify-center mb-10">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-primary/30 to-accent/30 rounded-3xl blur-2xl scale-150 animate-pulse" style={{ animationDuration: '4s' }} />
              <div className="relative p-6 rounded-3xl bg-gradient-to-br from-card to-card/50 border border-border/50 shadow-2xl">
                <Logo size="xl" showText={false} />
              </div>
            </div>
          </div>

          {/* Headline */}
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-foreground tracking-tight mb-6">
            Build Faster with
            <span className="block mt-2 bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
              AI Coding Agents
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-lg md:text-xl text-muted-foreground font-light max-w-2xl mx-auto mb-12 leading-relaxed">
            Transform GitHub issues into production code. Autonomous agents that understand your codebase and ship features while you sleep.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            {isAuthenticated ? (
              <div className="flex flex-col items-center gap-4">
                <p className="text-lg text-foreground">
                  Welcome back, <span className="font-semibold text-primary">{user?.username}</span>
                </p>
                <Button
                  size="lg"
                  variant="gradient"
                  onClick={() => navigate('/workspaces')}
                  className="h-14 px-8 rounded-2xl text-base font-semibold group"
                >
                  Go to Workspaces
                  <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                </Button>
              </div>
            ) : (
              <>
                <Button
                  size="lg"
                  variant="gradient"
                  onClick={() => navigate('/signin')}
                  className="h-14 px-8 rounded-2xl text-base font-semibold group"
                >
                  <MousePointer2 className="w-5 h-5 mr-2" />
                  Get Started Free
                  <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  onClick={() => navigate('/signin')}
                  className="h-14 px-8 rounded-2xl text-base font-medium border-border/50 hover:bg-muted/50 hover:border-border transition-all duration-300"
                >
                  Sign In
                </Button>
              </>
            )}
          </div>

          {/* Social proof */}
          <div className="mt-12 flex items-center justify-center gap-8 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="flex -space-x-2">
                {[
                    { from: 'from-violet-500', to: 'to-purple-600' },
                    { from: 'from-cyan-400', to: 'to-blue-500' },
                    { from: 'from-amber-400', to: 'to-orange-500' },
                    { from: 'from-emerald-400', to: 'to-teal-500' },
                  ].map((gradient, i) => (
                    <div key={i} className={`w-8 h-8 rounded-full bg-gradient-to-br ${gradient.from} ${gradient.to} border-2 border-background`} />
                  ))}
              </div>
              <span>1,000+ developers</span>
            </div>
            <div className="hidden sm:block w-px h-6 bg-border" />
            <div className="hidden sm:flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <svg key={i} className="w-4 h-4 text-amber-400 fill-current" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
              <span className="ml-1">4.9/5 rating</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 md:py-28">
        <div className="text-center mb-16">
          <span className="text-sm font-semibold text-primary uppercase tracking-widest">Features</span>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-4 tracking-tight">
            Everything you need to ship faster
          </h2>
          <p className="text-lg text-muted-foreground mt-4 max-w-xl mx-auto font-light">
            Powerful tools designed for modern development workflows
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((feature, index) => (
            <div
              key={index}
              className="group relative p-6 rounded-2xl bg-card/50 border border-border/50 hover:border-border hover:bg-card transition-all duration-300 hover:shadow-xl"
            >
              <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${feature.gradient} shadow-lg mb-5`}>
                <span className="text-white">{feature.icon}</span>
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2 group-hover:text-primary transition-colors">
                {feature.title}
              </h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      {!isAuthenticated && (
        <section className="py-20 md:py-28">
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary/10 via-card to-accent/10 border border-border/50 p-12 md:p-16 text-center">
            <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-primary/20 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-gradient-to-tr from-accent/20 to-transparent rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />

            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-4">
                Ready to transform your workflow?
              </h2>
              <p className="text-lg text-muted-foreground font-light max-w-xl mx-auto mb-10">
                Join thousands of developers shipping faster with AI-powered coding agents.
              </p>
              <Button
                size="lg"
                variant="gradient"
                onClick={() => navigate('/signin')}
                className="h-14 px-10 rounded-2xl text-base font-semibold group"
              >
                Start Building Today
                <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
            </div>
          </div>
        </section>
      )}

      {/* Footer spacing */}
      <div className="h-12" />
    </>
  );
};

export default HomePage;
