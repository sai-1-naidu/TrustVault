import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

interface AuditLog {
  id: string;
  user_id: string;
  document_id: string | null;
  action: string;
  details?: Record<string, unknown> | null;
  timestamp: string;
}

interface Verification {
  valid: boolean;
  message?: string;
}

function AuditLogs() {
  const navigate = useNavigate();

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [verification, setVerification] =
    useState<Verification | null>(null);
  const [loading, setLoading] = useState(true);
  const [verificationLoading, setVerificationLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchLogs = useCallback(async () => {
    setError("");
    try {
      const response = await api.get("/api/audit/all");
      setLogs(response.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Unable to load audit logs."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const verifyAudit = async () => {
    setError("");
    setVerification(null);
    setVerificationLoading(true);
    try {
      const response = await api.get("/api/audit/verify");
      setVerification(response.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Audit verification failed."
      );
    } finally {
      setVerificationLoading(false);
    }
  };

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      navigate("/login");
      return;
    }

    fetchLogs();
  }, [navigate, fetchLogs]);

  return (
    <div className="container-fluid bg-light min-vh-100">
      <nav className="navbar navbar-dark bg-primary px-4">
        <span className="navbar-brand fw-bold">
          TrustVault - Audit Logs
        </span>

        <button
          className="btn btn-light"
          onClick={() => navigate("/dashboard")}
        >
          Back to Dashboard
        </button>
      </nav>

      <div className="container py-4">
        <h2 className="fw-bold">Audit Logs</h2>

        <p className="text-muted">
          Monitor document activities and system events.
        </p>

        {error && (
          <div className="alert alert-danger">{error}</div>
        )}

        <div className="card shadow-sm p-4 mb-4">
          <h5>Audit Integrity Verification</h5>

          <p className="text-muted">
            Verify whether the audit event chain has been modified.
          </p>

          <button
            className="btn btn-primary"
            onClick={verifyAudit}
            disabled={verificationLoading}
          >
            {verificationLoading ? (
              <>
                <span
                  className="spinner-border spinner-border-sm me-2"
                  aria-hidden="true"
                />
                Verifying...
              </>
            ) : (
              "Verify Audit Integrity"
            )}
          </button>

          {verification && (
            <div
              className={`alert mt-3 mb-0 ${
                verification.valid
                  ? "alert-success"
                  : "alert-danger"
              }`}
            >
              {verification.valid
                ? "Audit chain integrity verified successfully."
                : verification.message ||
                  "Audit chain integrity verification failed."}
            </div>
          )}
        </div>

        <div className="card shadow-sm p-4">
          <h5 className="mb-3">System Activity History</h5>

          {loading ? (
            <div className="text-center py-4">
              <span
                className="spinner-border text-primary"
                role="status"
              >
                <span className="visually-hidden">Loading audit logs...</span>
              </span>
            </div>
          ) : logs.length === 0 ? (
            <p className="text-muted">No audit records found.</p>
          ) : (
            <div className="table-responsive">
              <table className="table table-bordered align-middle">
                <thead className="table-light">
                  <tr>
                    <th>Activity</th>
                    <th>User ID</th>
                    <th>Document ID</th>
                    <th>Details</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>

                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td>
                        <span className="badge bg-primary">
                          {log.action}
                        </span>
                      </td>

                      <td>{log.user_id}</td>

                      <td>
                        {log.document_id || "—"}
                      </td>

                      <td>
                        {log.details && Object.keys(log.details).length > 0 ? (
                          <details>
                            <summary>View details</summary>
                            <pre className="small text-wrap mb-0 mt-2">
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                          </details>
                        ) : (
                          "—"
                        )}
                      </td>

                      <td>
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AuditLogs;