/**
 * Subscription API client
 */
import { api, handleApiError } from './client';

// Types
export interface Subscription {
  id: number;
  user_id: number;
  plan: 'free' | 'pro' | 'team' | 'enterprise';
  status: 'active' | 'canceled' | 'past_due' | 'incomplete' | 'trialing';
  stripe_customer_id?: string;
  stripe_subscription_id?: string;
  current_period_start: string;
  current_period_end: string;
  agent_execution_quota: number;
  test_generation_quota: number;
  created_at: string;
  updated_at?: string;
  canceled_at?: string;
}

export interface UsageSummary {
  subscription: {
    plan: string;
    status: string;
    current_period_start: string;
    current_period_end: string;
    days_until_renewal: number;
  };
  quotas: {
    agent_execution: number;
    test_generation: number;
  };
  usage: {
    agent_execution: number;
    test_generation: number;
  };
  remaining: {
    agent_execution: number;
    test_generation: number;
  };
}

export interface QuotaCheck {
  allowed: boolean;
  remaining: number;
  quota: number;
  used: number;
  overage_credits: number;
  requires_upgrade: boolean;
  can_purchase_overage: boolean;
  overage_price_cents: number;
  plan: string;
  status: string;
}

export interface CheckoutSession {
  checkout_url: string;
  session_id: string;
}

export const getMySubscription = async (): Promise<Subscription> => {
  try {
    const response = await api.get('/api/v1/subscriptions/me');
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const getUsageSummary = async (): Promise<UsageSummary> => {
  try {
    const response = await api.get('/api/v1/subscriptions/usage');
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const checkQuota = async (
  eventType: 'agent_execution' | 'test_generation'
): Promise<QuotaCheck> => {
  try {
    const response = await api.get(`/api/v1/subscriptions/quota-check?type=${eventType}`);
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const createCheckoutSession = async (
  plan: 'pro' | 'team'
): Promise<CheckoutSession> => {
  try {
    const response = await api.post('/api/v1/subscriptions/checkout', { plan });
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};

export const cancelSubscription = async (): Promise<{
  message: string;
  effective_date: string;
  days_remaining?: number;
}> => {
  try {
    const response = await api.post('/api/v1/subscriptions/cancel');
    return response.data;
  } catch (error) {
    return handleApiError(error);
  }
};
