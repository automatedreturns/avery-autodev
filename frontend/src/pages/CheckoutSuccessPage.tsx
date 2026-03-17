import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, Loader2, ArrowRight } from 'lucide-react';
import { getMySubscription, type Subscription } from '../api/subscriptions';

export default function CheckoutSuccessPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session_id');

  const [loading, setLoading] = useState(true);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Verify the checkout session and load updated subscription
    const verifyCheckout = async () => {
      if (!sessionId) {
        setError('No session ID provided');
        setLoading(false);
        return;
      }

      try {
        // Wait a moment for webhook to process
        await new Promise((resolve) => setTimeout(resolve, 2000));

        // Fetch updated subscription
        const subData = await getMySubscription();
        setSubscription(subData);
      } catch (err) {
        console.error('Failed to verify checkout:', err);
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to verify payment. Please contact support if you were charged.'
        );
      } finally {
        setLoading(false);
      }
    };

    verifyCheckout();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Confirming your payment...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <div className="text-center">
            <div className="bg-red-100 rounded-full p-3 inline-block mb-4">
              <svg
                className="h-8 w-8 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Payment Verification Error
            </h2>
            <p className="text-gray-600 mb-6">{error}</p>
            <div className="space-y-3">
              <button
                onClick={() => navigate('/billing')}
                className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 font-semibold"
              >
                Go to Billing
              </button>
              <button
                onClick={() => navigate('/workspaces')}
                className="w-full bg-gray-100 text-gray-900 py-2 px-4 rounded-lg hover:bg-gray-200 font-semibold"
              >
                Back to Workspaces
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const planName = subscription?.plan.toUpperCase() || 'PRO';
  const isFreePlan = subscription?.plan === 'free';

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-2xl w-full">
        {/* Success Icon */}
        <div className="text-center mb-6">
          <div className="bg-green-100 rounded-full p-3 inline-block mb-4">
            <CheckCircle className="h-12 w-12 text-green-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {isFreePlan
              ? 'Payment Processing'
              : `Welcome to Avery ${planName}!`}
          </h1>
          <p className="text-lg text-gray-600">
            {isFreePlan
              ? 'Your payment is being processed. This may take a few moments.'
              : 'Your subscription is now active'}
          </p>
        </div>

        {/* Subscription Details */}
        {subscription && !isFreePlan && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Your Plan Includes:
            </h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="flex items-start">
                <CheckCircle className="h-5 w-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="font-semibold text-gray-900">
                    {subscription.agent_execution_quota} Agent Executions
                  </p>
                  <p className="text-sm text-gray-600">per month</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="h-5 w-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="font-semibold text-gray-900">
                    {subscription.test_generation_quota} Test Generations
                  </p>
                  <p className="text-sm text-gray-600">per month</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="h-5 w-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="font-semibold text-gray-900">Priority Support</p>
                  <p className="text-sm text-gray-600">Faster response times</p>
                </div>
              </div>
              <div className="flex items-start">
                <CheckCircle className="h-5 w-5 text-green-500 mr-2 mt-0.5" />
                <div>
                  <p className="font-semibold text-gray-900">Overage Credits</p>
                  <p className="text-sm text-gray-600">Purchase when needed</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Next Steps */}
        <div className="border-t pt-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            What's Next?
          </h2>
          <div className="space-y-3">
            <div className="flex items-start">
              <div className="bg-blue-100 text-blue-600 rounded-full w-6 h-6 flex items-center justify-center font-semibold text-sm mr-3 mt-0.5">
                1
              </div>
              <div>
                <p className="font-semibold text-gray-900">Connect Your GitHub</p>
                <p className="text-sm text-gray-600">
                  Integrate your repositories to start automating workflows
                </p>
              </div>
            </div>
            <div className="flex items-start">
              <div className="bg-blue-100 text-blue-600 rounded-full w-6 h-6 flex items-center justify-center font-semibold text-sm mr-3 mt-0.5">
                2
              </div>
              <div>
                <p className="font-semibold text-gray-900">Run Your First Agent</p>
                <p className="text-sm text-gray-600">
                  Try the AI coding agent to refactor or generate code
                </p>
              </div>
            </div>
            <div className="flex items-start">
              <div className="bg-blue-100 text-blue-600 rounded-full w-6 h-6 flex items-center justify-center font-semibold text-sm mr-3 mt-0.5">
                3
              </div>
              <div>
                <p className="font-semibold text-gray-900">Explore Test Generation</p>
                <p className="text-sm text-gray-600">
                  Automatically generate comprehensive test suites
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={() => navigate('/workspaces')}
            className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 font-semibold flex items-center justify-center"
          >
            Go to Workspaces
            <ArrowRight className="ml-2 h-5 w-5" />
          </button>
          <button
            onClick={() => navigate('/billing')}
            className="w-full bg-gray-100 text-gray-900 py-3 px-6 rounded-lg hover:bg-gray-200 font-semibold"
          >
            View Billing Details
          </button>
        </div>

        {/* Receipt Notice */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600">
            A receipt has been sent to your email address.
          </p>
          <p className="text-xs text-gray-500 mt-2">
            Session ID: {sessionId}
          </p>
        </div>
      </div>
    </div>
  );
}
