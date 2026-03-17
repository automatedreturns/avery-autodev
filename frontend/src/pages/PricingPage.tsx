import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Zap, Loader2, HelpCircle, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { createCheckoutSession } from '../api/subscriptions';

interface PricingTier {
  name: string;
  price: number;
  period: string;
  description: string;
  features: string[];
  agentExecutions: number;
  testGenerations: number;
  cta: string;
  popular?: boolean;
  plan: 'free' | 'pro' | 'team';
}

const pricingTiers: PricingTier[] = [
  {
    name: 'Free',
    price: 0,
    period: 'forever',
    description: 'Perfect for trying out Avery',
    features: [
      '3 agent executions/month',
      '5 test generations/month',
      'Community support',
      'Basic automation',
      'GitHub integration',
    ],
    agentExecutions: 3,
    testGenerations: 5,
    cta: 'Current Plan',
    plan: 'free',
  },
  {
    name: 'Pro',
    price: 79,
    period: 'month',
    description: 'For serious developers',
    features: [
      '25 agent executions/month',
      '50 test generations/month',
      'Priority support',
      'Advanced automation',
      'Overage: $4 per execution',
      'Usage analytics',
    ],
    agentExecutions: 25,
    testGenerations: 50,
    cta: 'Upgrade to Pro',
    popular: true,
    plan: 'pro',
  },
  {
    name: 'Team',
    price: 249,
    period: 'month',
    description: 'For teams & organizations',
    features: [
      '100 agent executions/month',
      '200 test generations/month',
      'Dedicated support',
      'Team collaboration',
      'Overage: $3 per execution',
      'Advanced analytics',
      'Custom integrations',
    ],
    agentExecutions: 100,
    testGenerations: 200,
    cta: 'Upgrade to Team',
    plan: 'team',
  },
];

const faqs = [
  {
    question: 'What happens when I exceed my quota?',
    answer:
      'On the Free plan, you\'ll need to wait until your next billing cycle or upgrade to a paid plan. On Pro plan, additional executions are $4 each. On Team plan, additional executions are $3 each. Test generation overages are $0.50 each on all paid plans.',
  },
  {
    question: 'Can I cancel anytime?',
    answer:
      'Yes! You can cancel your subscription at any time. Your subscription will remain active until the end of your current billing period, then you\'ll be downgraded to the free plan.',
  },
  {
    question: 'What payment methods do you accept?',
    answer:
      'We accept all major credit cards (Visa, Mastercard, American Express) through our secure payment processor, Stripe.',
  },
  {
    question: 'Is there a refund policy?',
    answer:
      'We offer a 14-day money-back guarantee. If you\'re not satisfied with your subscription, contact support within 14 days for a full refund.',
  },
  {
    question: 'What counts as an agent execution?',
    answer:
      'An agent execution is counted each time you run the AI coding agent to analyze, refactor, or generate code. Test generations are counted separately.',
  },
];

