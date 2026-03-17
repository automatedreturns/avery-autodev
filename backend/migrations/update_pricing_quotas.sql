-- Migration: Update Subscription Quotas for New Pricing
-- Date: December 24, 2024
-- Description: Updates agent_execution_quota and test_generation_quota to reflect new pricing

-- =============================================================================
-- STEP 1: Update FREE plan subscriptions (10 -> 3 executions)
-- =============================================================================

UPDATE subscriptions
SET
    agent_execution_quota = 3,
    test_generation_quota = 5,  -- Unchanged
    updated_at = NOW()
WHERE
    plan = 'free'
    AND agent_execution_quota = 10;

-- Verify FREE plan update
SELECT
    COUNT(*) as updated_free_plans,
    agent_execution_quota,
    test_generation_quota
FROM subscriptions
WHERE plan = 'free'
GROUP BY agent_execution_quota, test_generation_quota;


-- =============================================================================
-- STEP 2: Update PRO plan subscriptions (60 -> 25 executions, 30 -> 50 tests)
-- =============================================================================

UPDATE subscriptions
SET
    agent_execution_quota = 25,
    test_generation_quota = 50,
    updated_at = NOW()
WHERE
    plan = 'pro'
    AND agent_execution_quota = 60;

-- Verify PRO plan update
SELECT
    COUNT(*) as updated_pro_plans,
    agent_execution_quota,
    test_generation_quota
FROM subscriptions
WHERE plan = 'pro'
GROUP BY agent_execution_quota, test_generation_quota;


-- =============================================================================
-- STEP 3: Update TEAM plan subscriptions (200 -> 100 executions, 100 -> 200 tests)
-- =============================================================================

UPDATE subscriptions
SET
    agent_execution_quota = 100,
    test_generation_quota = 200,
    updated_at = NOW()
WHERE
    plan = 'team'
    AND agent_execution_quota = 200;

-- Verify TEAM plan update
SELECT
    COUNT(*) as updated_team_plans,
    agent_execution_quota,
    test_generation_quota
FROM subscriptions
WHERE plan = 'team'
GROUP BY agent_execution_quota, test_generation_quota;


-- =============================================================================
-- STEP 4: Verification - Check all subscription quotas
-- =============================================================================

SELECT
    plan,
    COUNT(*) as subscription_count,
    agent_execution_quota,
    test_generation_quota,
    MIN(updated_at) as oldest_update,
    MAX(updated_at) as newest_update
FROM subscriptions
GROUP BY plan, agent_execution_quota, test_generation_quota
ORDER BY plan;


-- =============================================================================
-- STEP 5: (Optional) Update default column values for new subscriptions
-- =============================================================================

-- Update the default value for agent_execution_quota
ALTER TABLE subscriptions
ALTER COLUMN agent_execution_quota SET DEFAULT 3;

-- Verify the default was changed
SELECT
    column_name,
    column_default,
    data_type
FROM information_schema.columns
WHERE
    table_name = 'subscriptions'
    AND column_name IN ('agent_execution_quota', 'test_generation_quota');


-- =============================================================================
-- ROLLBACK SCRIPT (if needed)
-- =============================================================================

/*
-- To rollback to old pricing:

-- Rollback FREE plan
UPDATE subscriptions
SET
    agent_execution_quota = 10,
    test_generation_quota = 5,
    updated_at = NOW()
WHERE
    plan = 'free'
    AND agent_execution_quota = 3;

-- Rollback PRO plan
UPDATE subscriptions
SET
    agent_execution_quota = 60,
    test_generation_quota = 30,
    updated_at = NOW()
WHERE
    plan = 'pro'
    AND agent_execution_quota = 25;

-- Rollback TEAM plan
UPDATE subscriptions
SET
    agent_execution_quota = 200,
    test_generation_quota = 100,
    updated_at = NOW()
WHERE
    plan = 'team'
    AND agent_execution_quota = 100;

-- Rollback default value
ALTER TABLE subscriptions
ALTER COLUMN agent_execution_quota SET DEFAULT 10;
*/


-- =============================================================================
-- SAFETY CHECKS BEFORE RUNNING
-- =============================================================================

-- Check current subscription counts by plan
SELECT
    plan,
    COUNT(*) as total_subscriptions,
    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_subscriptions,
    AVG(agent_execution_quota) as avg_execution_quota,
    AVG(test_generation_quota) as avg_test_quota
FROM subscriptions
GROUP BY plan
ORDER BY plan;

-- Check for any subscriptions with custom quotas (not matching standard plans)
SELECT
    id,
    user_id,
    plan,
    agent_execution_quota,
    test_generation_quota,
    status,
    created_at
FROM subscriptions
WHERE
    (plan = 'free' AND agent_execution_quota != 10)
    OR (plan = 'pro' AND agent_execution_quota != 60)
    OR (plan = 'team' AND agent_execution_quota != 200)
ORDER BY created_at DESC;
