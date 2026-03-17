/**
 * PolicyCheckStatus Component
 *
 * Displays test policy check status for agent tasks and PRs.
 * Shows coverage percentage, violations, and warnings.
 */

import { AlertCircle, CheckCircle, Shield, AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface PolicyViolation {
  rule: string;
  severity: "error" | "warning" | "info";
  message: string;
  current_value?: any;
  expected_value?: any;
  fix_suggestion?: string;
  affected_files?: string[];
}

interface PolicyCheckStatusProps {
  policyCheck?: {
    passed?: boolean;
    violations?: PolicyViolation[];
    warnings?: PolicyViolation[];
    summary?: string;
    checked_at?: string;
  };
  coveragePercent?: number;
  variant?: "compact" | "full";
}

export default function PolicyCheckStatus({
  policyCheck,
  coveragePercent,
  variant = "compact",
}: PolicyCheckStatusProps) {
  if (!policyCheck && coveragePercent === undefined) {
    return null;
  }

  const violations = policyCheck?.violations || [];
  const warnings = policyCheck?.warnings || [];
  const errorViolations = violations.filter((v) => v.severity === "error");
  const passed = policyCheck?.passed ?? true;

  // Compact variant - just a badge with coverage
  if (variant === "compact") {
    if (!coveragePercent) return null;

    return (
      <div className="flex items-center gap-2">
        <Shield className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">
          Coverage: {coveragePercent.toFixed(1)}%
        </span>
        {passed ? (
          <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800 font-medium">
            Passed
          </span>
        ) : (
          <span className="text-xs px-2 py-1 rounded bg-red-100 text-red-800 font-medium">
            Failed
          </span>
        )}
        {warnings.length > 0 && (
          <span className="text-xs px-2 py-1 rounded bg-yellow-100 text-yellow-800 font-medium">
            {warnings.length} warning{warnings.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
    );
  }

  // Full variant - detailed view with all violations/warnings
  return (
    <div className="space-y-4">
      {/* Coverage Badge */}
      {coveragePercent !== undefined && (
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-primary" />
          <div>
            <div className="text-sm font-medium">Test Coverage</div>
            <div className="text-2xl font-bold">{coveragePercent.toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Success State */}
      {passed && errorViolations.length === 0 && warnings.length === 0 && (
        <Alert variant="default" className="border-green-500 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-green-900">All Policies Passed</AlertTitle>
          <AlertDescription className="text-green-800">
            {policyCheck?.summary ||
              "All test policy requirements have been met."}
          </AlertDescription>
        </Alert>
      )}

      {/* Error Violations */}
      {errorViolations.length > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Policy Violations (Blocking)</AlertTitle>
          <AlertDescription>
            <div className="space-y-3 mt-2">
              {errorViolations.map((violation, idx) => (
                <div key={idx} className="border-l-2 border-red-500 pl-3">
                  <div className="font-semibold text-sm">{violation.rule}</div>
                  <div className="text-sm mt-1">{violation.message}</div>
                  {violation.fix_suggestion && (
                    <div className="text-xs mt-1 text-muted-foreground">
                      <strong>Fix:</strong> {violation.fix_suggestion}
                    </div>
                  )}
                  {violation.affected_files && violation.affected_files.length > 0 && (
                    <div className="text-xs mt-1 text-muted-foreground">
                      <strong>Files:</strong> {violation.affected_files.slice(0, 3).join(", ")}
                      {violation.affected_files.length > 3 && ` (+${violation.affected_files.length - 3} more)`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <Alert variant="default" className="border-yellow-500 bg-yellow-50">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <AlertTitle className="text-yellow-900">Policy Warnings</AlertTitle>
          <AlertDescription className="text-yellow-800">
            <div className="space-y-2 mt-2">
              {warnings.map((warning, idx) => (
                <div key={idx} className="border-l-2 border-yellow-500 pl-3">
                  <div className="font-semibold text-sm">{warning.rule}</div>
                  <div className="text-sm mt-1">{warning.message}</div>
                  {warning.fix_suggestion && (
                    <div className="text-xs mt-1">
                      <strong>Suggestion:</strong> {warning.fix_suggestion}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Policy Check Summary */}
      {policyCheck?.summary && (errorViolations.length > 0 || warnings.length > 0) && (
        <div className="text-sm text-muted-foreground">
          {policyCheck.summary}
        </div>
      )}

      {/* Timestamp */}
      {policyCheck?.checked_at && (
        <div className="text-xs text-muted-foreground">
          Checked at: {new Date(policyCheck.checked_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

/**
 * Usage Examples:
 *
 * // Compact variant in a list
 * <PolicyCheckStatus
 *   coveragePercent={85.5}
 *   policyCheck={{ passed: true }}
 *   variant="compact"
 * />
 *
 * // Full variant in a detail view
 * <PolicyCheckStatus
 *   coveragePercent={75.2}
 *   policyCheck={{
 *     passed: false,
 *     violations: [{ rule: "Minimum Coverage", severity: "error", message: "..." }],
 *     warnings: [],
 *     summary: "Coverage below minimum threshold"
 *   }}
 *   variant="full"
 * />
 */
