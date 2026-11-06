import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: "ADMIN" | "USER";
  is_active: boolean;
  created_at: string;
}

interface AdminDocument {
  id: string;
  filename: string;
  content_type: string;
  file_size: number;
  created_at: string;
  owner_id: string;
  owner_name: string;
  owner_email: string;
  is_deleted: boolean;
  active_viewer_count: number;
}

interface AdminDocumentDetail {
  document: AdminDocument;
  permissions: Array<{
    id: string;
    recipient_name: string;
    recipient_email: string;
    permission: string;
    created_at: string;
    revoked_at: string | null;
  }>;
  sharing_history: Array<{
    id: string;
    user_id: string | null;
    action: string;
    details: Record<string, unknown> | null;
    timestamp: string;
  }>;
}

interface UserPage {
  items: AdminUser[];
  total: number;
  active_count: number;
  admin_count: number;
}

interface DocumentPage {
  items: AdminDocument[];
  total: number;
}

type AdminSection = "overview" | "users" | "documents";
type PendingUserAction =
  | { kind: "role"; user: AdminUser }
  | { kind: "status"; user: AdminUser };

function getErrorMessage(error: unknown, fallback: string) {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof error.response === "object" &&
    error.response !== null &&
    "data" in error.response &&
    typeof error.response.data === "object" &&
    error.response.data !== null &&
    "detail" in error.response.data &&
    typeof error.response.data.detail === "string"
  ) {
    return error.response.data.detail;
  }
  return fallback;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function AdminDashboard() {
  const navigate = useNavigate();
  const [authorized, setAuthorized] = useState(false);
  const [adminName, setAdminName] = useState("");
  const [adminId, setAdminId] = useState("");
  const [section, setSection] = useState<AdminSection>("overview");
  const [users, setUsers] = useState<UserPage>({
    items: [],
    total: 0,
    active_count: 0,
    admin_count: 0,
  });
  const [documents, setDocuments] = useState<DocumentPage>({
    items: [],
    total: 0,
  });
  const [userSearch, setUserSearch] = useState("");
  const [userRole, setUserRole] = useState("");
  const [userStatus, setUserStatus] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [ownerSearch, setOwnerSearch] = useState("");
  const [userPage, setUserPage] = useState(0);
  const [documentPage, setDocumentPage] = useState(0);
  const [usersLoading, setUsersLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pendingUserAction, setPendingUserAction] =
    useState<PendingUserAction | null>(null);
  const [transferDocument, setTransferDocument] =
    useState<AdminDocument | null>(null);
  const [transferSearch, setTransferSearch] = useState("");
  const [transferCandidates, setTransferCandidates] = useState<AdminUser[]>([]);
  const [newOwnerEmail, setNewOwnerEmail] = useState("");
  const [transferConfirmed, setTransferConfirmed] = useState(false);
  const [selectedDocument, setSelectedDocument] =
    useState<AdminDocumentDetail | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [userReloadKey, setUserReloadKey] = useState(0);
  const [documentReloadKey, setDocumentReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }

    api.get("/api/auth/me")
      .then(({ data }) => {
        if (!active) return;
        if (data.role !== "ADMIN") {
          navigate("/dashboard", { replace: true });
          return;
        }
        setAdminName(data.name);
        setAdminId(data.id);
        setAuthorized(true);
      })
      .catch(() => {
        if (active) navigate("/login", { replace: true });
      });

    return () => {
      active = false;
    };
  }, [navigate]);

  useEffect(() => {
    if (!authorized) return;
    let active = true;
    const timer = window.setTimeout(() => {
      setUsersLoading(true);
      api.get<UserPage>("/api/admin/users", {
        params: {
          q: userSearch.trim() || undefined,
          role: userRole || undefined,
          is_active: userStatus === "" ? undefined : userStatus === "active",
          skip: userPage * 25,
          limit: 25,
        },
      })
        .then(({ data }) => {
          if (active) setUsers(data);
        })
        .catch((requestError: unknown) => {
          if (active) setError(getErrorMessage(requestError, "Unable to load users."));
        })
        .finally(() => {
          if (active) setUsersLoading(false);
        });
    }, userSearch ? 250 : 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [authorized, userSearch, userRole, userStatus, userPage, userReloadKey]);

  useEffect(() => {
    if (!authorized) return;
    let active = true;
    const timer = window.setTimeout(() => {
      setDocumentsLoading(true);
      api.get<DocumentPage>("/api/admin/documents", {
        params: {
          q: documentSearch.trim() || undefined,
          owner_email: ownerSearch.trim() || undefined,
          skip: documentPage * 25,
          limit: 25,
        },
      })
        .then(({ data }) => {
          if (active) setDocuments(data);
        })
        .catch((requestError: unknown) => {
          if (active) {
            setError(
              getErrorMessage(requestError, "Unable to load documents."),
            );
          }
        })
        .finally(() => {
          if (active) setDocumentsLoading(false);
        });
    }, documentSearch || ownerSearch ? 250 : 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [
    authorized,
    documentSearch,
    ownerSearch,
    documentPage,
    documentReloadKey,
  ]);

  useEffect(() => {
    if (!transferDocument) return;
    let active = true;
    const timer = window.setTimeout(() => {
      api.get<UserPage>("/api/admin/users", {
        params: {
          q: transferSearch.trim() || undefined,
          is_active: true,
          skip: 0,
          limit: 50,
        },
      })
        .then(({ data }) => {
          if (active) {
            setTransferCandidates(
              data.items.filter((user) => user.id !== transferDocument.owner_id),
            );
          }
        })
        .catch((requestError: unknown) => {
          if (active) {
            setError(
              getErrorMessage(requestError, "Unable to search active users."),
            );
          }
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [transferDocument, transferSearch]);

  const closeTransfer = () => {
    setTransferDocument(null);
    setTransferCandidates([]);
    setTransferSearch("");
    setNewOwnerEmail("");
    setTransferConfirmed(false);
  };

  const confirmUserAction = async () => {
    if (!pendingUserAction) return;
    setActionLoading(true);
    setError("");
    setMessage("");
    const { user } = pendingUserAction;
    try {
      if (pendingUserAction.kind === "role") {
        const role = user.role === "ADMIN" ? "USER" : "ADMIN";
        await api.patch(`/api/admin/users/${user.id}/role`, { role });
        setMessage(`${user.email} is now ${role}.`);
      } else {
        const is_active = !user.is_active;
        await api.patch(`/api/admin/users/${user.id}/status`, { is_active });
        setMessage(`${user.email} was ${is_active ? "activated" : "deactivated"}.`);
      }
      setPendingUserAction(null);
      setUserReloadKey((key) => key + 1);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The account update failed."));
    } finally {
      setActionLoading(false);
    }
  };

  const submitTransfer = async () => {
    if (!transferDocument || !newOwnerEmail || !transferConfirmed) return;
    setActionLoading(true);
    setError("");
    setMessage("");
    try {
      await api.post(
        `/api/admin/documents/${transferDocument.id}/transfer`,
        { new_owner_email: newOwnerEmail },
      );
      setMessage(`Ownership of ${transferDocument.filename} was transferred.`);
      closeTransfer();
      setDocumentReloadKey((key) => key + 1);
      if (selectedDocument?.document.id === transferDocument.id) {
        setSelectedDocument(null);
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Ownership transfer failed."));
    } finally {
      setActionLoading(false);
    }
  };

  const showDocumentDetails = useCallback(async (documentId: string) => {
    setDetailsLoading(true);
    setError("");
    try {
      const { data } = await api.get<AdminDocumentDetail>(
        `/api/admin/documents/${documentId}`,
      );
      setSelectedDocument(data);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load document details."));
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  const logout = () => {
    localStorage.removeItem("access_token");
    navigate("/login", { replace: true });
  };

  const summaryCards = useMemo(
    () => [
      { label: "Registered users", value: users.total, icon: "USERS" },
      { label: "Active accounts", value: users.active_count, icon: "ACTIVE" },
      { label: "Administrators", value: users.admin_count, icon: "ADMINS" },
      { label: "Documents", value: documents.total, icon: "FILES" },
    ],
    [users, documents.total],
  );

  if (!authorized) {
    return (
      <main className="container min-vh-100 d-flex align-items-center justify-content-center">
        <div className="text-center" role="status">
          <span className="spinner-border text-primary" />
          <p className="text-muted mt-3">Checking administrator access...</p>
        </div>
      </main>
    );
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-brand">
          <span className="admin-brand-mark">T</span>
          <span>TrustVault <small>ADMIN</small></span>
        </div>
        <nav className="admin-nav" aria-label="Admin navigation">
          {([
            ["overview", "Overview"],
            ["users", "User Management"],
            ["documents", "Document Management"],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              className={`admin-nav-link ${section === id ? "active" : ""}`}
              onClick={() => setSection(id)}
            >
              {label}
            </button>
          ))}
          <button className="admin-nav-link" onClick={() => navigate("/audit")}>
            Audit Logs
          </button>
          <button className="admin-nav-link" onClick={() => navigate("/dashboard")}>
            Back to User Dashboard
          </button>
        </nav>
        <div className="admin-sidebar-footer">
          <span>{adminName}</span>
          <button className="btn btn-outline-light btn-sm w-100 mt-2" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>

      <main className="admin-main">
        <header className="admin-page-header">
          <div>
            <p className="text-primary fw-semibold mb-1">TRUSTVAULT ADMINISTRATION</p>
            <h1>
              {section === "overview"
                ? "Admin Overview"
                : section === "users"
                  ? "User Management"
                  : "Document Management"}
            </h1>
            <p className="text-muted mb-0">
              Manage accounts and document ownership securely.
            </p>
          </div>
          <span className="badge text-bg-light border">Signed in as {adminName}</span>
        </header>

        {message && (
          <div className="alert alert-success alert-dismissible" role="status">
            {message}
            <button className="btn-close" aria-label="Dismiss" onClick={() => setMessage("")} />
          </div>
        )}
        {error && (
          <div className="alert alert-danger alert-dismissible" role="alert">
            {error}
            <button className="btn-close" aria-label="Dismiss" onClick={() => setError("")} />
          </div>
        )}

        <section className="admin-summary-grid" aria-label="Platform summary">
          {summaryCards.map((card) => (
            <article className="admin-summary-card" key={card.label}>
              <span className="admin-summary-icon">{card.icon}</span>
              <p>{card.label}</p>
              <strong>{card.value}</strong>
            </article>
          ))}
        </section>

        {section === "overview" && (
          <section className="admin-overview-grid">
            <article className="admin-panel">
              <div className="admin-panel-heading">
                <div>
                  <h2>Account administration</h2>
                  <p>Review and update TrustVault account access.</p>
                </div>
                <button className="btn btn-primary" onClick={() => setSection("users")}>
                  Manage users
                </button>
              </div>
              <p className="mb-0 text-muted">
                Role and status changes are protected by server-side administrator
                checks and recorded in the existing audit chain.
              </p>
            </article>
            <article className="admin-panel">
              <div className="admin-panel-heading">
                <div>
                  <h2>Document ownership</h2>
                  <p>Inspect metadata, sharing history, and ownership.</p>
                </div>
                <button className="btn btn-primary" onClick={() => setSection("documents")}>
                  Manage documents
                </button>
              </div>
              <p className="mb-0 text-muted">
                Admin views expose metadata only; they do not grant access to
                private document content.
              </p>
            </article>
          </section>
        )}

        {section === "users" && (
          <section className="admin-panel">
            <div className="admin-panel-heading">
              <div>
                <h2>Registered accounts</h2>
                <p>Search and filter accounts, then confirm sensitive changes.</p>
              </div>
              <span className="badge text-bg-light border">{users.total} users</span>
            </div>
            <div className="admin-filter-row">
              <input
                className="form-control"
                type="search"
                placeholder="Search name or email"
                value={userSearch}
                onChange={(event) => {
                  setUserSearch(event.target.value);
                  setUserPage(0);
                }}
              />
              <select
                className="form-select"
                aria-label="Filter by account role"
                value={userRole}
                onChange={(event) => {
                  setUserRole(event.target.value);
                  setUserPage(0);
                }}
              >
                <option value="">All roles</option>
                <option value="ADMIN">Admin</option>
                <option value="USER">User</option>
              </select>
              <select
                className="form-select"
                aria-label="Filter by account status"
                value={userStatus}
                onChange={(event) => {
                  setUserStatus(event.target.value);
                  setUserPage(0);
                }}
              >
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            {usersLoading ? (
              <div className="admin-loading"><span className="spinner-border text-primary" /> Loading users...</div>
            ) : users.items.length === 0 ? (
              <p className="admin-empty">No users match these filters.</p>
            ) : (
              <div className="table-responsive">
                <table className="table align-middle admin-table">
                  <thead><tr><th>User ID</th><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Registered</th><th>Actions</th></tr></thead>
                  <tbody>
                    {users.items.map((user) => (
                      <tr key={user.id}>
                        <td><code>{user.id.slice(0, 8)}</code></td>
                        <td className="fw-semibold">{user.name}</td>
                        <td>{user.email}</td>
                        <td><span className={`badge ${user.role === "ADMIN" ? "text-bg-primary" : "text-bg-secondary"}`}>{user.role}</span></td>
                        <td><span className={`badge ${user.is_active ? "text-bg-success" : "text-bg-danger"}`}>{user.is_active ? "Active" : "Inactive"}</span></td>
                        <td>{new Date(user.created_at).toLocaleDateString()}</td>
                        <td>
                          <div className="d-flex flex-wrap gap-2">
                            <button
                              className="btn btn-outline-primary btn-sm"
                              onClick={() => setPendingUserAction({ kind: "role", user })}
                            >
                              {user.role === "ADMIN" ? "Demote" : "Promote"}
                            </button>
                            <button
                              className="btn btn-outline-secondary btn-sm"
                              disabled={user.id === adminId && user.is_active}
                              onClick={() => setPendingUserAction({ kind: "status", user })}
                            >
                              {user.is_active ? "Deactivate" : "Activate"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination
              page={userPage}
              total={users.total}
              pageSize={25}
              onPageChange={setUserPage}
            />
          </section>
        )}

        {section === "documents" && (
          <section className="admin-panel">
            <div className="admin-panel-heading">
              <div>
                <h2>Documents</h2>
                <p>Manage metadata and ownership without exposing file contents.</p>
              </div>
              <span className="badge text-bg-light border">{documents.total} documents</span>
            </div>
            <div className="admin-filter-row">
              <input
                className="form-control"
                type="search"
                placeholder="Search filename"
                value={documentSearch}
                onChange={(event) => {
                  setDocumentSearch(event.target.value);
                  setDocumentPage(0);
                }}
              />
              <input
                className="form-control"
                type="search"
                placeholder="Filter owner email"
                value={ownerSearch}
                onChange={(event) => {
                  setOwnerSearch(event.target.value);
                  setDocumentPage(0);
                }}
              />
            </div>
            {documentsLoading ? (
              <div className="admin-loading"><span className="spinner-border text-primary" /> Loading documents...</div>
            ) : documents.items.length === 0 ? (
              <p className="admin-empty">No documents match these filters.</p>
            ) : (
              <div className="table-responsive">
                <table className="table align-middle admin-table">
                  <thead><tr><th>Filename</th><th>Type</th><th>Current owner</th><th>Uploaded</th><th>Status</th><th>Active viewers</th><th>Actions</th></tr></thead>
                  <tbody>
                    {documents.items.map((document) => (
                      <tr key={document.id}>
                        <td className="fw-semibold">{document.filename}</td>
                        <td>{document.content_type.split("/").pop()?.toUpperCase()}</td>
                        <td>{document.owner_name}<small className="d-block text-muted">{document.owner_email}</small></td>
                        <td>{new Date(document.created_at).toLocaleDateString()}</td>
                        <td><span className={`badge ${document.is_deleted ? "text-bg-secondary" : "text-bg-success"}`}>{document.is_deleted ? "Deleted" : "Available"}</span></td>
                        <td>{document.active_viewer_count}</td>
                        <td>
                          <div className="d-flex flex-wrap gap-2">
                            <button className="btn btn-outline-secondary btn-sm" onClick={() => showDocumentDetails(document.id)}>
                              Details
                            </button>
                            <button
                              className="btn btn-primary btn-sm"
                              disabled={document.is_deleted}
                              onClick={() => {
                                setTransferDocument(document);
                                setTransferSearch("");
                                setTransferConfirmed(false);
                              }}
                            >
                              Transfer owner
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination
              page={documentPage}
              total={documents.total}
              pageSize={25}
              onPageChange={setDocumentPage}
            />
          </section>
        )}
      </main>

      {pendingUserAction && (
        <div className="admin-modal-layer">
          <div className="modal-backdrop show" />
          <div className="modal d-block" role="dialog" aria-modal="true" aria-labelledby="user-action-title">
            <div className="modal-dialog modal-dialog-centered">
              <div className="modal-content">
                <div className="modal-header">
                  <h2 className="modal-title fs-5" id="user-action-title">Confirm account change</h2>
                  <button className="btn-close" aria-label="Close" disabled={actionLoading} onClick={() => setPendingUserAction(null)} />
                </div>
                <div className="modal-body">
                  {pendingUserAction.kind === "role"
                    ? <>Change <strong>{pendingUserAction.user.email}</strong> from {pendingUserAction.user.role} to {pendingUserAction.user.role === "ADMIN" ? "USER" : "ADMIN"}?</>
                    : <>{pendingUserAction.user.is_active ? "Deactivate" : "Activate"} <strong>{pendingUserAction.user.email}</strong>?</>}
                  <p className="text-muted mt-3 mb-0">This action is recorded in the audit log. The server will prevent removing the last active administrator.</p>
                </div>
                <div className="modal-footer">
                  <button className="btn btn-outline-secondary" disabled={actionLoading} onClick={() => setPendingUserAction(null)}>Cancel</button>
                  <button className="btn btn-primary" disabled={actionLoading} onClick={confirmUserAction}>
                    {actionLoading ? "Saving..." : "Confirm"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {transferDocument && (
        <div className="admin-modal-layer">
          <div className="modal-backdrop show" />
          <div className="modal d-block" role="dialog" aria-modal="true" aria-labelledby="transfer-title">
            <div className="modal-dialog modal-dialog-centered">
              <div className="modal-content">
                <div className="modal-header">
                  <h2 className="modal-title fs-5" id="transfer-title">Transfer document ownership</h2>
                  <button className="btn-close" aria-label="Close" disabled={actionLoading} onClick={closeTransfer} />
                </div>
                <div className="modal-body">
                  <p><strong>Document:</strong> {transferDocument.filename}</p>
                  <p><strong>Current owner:</strong> {transferDocument.owner_email}</p>
                  <label className="form-label" htmlFor="transfer-user-search">Search active users</label>
                  <input
                    id="transfer-user-search"
                    className="form-control mb-2"
                    type="search"
                    placeholder="Search by name or email"
                    value={transferSearch}
                    onChange={(event) => {
                      setTransferSearch(event.target.value);
                      setNewOwnerEmail("");
                    }}
                  />
                  <select
                    className="form-select"
                    aria-label="Select new owner"
                    value={newOwnerEmail}
                    onChange={(event) => setNewOwnerEmail(event.target.value)}
                  >
                    <option value="">Choose an active user</option>
                    {transferCandidates.map((candidate) => (
                      <option key={candidate.id} value={candidate.email}>
                        {candidate.name} — {candidate.email}
                      </option>
                    ))}
                  </select>
                  <div className="alert alert-warning mt-3 mb-2">
                    The selected user becomes the owner; the previous owner loses owner-only privileges. Other viewer permissions and history are retained.
                  </div>
                  <div className="form-check">
                    <input
                      id="confirm-transfer"
                      className="form-check-input"
                      type="checkbox"
                      checked={transferConfirmed}
                      onChange={(event) => setTransferConfirmed(event.target.checked)}
                    />
                    <label className="form-check-label" htmlFor="confirm-transfer">
                      I confirm this ownership transfer.
                    </label>
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn btn-outline-secondary" disabled={actionLoading} onClick={closeTransfer}>Cancel</button>
                  <button
                    className="btn btn-primary"
                    disabled={actionLoading || !newOwnerEmail || !transferConfirmed}
                    onClick={submitTransfer}
                  >
                    {actionLoading ? "Transferring..." : "Confirm transfer"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedDocument && (
        <div className="admin-modal-layer">
          <div className="modal-backdrop show" />
          <div className="modal d-block" role="dialog" aria-modal="true" aria-labelledby="document-detail-title">
            <div className="modal-dialog modal-lg modal-dialog-scrollable">
              <div className="modal-content">
                <div className="modal-header">
                  <h2 className="modal-title fs-5" id="document-detail-title">Document details</h2>
                  <button className="btn-close" aria-label="Close" onClick={() => setSelectedDocument(null)} />
                </div>
                <div className="modal-body">
                  <h3 className="h6">{selectedDocument.document.filename}</h3>
                  <p className="text-muted">
                    Owner: {selectedDocument.document.owner_name} ({selectedDocument.document.owner_email})
                    <br />Type: {selectedDocument.document.content_type}
                    <br />Size: {formatFileSize(selectedDocument.document.file_size)}
                    <br />Uploaded: {new Date(selectedDocument.document.created_at).toLocaleString()}
                  </p>
                  <h3 className="h6 mt-4">Viewer permissions</h3>
                  {selectedDocument.permissions.length === 0 ? (
                    <p className="text-muted">No permission history.</p>
                  ) : (
                    <div className="table-responsive">
                      <table className="table table-sm">
                        <thead><tr><th>Recipient</th><th>Permission</th><th>Status</th><th>Granted</th></tr></thead>
                        <tbody>{selectedDocument.permissions.map((permission) => (
                          <tr key={permission.id}>
                            <td>{permission.recipient_name}<small className="d-block text-muted">{permission.recipient_email}</small></td>
                            <td>{permission.permission}</td>
                            <td>{permission.revoked_at ? "Revoked" : "Active"}</td>
                            <td>{new Date(permission.created_at).toLocaleString()}</td>
                          </tr>
                        ))}</tbody>
                      </table>
                    </div>
                  )}
                  <h3 className="h6 mt-4">Sharing and transfer history</h3>
                  {selectedDocument.sharing_history.length === 0 ? (
                    <p className="text-muted">No sharing history.</p>
                  ) : (
                    <ul className="list-group">
                      {selectedDocument.sharing_history.map((event) => (
                        <li className="list-group-item" key={event.id}>
                          <strong>{event.action}</strong>
                          <span className="d-block text-muted small">{new Date(event.timestamp).toLocaleString()}</span>
                          {event.details && <pre className="small text-wrap mb-0 mt-2">{JSON.stringify(event.details, null, 2)}</pre>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="modal-footer">
                  <button className="btn btn-secondary" onClick={() => setSelectedDocument(null)}>Close</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      {detailsLoading && (
        <div className="admin-details-loading" role="status">
          <span className="spinner-border text-primary" />
          <span className="visually-hidden">Loading document details</span>
        </div>
      )}
    </div>
  );
}

function Pagination({
  page,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  if (pageCount <= 1) return null;
  return (
    <div className="admin-pagination">
      <button className="btn btn-outline-secondary btn-sm" disabled={page === 0} onClick={() => onPageChange(page - 1)}>
        Previous
      </button>
      <span>Page {page + 1} of {pageCount}</span>
      <button className="btn btn-outline-secondary btn-sm" disabled={page + 1 >= pageCount} onClick={() => onPageChange(page + 1)}>
        Next
      </button>
    </div>
  );
}

export default AdminDashboard;
