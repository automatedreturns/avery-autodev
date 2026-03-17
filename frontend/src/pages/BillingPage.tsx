import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  CreditCard,
  Calendar,
  TrendingUp,
  AlertCircle,
  Check,
  Loader2,
  ExternalLink,
  CheckCircle,
} from "lucide-react";
import {
  getMySubscription,
  getUsageSummary,
  cancelSubscription,
  type Subscription,
  type UsageSummary,
} from "../api/subscriptions";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useAuth } from "@/context/AuthContext";

export default function BillingPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [canceling, setCanceling] = useState(false);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const { user } = useAuth();

  useEffect(() => {
    loadBillingData(true); // Show loading spinner on initial load

    // Poll for updates every 10 seconds (without loading spinner)
    const interval = setInterval(() => {
      loadBillingData(false);
    }, 10000);

    // Cleanup interval on unmount
    return () => clearInterval(interval);
  }, []);

  const loadBillingData = async (showLoadingSpinner = true) => {
    if (showLoadingSpinner) {
      setLoading(true);
    }
    setError(null);

    try {
      const [subData, usageData] = await Promise.all([
        getMySubscription(),
        getUsageSummary(),
      ]);

      setSubscription(subData);
      setUsage(usageData);
    } catch (err) {
      console.error("Failed to load billing data:", err);
      setError(
        err instanceof Error ? err.message : "Failed to load billing data"
      );
    } finally {
      if (showLoadingSpinner) {
        setLoading(false);
      }
    }
  };

  const handleCancelSubscription = async () => {
    setCanceling(true);
    setError(null);

    try {
      const result = await cancelSubscription();
      setSuccessMessage(result.message);
      setShowSuccessModal(true);
      // Reload data to reflect cancellation
      await loadBillingData();
      setShowCancelConfirm(false);
    } catch (err) {
      console.error("Failed to cancel subscription:", err);
      setError(
        err instanceof Error ? err.message : "Failed to cancel subscription"
      );
    } finally {
      setCanceling(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const getPlanColor = (plan: string) => {
    switch (plan.toLowerCase()) {
      case "free":
        return "bg-muted text-muted-foreground";
      case "pro":
        return "bg-primary/10 text-primary dark:bg-primary/20";
      case "team":
        return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
      case "enterprise":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  const getUsagePercentage = (used: number, quota: number) => {
    if (quota === 0) return 0;
    return Math.min((used / quota) * 100, 100);
  };

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return "bg-red-500 dark:bg-red-600";
    if (percentage >= 70) return "bg-yellow-500 dark:bg-yellow-600";
    return "bg-green-500 dark:bg-green-600";
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="animate-spin h-12 w-12 text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">
            Loading billing information...
          </p>
        </div>
      </div>
    );
  }

  if (error && !subscription) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-8 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h2 className="text-xl font-bold text-foreground mb-2">
              Error Loading Billing Data
            </h2>
            <p className="text-muted-foreground mb-6">{error}</p>
            <Button
              variant="gradient"
              onClick={() => loadBillingData(true)}
              className="w-full"
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Billing & Usage
          </h1>
          <p className="text-muted-foreground">
            Manage your subscription and monitor your usage
          </p>
        </div>

        {/* Error Banner */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Current Plan Card */}
        {subscription && (
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle>Current Plan</CardTitle>
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-sm font-semibold mt-2 ${getPlanColor(
                      subscription.plan
                    )}`}
                  >
                    {subscription.plan.toUpperCase()}
                  </span>
                </div>
                <CreditCard className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardHeader>

            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Status</p>
                  <p className="text-lg font-semibold text-foreground capitalize">
                    {subscription.status}
                    {subscription.status === "canceled" &&
                      subscription.current_period_end && (
                        <span className="text-sm text-muted-foreground ml-2">
                          (until {formatDate(subscription.current_period_end)})
                        </span>
                      )}
                  </p>
                </div>

                {subscription.current_period_end && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">
                      <Calendar className="inline h-4 w-4 mr-1" />
                      {subscription.status === "canceled"
                        ? "Active Until"
                        : "Next Billing Date"}
                    </p>
                    <p className="text-lg font-semibold text-foreground">
                      {formatDate(subscription.current_period_end)}
                    </p>
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                {subscription.plan === "free" ? (
                  <Button
                    variant="gradient"
                    onClick={() => navigate("/pricing")}
                    className="flex-1"
                  >
                    Upgrade Plan
                  </Button>
                ) : (
                  <>
                    <Button
                      disabled={user?.email
                        .toLowerCase()
                        .endsWith("@goodgist.com")}
                      onClick={() => navigate("/pricing")}
                      variant="outline"
                      className="flex-1"
                    >
                      Change Plan
                    </Button>
                    {subscription.status !== "canceled" && (
                      <Button
                        disabled={user?.email
                          .toLowerCase()
                          .endsWith("@goodgist.com")}
                        onClick={() => setShowCancelConfirm(true)}
                        variant="destructive"
                        className="flex-1"
                      >
                        Cancel Subscription
                      </Button>
                    )}
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Usage Statistics */}
        {usage && (
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Usage This Period</CardTitle>
                <TrendingUp className="h-6 w-6 text-muted-foreground" />
              </div>
              <CardDescription>
                Billing period:{" "}
                {formatDate(usage.subscription.current_period_start)} -{" "}
                {formatDate(usage.subscription.current_period_end)}
                {usage.subscription.days_until_renewal > 0 && (
                  <span className="ml-2">
                    ({usage.subscription.days_until_renewal} days remaining)
                  </span>
                )}
              </CardDescription>
            </CardHeader>

            <CardContent>
              {/* Agent Executions */}
              <div className="mb-6">
                <div className="flex justify-between mb-2">
                  <span className="font-semibold text-foreground">
                    Agent Executions
                  </span>
                  <span className="text-muted-foreground">
                    {usage.usage.agent_execution} /{" "}
                    {usage.quotas.agent_execution} used
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${getUsageColor(
                      getUsagePercentage(
                        usage.usage.agent_execution,
                        usage.quotas.agent_execution
                      )
                    )}`}
                    style={{
                      width: `${getUsagePercentage(
                        usage.usage.agent_execution,
                        usage.quotas.agent_execution
                      )}%`,
                    }}
                  />
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {usage.remaining.agent_execution} executions remaining
                </p>
              </div>

              {/* Test Generations */}
              <div>
                <div className="flex justify-between mb-2">
                  <span className="font-semibold text-foreground">
                    Test Generations
                  </span>
                  <span className="text-muted-foreground">
                    {usage.usage.test_generation} /{" "}
                    {usage.quotas.test_generation} used
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${getUsageColor(
                      getUsagePercentage(
                        usage.usage.test_generation,
                        usage.quotas.test_generation
                      )
                    )}`}
                    style={{
                      width: `${getUsagePercentage(
                        usage.usage.test_generation,
                        usage.quotas.test_generation
                      )}%`,
                    }}
                  />
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {usage.remaining.test_generation} generations remaining
                </p>
              </div>

              {/* Upgrade Notice */}
              {(usage.remaining.agent_execution === 0 ||
                usage.remaining.test_generation === 0) &&
                subscription?.plan === "free" && (
                  <Alert className="mt-6 bg-primary/10 border-primary/20">
                    <AlertCircle className="h-4 w-4 text-primary" />
                    <AlertDescription>
                      <p className="font-semibold mb-1">Out of Credits</p>
                      <p className="mb-3">
                        You've used all your free credits for this month.
                        Upgrade to continue using Avery without interruption.
                      </p>
                      <Button
                        variant="gradient"
                        onClick={() => navigate("/pricing")}
                        size="sm"
                      >
                        View Plans
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}
            </CardContent>
          </Card>
        )}

        {/* Plan Features */}
        {subscription && (
          <Card>
            <CardHeader>
              <CardTitle>Your Plan Includes</CardTitle>
            </CardHeader>

            <CardContent>
              <div className="space-y-3">
                <div className="flex items-start">
                  <Check className="h-5 w-5 text-green-500 dark:text-green-400 mr-3 mt-0.5" />
                  <span className="text-foreground">
                    {subscription.agent_execution_quota} agent executions per
                    month
                  </span>
                </div>
                <div className="flex items-start">
                  <Check className="h-5 w-5 text-green-500 dark:text-green-400 mr-3 mt-0.5" />
                  <span className="text-foreground">
                    {subscription.test_generation_quota} test generations per
                    month
                  </span>
                </div>
                <div className="flex items-start">
                  <Check className="h-5 w-5 text-green-500 dark:text-green-400 mr-3 mt-0.5" />
                  <span className="text-foreground">GitHub integration</span>
                </div>
                {subscription.plan !== "free" && (
                  <>
                    <div className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 dark:text-green-400 mr-3 mt-0.5" />
                      <span className="text-foreground">
                        Priority support & faster response times
                      </span>
                    </div>
                    <div className="flex items-start">
                      <Check className="h-5 w-5 text-green-500 dark:text-green-400 mr-3 mt-0.5" />
                      <span className="text-foreground">
                        Purchase additional credits when needed
                      </span>
                    </div>
                  </>
                )}
              </div>

              {subscription.plan === "free" && (
                <div className="mt-6 pt-6 border-t border-border">
                  <p className="text-muted-foreground mb-4">
                    Want more? Upgrade to unlock additional features and higher
                    quotas.
                  </p>
                  <Button
                    onClick={() => navigate("/pricing")}
                    variant="link"
                    className="p-0 h-auto"
                  >
                    Compare Plans
                    <ExternalLink className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Cancel Confirmation Modal */}
      <Dialog open={showCancelConfirm} onOpenChange={setShowCancelConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Subscription?</DialogTitle>
            <DialogDescription>
              Your subscription will remain active until the end of your current
              billing period (
              {subscription?.current_period_end &&
                formatDate(subscription.current_period_end)}
              ), then you'll be downgraded to the free plan.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 mt-4">
            <Button
              onClick={() => setShowCancelConfirm(false)}
              disabled={canceling}
              variant="outline"
              className="flex-1"
            >
              Keep Subscription
            </Button>
            <Button
              onClick={handleCancelSubscription}
              disabled={canceling}
              variant="destructive"
              className="flex-1"
            >
              {canceling ? (
                <>
                  <Loader2 className="animate-spin mr-2 h-5 w-5" />
                  Canceling...
                </>
              ) : (
                "Cancel Subscription"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Success Modal */}
      <Dialog open={showSuccessModal} onOpenChange={setShowSuccessModal}>
        <DialogContent>
          <DialogHeader>
            <div className="flex items-center justify-center mb-4">
              <div className="bg-green-100 rounded-full p-3">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <DialogTitle className="text-center">Success!</DialogTitle>
            <DialogDescription className="text-center">
              {successMessage}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-center mt-4">
            <Button
              variant="gradient"
              onClick={() => setShowSuccessModal(false)}
            >
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
