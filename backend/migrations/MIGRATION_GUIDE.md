# PostgreSQL Migration Guide - Pricing Update

## Overview
This migration updates subscription quotas to reflect the new pricing structure.

## Pre-Migration Checklist

- [ ] **Backup Database**: Create a full backup before proceeding
- [ ] **Test in Staging**: Run these commands in a staging environment first
- [ ] **Notify Users**: Consider notifying users about the quota changes
- [ ] **Check Active Subscriptions**: Review current subscription data

## Step-by-Step Migration

### Step 1: Create Database Backup

```bash
# PostgreSQL backup command
pg_dump -U your_username -d avery_db > backup_before_pricing_update_$(date +%Y%m%d).sql

# Or if using Docker:
docker exec postgres_container pg_dump -U your_username avery_db > backup_before_pricing_update_$(date +%Y%m%d).sql
```

### Step 2: Check Current State

```sql
-- See current subscription distribution
SELECT
    plan,
    COUNT(*) as total,
    agent_execution_quota,
    test_generation_quota
FROM subscriptions
GROUP BY plan, agent_execution_quota, test_generation_quota
ORDER BY plan;
```

Expected output:
```
 plan  | total | agent_execution_quota | test_generation_quota
-------+-------+-----------------------+-----------------------
 free  |   XX  |          10           |           5
 pro   |   XX  |          60           |          30
 team  |   XX  |         200           |         100
```

### Step 3: Run Migration (Transaction-Safe)

```sql
-- Start transaction
BEGIN;

-- Update FREE tier (10 -> 3 executions)
UPDATE subscriptions
SET
    agent_execution_quota = 3,
    test_generation_quota = 5,
    updated_at = NOW()
WHERE
    plan = 'free'
    AND agent_execution_quota = 10;

-- Update PRO tier (60 -> 25 executions, 30 -> 50 tests)
UPDATE subscriptions
SET
    agent_execution_quota = 25,
    test_generation_quota = 50,
    updated_at = NOW()
WHERE
    plan = 'pro'
    AND agent_execution_quota = 60;

-- Update TEAM tier (200 -> 100 executions, 100 -> 200 tests)
UPDATE subscriptions
SET
    agent_execution_quota = 100,
    test_generation_quota = 200,
    updated_at = NOW()
WHERE
    plan = 'team'
    AND agent_execution_quota = 200;

-- Update default column value for new subscriptions
ALTER TABLE subscriptions
ALTER COLUMN agent_execution_quota SET DEFAULT 3;

-- Verify changes before committing
SELECT
    plan,
    COUNT(*) as count,
    agent_execution_quota,
    test_generation_quota
FROM subscriptions
GROUP BY plan, agent_execution_quota, test_generation_quota
ORDER BY plan;

-- If everything looks good, commit
COMMIT;

-- If something is wrong, rollback
-- ROLLBACK;
```

### Step 4: Verify Migration Success

```sql
-- Check that all subscriptions have been updated
SELECT
    plan,
    COUNT(*) as subscription_count,
    agent_execution_quota,
    test_generation_quota
FROM subscriptions
GROUP BY plan, agent_execution_quota, test_generation_quota
ORDER BY plan;
```

Expected output after migration:
```
 plan  | subscription_count | agent_execution_quota | test_generation_quota
-------+--------------------+-----------------------+-----------------------
 free  |        XX          |           3           |           5
 pro   |        XX          |          25           |          50
 team  |        XX          |         100           |         200
```

### Step 5: Check for Edge Cases

```sql
-- Find any subscriptions that didn't update (custom quotas)
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
    (plan = 'free' AND agent_execution_quota NOT IN (3, 10))
    OR (plan = 'pro' AND agent_execution_quota NOT IN (25, 60))
    OR (plan = 'team' AND agent_execution_quota NOT IN (100, 200))
ORDER BY created_at DESC;
```

## Post-Migration Steps

### 1. Update Usage Alerts
If you have any monitoring/alerting based on quota usage, update thresholds.

### 2. Monitor User Impact
```sql
-- Check how many users are over their new quota
SELECT
    s.id,
    s.user_id,
    s.plan,
    s.agent_execution_quota as new_quota,
    COUNT(ur.id) as current_usage,
    s.agent_execution_quota - COUNT(ur.id) as remaining
FROM subscriptions s
LEFT JOIN usage_records ur ON s.id = ur.subscription_id
    AND ur.event_type = 'agent_execution'
    AND ur.billing_period_start = s.current_period_start
GROUP BY s.id, s.user_id, s.plan, s.agent_execution_quota
HAVING COUNT(ur.id) > s.agent_execution_quota
ORDER BY (COUNT(ur.id) - s.agent_execution_quota) DESC;
```

