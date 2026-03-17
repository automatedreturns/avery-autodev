/**
 * Phase 2: Test Policy Settings Component
 *
 * Allows workspace admins to configure test quality policies.
 */

import { useState, useEffect } from 'react';
import { Shield, Save, ToggleLeft, ToggleRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { getTestPolicy, updateTestPolicy, toggleTestPolicyEnabled } from '../api/test_policy';
import type { TestPolicyResponse, TestPolicyUpdate } from '../types/test_policy';

interface TestPolicySettingsProps {
  workspaceId: number;
}

export default function TestPolicySettings({ workspaceId }: TestPolicySettingsProps) {
  const [policy, setPolicy] = useState<TestPolicyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Local form state
  const [minimumCoverage, setMinimumCoverage] = useState(80);
  const [testQualityThreshold, setTestQualityThreshold] = useState(70);
  const [allowCoverageDecrease, setAllowCoverageDecrease] = useState(false);
  const [maxCoverageDecrease, setMaxCoverageDecrease] = useState(0);
  const [requireTestsForFeatures, setRequireTestsForFeatures] = useState(true);
  const [requireTestsForBugFixes, setRequireTestsForBugFixes] = useState(true);
  const [autoGenerateTests, setAutoGenerateTests] = useState(true);

  useEffect(() => {
    loadPolicy();
  }, [workspaceId]);

  const loadPolicy = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await getTestPolicy(workspaceId);
      setPolicy(data);

      // Update local state
      setMinimumCoverage(data.test_policy_config.minimum_coverage_percent);
      setTestQualityThreshold(data.test_policy_config.test_quality_threshold);
      setAllowCoverageDecrease(data.test_policy_config.allow_coverage_decrease);
      setMaxCoverageDecrease(data.test_policy_config.max_coverage_decrease_percent);
      setRequireTestsForFeatures(data.test_policy_config.require_tests_for_features);
      setRequireTestsForBugFixes(data.test_policy_config.require_tests_for_bug_fixes);
      setAutoGenerateTests(data.test_policy_config.auto_generate_tests);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load test policy');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleEnabled = async () => {
    if (!policy) return;

    try {
      setSaving(true);
      setError('');
      const updated = await toggleTestPolicyEnabled(workspaceId, !policy.test_policy_enabled);
      setPolicy(updated);
      setSuccess(`Test policy ${updated.test_policy_enabled ? 'enabled' : 'disabled'} successfully`);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle test policy');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');

      const update: TestPolicyUpdate = {
        minimum_coverage_percent: minimumCoverage,
        test_quality_threshold: testQualityThreshold,
        allow_coverage_decrease: allowCoverageDecrease,
        max_coverage_decrease_percent: maxCoverageDecrease,
        require_tests_for_features: requireTestsForFeatures,
        require_tests_for_bug_fixes: requireTestsForBugFixes,
        auto_generate_tests: autoGenerateTests,
      };

      const updated = await updateTestPolicy(workspaceId, update);
      setPolicy(updated);
      setSuccess('Test policy settings saved successfully');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save test policy');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-primary animate-pulse" />
          <span className="text-sm text-muted-foreground">Loading test policy settings...</span>
        </div>
      </Card>
    );
  }

  if (!policy) {
    return (
      <Card className="p-6">
        <Alert>
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>Failed to load test policy settings</AlertDescription>
        </Alert>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Enable/Disable Toggle */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Shield className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Test Policy Enforcement</h3>
              <p className="text-sm text-muted-foreground">
                {policy.test_policy_enabled
                  ? 'Policies are currently enforced'
                  : 'Policies are currently disabled'}
              </p>
            </div>
          </div>

          <Button
            onClick={handleToggleEnabled}
            disabled={saving}
            variant={policy.test_policy_enabled ? 'default' : 'outline'}
            className="min-w-[120px]"
          >
            {policy.test_policy_enabled ? (
              <>
                <ToggleRight className="w-4 h-4 mr-2" />
                Enabled
              </>
            ) : (
              <>
                <ToggleLeft className="w-4 h-4 mr-2" />
                Disabled
              </>
            )}
          </Button>
        </div>
      </Card>

      {/* Policy Configuration */}
      {policy.test_policy_enabled && (
        <Card className="p-6">
          <div className="space-y-6">
            <div>
              <h4 className="text-md font-semibold mb-4">Coverage Requirements</h4>

              <div className="space-y-4">
                {/* Minimum Coverage */}
                <div>
                  <label className="text-sm font-medium mb-2 block">
                    Minimum Coverage Percentage
                  </label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={minimumCoverage}
                      onChange={(e) => setMinimumCoverage(Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-lg font-bold min-w-[60px] text-primary">
                      {minimumCoverage}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Pull requests must meet this minimum coverage threshold
                  </p>
                </div>

                {/* Allow Coverage Decrease */}
                <div className="flex items-center justify-between py-3 border-t">
                  <div>
                    <p className="text-sm font-medium">Allow Coverage Decrease</p>
                    <p className="text-xs text-muted-foreground">
                      Permit coverage to decrease below previous snapshot
                    </p>
                  </div>
                  <Button
                    onClick={() => setAllowCoverageDecrease(!allowCoverageDecrease)}
                    variant={allowCoverageDecrease ? 'default' : 'outline'}
                    size="sm"
                  >
                    {allowCoverageDecrease ? (
                      <ToggleRight className="w-4 h-4" />
                    ) : (
                      <ToggleLeft className="w-4 h-4" />
                    )}
                  </Button>
                </div>

                {/* Max Coverage Decrease */}
                {allowCoverageDecrease && (
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Maximum Coverage Decrease
                    </label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0"
                        max="20"
                        step="0.5"
                        value={maxCoverageDecrease}
                        onChange={(e) => setMaxCoverageDecrease(Number(e.target.value))}
                        className="flex-1"
                      />
                      <span className="text-lg font-bold min-w-[60px] text-amber-600">
                        {maxCoverageDecrease}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Maximum allowed coverage reduction
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="border-t pt-6">
              <h4 className="text-md font-semibold mb-4">Test Requirements</h4>

              <div className="space-y-4">
                {/* Require Tests for Features */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Require Tests for Features</p>
                    <p className="text-xs text-muted-foreground">
                      New features must include tests
                    </p>
                  </div>
                  <Button
                    onClick={() => setRequireTestsForFeatures(!requireTestsForFeatures)}
                    variant={requireTestsForFeatures ? 'default' : 'outline'}
                    size="sm"
                  >
                    {requireTestsForFeatures ? (
                      <ToggleRight className="w-4 h-4" />
                    ) : (
                      <ToggleLeft className="w-4 h-4" />
                    )}
                  </Button>
                </div>

                {/* Require Tests for Bug Fixes */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Require Tests for Bug Fixes</p>
                    <p className="text-xs text-muted-foreground">
                      Bug fixes must include regression tests
                    </p>
                  </div>
                  <Button
                    onClick={() => setRequireTestsForBugFixes(!requireTestsForBugFixes)}
                    variant={requireTestsForBugFixes ? 'default' : 'outline'}
                    size="sm"
                  >
                    {requireTestsForBugFixes ? (
                      <ToggleRight className="w-4 h-4" />
                    ) : (
                      <ToggleLeft className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>

            <div className="border-t pt-6">
              <h4 className="text-md font-semibold mb-4">Test Quality</h4>

              <div className="space-y-4">
                {/* Test Quality Threshold */}
                <div>
                  <label className="text-sm font-medium mb-2 block">
                    Test Quality Threshold
                  </label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={testQualityThreshold}
                      onChange={(e) => setTestQualityThreshold(Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-lg font-bold min-w-[60px] text-primary">
                      {testQualityThreshold}/100
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Minimum quality score for generated tests
                  </p>
                </div>

                {/* Auto-generate Tests */}
                <div className="flex items-center justify-between border-t pt-4">
                  <div>
                    <p className="text-sm font-medium">Auto-generate Tests</p>
                    <p className="text-xs text-muted-foreground">
                      Automatically generate tests when policy violations occur
                    </p>
                  </div>
                  <Button
                    onClick={() => setAutoGenerateTests(!autoGenerateTests)}
                    variant={autoGenerateTests ? 'default' : 'outline'}
                    size="sm"
                  >
                    {autoGenerateTests ? (
                      <ToggleRight className="w-4 h-4" />
                    ) : (
                      <ToggleLeft className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="flex items-center justify-between border-t pt-6">
              <div className="text-sm text-muted-foreground">
                Changes will apply to future pull requests
              </div>
              <Button onClick={handleSave} disabled={saving} className="min-w-[120px]">
                {saving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-background border-t-transparent rounded-full animate-spin mr-2" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Save Changes
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Success/Error Messages */}
      {success && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle2 className="w-4 h-4 text-green-600" />
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