export default function PricingPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpgrade = async (plan: 'pro' | 'team') => {
    setLoading(plan);
    setError(null);

    try {
      const session = await createCheckoutSession(plan);
      window.location.href = session.checkout_url;
    } catch (err) {
      console.error('Failed to create checkout session:', err);
      setError(err instanceof Error ? err.message : 'Failed to start checkout. Please try again.');
      setLoading(null);
    }
  };

  return (
    <div className="py-8">
      {/* Header */}
      <div className="text-center mb-16">
        <span className="text-sm font-semibold text-primary uppercase tracking-widest">Pricing</span>
        <h1 className="text-4xl md:text-5xl font-bold text-foreground mt-4 tracking-tight">
          Simple, Transparent Pricing
        </h1>
        <p className="text-lg text-muted-foreground mt-4 max-w-2xl mx-auto font-light">
          Choose the plan that fits your needs. Upgrade, downgrade, or cancel anytime.
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <Alert variant="destructive" className="max-w-3xl mx-auto mb-8 rounded-xl border-destructive/20 bg-destructive/5">
          <AlertDescription className="font-medium">{error}</AlertDescription>
        </Alert>
      )}

      {/* Pricing Cards */}
      <div className="grid md:grid-cols-3 gap-6 mb-20">
        {pricingTiers.map((tier) => (
          <div
            key={tier.name}
            className={`relative p-6 rounded-2xl transition-all duration-300 ${
              tier.popular
                ? 'bg-gradient-to-b from-primary/10 to-card border-2 border-primary/50 shadow-xl shadow-primary/10 scale-105 z-10'
                : 'bg-card/50 border border-border/50 hover:border-border hover:shadow-lg'
            }`}
          >
            {tier.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="px-4 py-1 rounded-full bg-gradient-to-r from-primary to-primary/80 text-primary-foreground text-xs font-semibold uppercase tracking-wider shadow-lg">
                  Most Popular
                </span>
              </div>
            )}

            <div className="mb-6">
              <h3 className="text-2xl font-bold text-foreground">{tier.name}</h3>
              <p className="text-sm text-muted-foreground mt-1">{tier.description}</p>
            </div>

            <div className="mb-6">
              <span className="text-5xl font-bold text-foreground">${tier.price}</span>
              <span className="text-muted-foreground ml-2">/{tier.period}</span>
            </div>

            <Button
              onClick={() => {
                if (tier.plan === 'free') {
                  navigate('/workspaces');
                } else {
                  handleUpgrade(tier.plan as 'pro' | 'team');
                }
              }}
              disabled={loading !== null}
              className={`w-full h-12 rounded-xl font-semibold transition-all duration-300 mb-6 ${
                tier.popular
                  ? 'bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 shadow-lg shadow-primary/20'
                  : ''
              }`}
              variant={tier.popular ? 'default' : 'outline'}
            >
              {loading === tier.plan ? (
                <>
                  <Loader2 className="animate-spin mr-2 h-5 w-5" />
                  Loading...
                </>
              ) : (
                tier.cta
              )}
            </Button>

            <ul className="space-y-3">
              {tier.features.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                  <span className="text-sm text-foreground">{feature}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Feature Comparison */}
      <div className="rounded-2xl border border-border/50 bg-card/50 p-8 mb-20">
        <h2 className="text-2xl font-bold text-foreground mb-8 text-center">
          Feature Comparison
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-4 px-4 font-semibold text-foreground">Feature</th>
                <th className="text-center py-4 px-4 font-semibold text-foreground">Free</th>
                <th className="text-center py-4 px-4 font-semibold text-primary">Pro</th>
                <th className="text-center py-4 px-4 font-semibold text-foreground">Team</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border/50">
                <td className="py-4 px-4 text-muted-foreground">Agent Executions/month</td>
                <td className="text-center py-4 px-4 text-foreground font-semibold">3</td>
                <td className="text-center py-4 px-4 text-primary font-semibold">25</td>
                <td className="text-center py-4 px-4 text-foreground font-semibold">100</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-4 px-4 text-muted-foreground">Test Generations/month</td>
                <td className="text-center py-4 px-4 text-foreground font-semibold">5</td>
                <td className="text-center py-4 px-4 text-primary font-semibold">50</td>
                <td className="text-center py-4 px-4 text-foreground font-semibold">200</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-4 px-4 text-muted-foreground">Overage Purchases</td>
                <td className="text-center py-4 px-4">
                  <span className="text-muted-foreground/50">—</span>
                </td>
                <td className="text-center py-4 px-4">
                  <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                </td>
                <td className="text-center py-4 px-4">
                  <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                </td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-4 px-4 text-muted-foreground">Priority Support</td>
                <td className="text-center py-4 px-4">
                  <span className="text-muted-foreground/50">—</span>
                </td>
                <td className="text-center py-4 px-4">
                  <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                </td>
                <td className="text-center py-4 px-4">
                  <Zap className="h-5 w-5 text-primary mx-auto" />
                </td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-4 px-4 text-muted-foreground">Usage Analytics</td>
                <td className="text-center py-4 px-4">
                  <span className="text-muted-foreground/50">—</span>
                </td>
                <td className="text-center py-4 px-4">
                  <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                </td>
                <td className="text-center py-4 px-4">
                  <Zap className="h-5 w-5 text-primary mx-auto" />
                </td>
              </tr>
              <tr>
                <td className="py-4 px-4 text-muted-foreground">Team Collaboration</td>
                <td className="text-center py-4 px-4">
                  <span className="text-muted-foreground/50">—</span>
                </td>
                <td className="text-center py-4 px-4">
                  <span className="text-muted-foreground/50">—</span>
                </td>
                <td className="text-center py-4 px-4">
                  <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* FAQ Section */}
      <div className="max-w-3xl mx-auto mb-20">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-4">
            <HelpCircle className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-primary">FAQ</span>
          </div>
          <h2 className="text-3xl font-bold text-foreground tracking-tight">
            Frequently Asked Questions
          </h2>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="rounded-2xl border border-border/50 bg-card/50 p-6 hover:border-border hover:shadow-lg transition-all duration-300"
            >
              <h3 className="text-lg font-semibold text-foreground mb-2">
                {faq.question}
              </h3>
              <p className="text-muted-foreground leading-relaxed">{faq.answer}</p>
            </div>
          ))}
        </div>
      </div>

      {/* CTA Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary/10 via-card to-accent/10 border border-border/50 p-12 text-center">
        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-primary/20 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-gradient-to-tr from-accent/20 to-transparent rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />

        <div className="relative">
          <h2 className="text-2xl md:text-3xl font-bold text-foreground tracking-tight mb-4">
            Need a custom plan for your organization?
          </h2>
          <p className="text-muted-foreground font-light max-w-xl mx-auto mb-8">
            Get in touch with our sales team to discuss enterprise solutions tailored to your needs.
          </p>
          <Button
            variant="gradient"
            onClick={() => navigate('/contact')}
            size="lg"
            className="h-12 px-8 rounded-xl group"
          >
            Contact Sales
            <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
          </Button>
        </div>
      </div>

      {/* Footer spacing */}
      <div className="h-12" />
    </div>
  );
}