### 3. Communication Template
For users who are now over their quota, you might want to send an email:

```
Subject: Important: Avery Subscription Update

Hi [Name],

We've updated our pricing to ensure sustainable, high-quality AI coding services.

Your current plan: [PLAN_NAME]
New monthly quota: [NEW_QUOTA] agent executions

Your account:
- Used this month: [CURRENT_USAGE] executions
- New monthly limit: [NEW_QUOTA] executions

If you need more executions, you can:
1. Upgrade to a higher plan
2. Purchase additional executions at $[RATE] each

View your usage: [DASHBOARD_URL]

Questions? Contact us at support@goodgist.com
```

## Rollback Instructions

If you need to rollback to the old pricing:

```sql
BEGIN;

-- Rollback FREE plan
UPDATE subscriptions
SET
    agent_execution_quota = 10,
    test_generation_quota = 5,
    updated_at = NOW()
WHERE plan = 'free';

-- Rollback PRO plan
UPDATE subscriptions
SET
    agent_execution_quota = 60,
    test_generation_quota = 30,
    updated_at = NOW()
WHERE plan = 'pro';

-- Rollback TEAM plan
UPDATE subscriptions
SET
    agent_execution_quota = 200,
    test_generation_quota = 100,
    updated_at = NOW()
WHERE plan = 'team';

-- Rollback default value
ALTER TABLE subscriptions
ALTER COLUMN agent_execution_quota SET DEFAULT 10;

COMMIT;
```

## Alternative: Gradual Migration

If you want to grandfather existing users for a period:

```sql
-- Add a temporary flag
ALTER TABLE subscriptions
ADD COLUMN legacy_pricing BOOLEAN DEFAULT FALSE;

-- Mark existing paid subscriptions as legacy
UPDATE subscriptions
SET legacy_pricing = TRUE
WHERE
    plan IN ('pro', 'team')
    AND created_at < NOW();

-- Then only update new subscriptions
UPDATE subscriptions
SET
    agent_execution_quota = CASE
        WHEN plan = 'free' THEN 3
        WHEN plan = 'pro' THEN 25
        WHEN plan = 'team' THEN 100
    END,
    test_generation_quota = CASE
        WHEN plan = 'free' THEN 5
        WHEN plan = 'pro' THEN 50
        WHEN plan = 'team' THEN 200
    END,
    updated_at = NOW()
WHERE
    legacy_pricing = FALSE;

-- After grace period (e.g., 90 days), migrate legacy users
UPDATE subscriptions
SET
    agent_execution_quota = CASE
        WHEN plan = 'free' THEN 3
        WHEN plan = 'pro' THEN 25
        WHEN plan = 'team' THEN 100
    END,
    test_generation_quota = CASE
        WHEN plan = 'free' THEN 5
        WHEN plan = 'pro' THEN 50
        WHEN plan = 'team' THEN 200
    END,
    legacy_pricing = FALSE,
    updated_at = NOW()
WHERE
    legacy_pricing = TRUE
    AND current_period_end < NOW() + INTERVAL '90 days';
```

## Troubleshooting

### Issue: Some subscriptions didn't update
**Solution**: Check for custom quotas that don't match standard plans
```sql
SELECT * FROM subscriptions
WHERE agent_execution_quota NOT IN (3, 10, 25, 60, 100, 200);
```

### Issue: Users complaining about reduced quota
**Solution**: Check if they had custom/grandfathered quotas
```sql
SELECT
    s.*,
    u.email
FROM subscriptions s
JOIN users u ON s.user_id = u.id
WHERE
    s.user_id = [USER_ID]
    AND s.updated_at > NOW() - INTERVAL '7 days';
```

### Issue: Need to revert specific user
**Solution**: Manually update their subscription
```sql
UPDATE subscriptions
SET
    agent_execution_quota = [CUSTOM_QUOTA],
    test_generation_quota = [CUSTOM_QUOTA],
    updated_at = NOW()
WHERE user_id = [USER_ID];
```

## Testing Checklist

After migration, verify:

- [ ] All free users have 3 execution quota
- [ ] All pro users have 25 execution quota
- [ ] All team users have 100 execution quota
- [ ] Default column value is 3
- [ ] New signups get correct quotas
- [ ] Existing subscriptions enforcing new limits
- [ ] Overage purchases working correctly
- [ ] Frontend displays correct quotas
- [ ] Usage tracking still works

## Support

If you encounter issues:
1. Check the backup was created successfully
2. Review the verification queries
3. Contact the development team
4. Have the rollback script ready

---

**Migration Date**: December 24, 2024
**Database Version**: PostgreSQL 14+
**Estimated Time**: 5-10 minutes
**Downtime Required**: No (can run while app is running)
