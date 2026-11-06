import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

interface Document {
  id: string;
  filename: string;
  file_size?: number;
  created_at?: string;
}
interface UserProfile {
  name: string;
  email: string;
  role: string;
}
interface Permission {
  id: string;
  document_id: string;
  user_id: string;
  permission: string;
  recipient_email?: string | null;
  granted_by: string;
  created_at: string;
  revoked_at: string | null;
}

function formatFileSize(size?: number) {
  if (size === undefined) {
    return "—";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function Dashboard() {
  const navigate = useNavigate();

  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [sharedDocuments, setSharedDocuments] = useState<Document[]>([]);
  const [sharedLoading, setSharedLoading] = useState(false);
  const [sharedSearchQuery, setSharedSearchQuery] = useState("");
  const [selectedSharedDocument, setSelectedSharedDocument] =
    useState<Document | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [viewingPermissionsId, setViewingPermissionsId] =
  useState<string | null>(null);
  const [permissionsLoading, setPermissionsLoading] = useState(false);

  // Sharing states
  const [sharingDocumentId, setSharingDocumentId] = useState<string | null>(null);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [sharingLoading, setSharingLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
const [searchLoading, setSearchLoading] = useState(false);


  const fetchDocuments = useCallback(async () => {
    try {
      const response = await api.get("/api/documents/");
      setDocuments(response.data);
    } catch {
      setError("Unable to load documents.");
    }
  }, []);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const response = await api.get("/api/auth/me");
      setCurrentUser(response.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Unable to load account details."
      );
    }
  }, []);

  const fetchSharedDocuments = useCallback(async () => {
    try {
      setSharedLoading(true);

      const response = await api.get(
        "/api/documents/shared-with-me"
      );

      setSharedDocuments(response.data);
      setSelectedSharedDocument((selected) =>
        selected &&
        !response.data.some((doc: Document) => doc.id === selected.id)
          ? null
          : selected
      );
    } catch (err: any) {
      setSharedDocuments([]);
      setSelectedSharedDocument(null);
      setError(
        err.response?.data?.detail ||
        "Unable to load shared documents."
      );
    } finally {
      setSharedLoading(false);
    }
  }, []);
  const searchDocuments = async () => {
  setError("");
  if (!searchQuery.trim()) {
    await fetchDocuments();
    return;
  }

  setSearchLoading(true);
  setError("");

  try {
    const response = await api.get("/api/documents/search", {
      params: { q: searchQuery.trim() },
    });

    setDocuments(response.data);
  } catch (err: any) {
    setError(
      err.response?.data?.detail || "Document search failed."
    );
  } finally {
    setSearchLoading(false);
  }
};

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      navigate("/login");
      return;
    }

    fetchDocuments();
    fetchSharedDocuments();
    fetchCurrentUser();
  }, [navigate, fetchDocuments, fetchSharedDocuments, fetchCurrentUser]);

  useEffect(() => {
    const refreshSharedDocuments = () => {
      if (document.visibilityState === "visible") {
        fetchSharedDocuments();
      }
    };

    window.addEventListener("focus", refreshSharedDocuments);
    document.addEventListener("visibilitychange", refreshSharedDocuments);

    return () => {
      window.removeEventListener("focus", refreshSharedDocuments);
      document.removeEventListener("visibilitychange", refreshSharedDocuments);
    };
  }, [fetchSharedDocuments]);

  const uploadDocument = async () => {
    if (!file) {
      setError("Please select a document.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    setError("");
    setMessage("");

    try {
      await api.post("/api/documents/upload", formData);
      setMessage("Document uploaded successfully.");
      setFile(null);
      await fetchDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  const downloadDocument = async (id: string, filename: string) => {
    try {
      const response = await api.get(`/api/documents/${id}/download`, {
        responseType: "blob",
      });

      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");

      link.href = url;
      link.download = filename;
      link.click();

      window.URL.revokeObjectURL(url);
    } catch {
      setError("Document download failed.");
    }
  };

  const deleteDocument = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this document?")) {
      return;
    }

    try {
      await api.delete(`/api/documents/${id}`);
      setMessage("Document deleted.");
      await fetchDocuments();
    } catch {
      setError("Document deletion failed.");
    }
  };

  // Share document with another user
  const shareDocument = async (documentId: string) => {
    if (!recipientEmail.trim()) {
      setError("Please enter the recipient's email.");
      return;
    }

    setSharingLoading(true);
    setError("");
    setMessage("");

    try {
      await api.post(
        `/api/permissions/documents/${documentId}/share`,
        {
          email: recipientEmail.trim(),
          permission: "VIEWER",
        }
      );

      setMessage(`Document shared successfully with ${recipientEmail}.`);
      setRecipientEmail("");
      setSharingDocumentId(null);
      await fetchSharedDocuments();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : detail
            ? JSON.stringify(detail)
            : "Document sharing failed."
      );
    } finally {
      setSharingLoading(false);
    }
  };
  const fetchPermissions = async (documentId: string) => {
    setPermissionsLoading(true);
    setError("");
    setMessage("");

    try {
      const response = await api.get(
        `/api/permissions/documents/${documentId}`
      );

      setPermissions(response.data);
      setViewingPermissionsId(documentId);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Unable to load permissions."
      );
    } finally {
      setPermissionsLoading(false);
    }
  };

  const revokeAccess = async (permissionId: string) => {
    if (!window.confirm("Are you sure you want to revoke access?")) {
      return;
    }

    try {
      await api.delete(`/api/permissions/${permissionId}`);
      await fetchSharedDocuments();
      setMessage("Document access revoked successfully.");

      if (viewingPermissionsId) {
        await fetchPermissions(viewingPermissionsId);
      }
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Unable to revoke access."
      );
    }
  };
  const logout = () => {
    localStorage.removeItem("access_token");
    navigate("/login");
  };

  const filteredSharedDocuments = sharedDocuments.filter((doc) =>
    doc.filename.toLowerCase().includes(sharedSearchQuery.trim().toLowerCase())
  );

  return (
    <div className="container-fluid bg-light min-vh-100">
      <nav className="navbar navbar-dark bg-primary px-4">
        <span className="navbar-brand fw-bold">TrustVault</span>
        <div className="d-flex align-items-center gap-2">
          {currentUser && (
            <span className="navbar-text text-white d-none d-md-inline">
              {currentUser.name}
            </span>
          )}
          {currentUser?.role === "ADMIN" && (
            <>
              <button
                className="btn btn-light"
                onClick={() => navigate("/admin")}
              >
                Admin Dashboard
              </button>
              <button
                className="btn btn-light"
                onClick={() => navigate("/audit")}
              >
                Audit Logs
              </button>
            </>
          )}
          <button className="btn btn-light" onClick={logout}>
            Logout
          </button>
        </div>
      </nav>

      <div className="container py-4">
        <h2 className="fw-bold">Dashboard</h2>
        <p className="text-muted">Manage your secure documents.</p>

        {message && (
          <div className="alert alert-success">{message}</div>
        )}

        {error && (
          <div className="alert alert-danger">{error}</div>
        )}

        <div className="card shadow-sm p-4 mb-4">
          <h5>Upload Document</h5>

          <input
            type="file"
            className="form-control my-3"
            accept=".pdf,.docx"
            onChange={(e) =>
              setFile(e.target.files?.[0] || null)
            }
          />

          <button
            className="btn btn-primary"
            onClick={uploadDocument}
            disabled={loading}
          >
            {loading ? "Uploading..." : "Upload Document"}
          </button>
        </div>

        <div className="card shadow-sm p-4">
  <h5 className="mb-3">My Documents</h5>

  {/* Document Search Bar */}
  <div className="input-group mb-3">
    <input
      type="text"
      className="form-control"
      placeholder="Search documents by filename..."
      value={searchQuery}
      onChange={(e) => setSearchQuery(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") searchDocuments();
      }}
    />

    <button
      className="btn btn-primary"
      onClick={searchDocuments}
      disabled={searchLoading}
    >
      {searchLoading ? "Searching..." : "Search"}
    </button>

    <button
      className="btn btn-secondary"
      onClick={() => {
        setSearchQuery("");
        fetchDocuments();
      }}
    >
      Reset
    </button>
  </div>

  {documents.length === 0 ? (
    <p className="text-muted">
      {searchQuery.trim()
        ? "No documents match your search."
        : "No documents available."}
    </p>
          ) : (
            <div className="table-responsive">
              <table className="table table-bordered align-middle">
                <thead className="table-light">
                  <tr>
                    <th>Filename</th>
                    <th>Size</th>
                    <th>Uploaded</th>
                    <th>Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id}>
                      <td>{doc.filename}</td>

                      <td>{formatFileSize(doc.file_size)}</td>
                      <td>
                        {doc.created_at
                          ? new Date(doc.created_at).toLocaleDateString()
                          : "—"}
                      </td>

                      <td>
                        <button
                          className="btn btn-success btn-sm me-2 mb-1"
                          onClick={() =>
                            downloadDocument(doc.id, doc.filename)
                          }
                        >
                          Download
                        </button>

                        <button
                          className="btn btn-primary btn-sm me-2 mb-1"
                          onClick={() => {
                            setError("");
                            setMessage("");
                            setRecipientEmail("");
                            setSharingDocumentId(
                              sharingDocumentId === doc.id
                                ? null
                                : doc.id
                            );
                          }}
                        >
                          Share
                        </button>
                        <button
                className="btn btn-info btn-sm me-2 mb-1"
                onClick={() => fetchPermissions(doc.id)}
>
                Manage Access
                        </button>
                        <button
                          className="btn btn-danger btn-sm mb-1"
                          onClick={() => deleteDocument(doc.id)}
                        >
                          Delete
                        </button>

                        {sharingDocumentId === doc.id && (
                          <div className="border rounded p-3 mt-3">
                            <h6>Share Document</h6>

                            <label className="form-label">
                              Recipient Email
                            </label>

                            <input
                              type="email"
                              className="form-control mb-2"
                              placeholder="Enter recipient email"
                              value={recipientEmail}
                              onChange={(e) =>
                                setRecipientEmail(e.target.value)
                              }
                            />

                            <label className="form-label">
                              Permission
                            </label>

                            <input
                              className="form-control mb-3"
                              value="VIEWER"
                              disabled
                            />

                            <button
                              className="btn btn-primary btn-sm me-2"
                              onClick={() =>
                                shareDocument(doc.id)
                              }
                              disabled={sharingLoading}
                            >
                              {sharingLoading
                                ? "Sharing..."
                                : "Confirm Share"}
                            </button>

                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() =>
                                setSharingDocumentId(null)
                              }
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {/* SHARED WITH ME SECTION */}
<div className="card shadow-sm p-4 mt-4">

  <div className="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h5 className="fw-bold mb-1">Shared With Me</h5>
      <small className="text-muted">
        Documents shared with your account by other users.
      </small>
    </div>

    <button
      className="btn btn-outline-primary btn-sm"
      onClick={fetchSharedDocuments}
      disabled={sharedLoading}
    >
      <i className="bi bi-arrow-clockwise me-1"></i>
      Refresh
    </button>
  </div>

  <div className="input-group mb-3">
    <input
      type="search"
      className="form-control"
      placeholder="Filter shared documents..."
      aria-label="Filter shared documents"
      value={sharedSearchQuery}
      onChange={(e) => setSharedSearchQuery(e.target.value)}
    />
    {sharedSearchQuery && (
      <button
        className="btn btn-outline-secondary"
        onClick={() => setSharedSearchQuery("")}
      >
        Clear
      </button>
    )}
  </div>

  {sharedLoading ? (
    <div className="text-center py-4">
      <div className="spinner-border text-primary"></div>
      <p className="text-muted mt-2">
        Loading shared documents...
      </p>
    </div>
  ) : filteredSharedDocuments.length === 0 ? (
    <div className="text-center py-5">
      <i className="bi bi-folder2-open fs-1 text-secondary"></i>
      <h6 className="mt-3">
        {sharedDocuments.length === 0
          ? "No shared documents yet"
          : "No shared documents match your search"}
      </h6>
      <p className="text-muted mb-0">
        {sharedDocuments.length === 0
          ? "Documents shared with you will appear here."
          : "Try another filename or clear your search."}
      </p>
    </div>
  ) : (
    <div className="table-responsive">
      <table className="table table-hover align-middle">
        <thead className="table-light">
          <tr>
            <th>Document</th>
            <th>Size</th>
            <th>Uploaded</th>
            <th>Access Level</th>
            <th>Actions</th>
          </tr>
        </thead>

        <tbody>
          {filteredSharedDocuments.map((doc) => (
            <tr key={doc.id}>
              <td>
                <span className="badge bg-light text-secondary border me-2">
                  {doc.filename.split(".").pop()?.toUpperCase() || "FILE"}
                </span>
                <span className="fw-semibold">
                  {doc.filename}
                </span>
              </td>

              <td>{formatFileSize(doc.file_size)}</td>
              <td>
                {doc.created_at
                  ? new Date(doc.created_at).toLocaleDateString()
                  : "—"}
              </td>

              <td>
                <span className="badge bg-info text-dark">
                  VIEWER
                </span>
              </td>

              <td>
                <button
                  className="btn btn-outline-primary btn-sm me-2 mb-1"
                  onClick={async () => {
                    try {
                      const response = await api.get(
                        `/api/documents/${doc.id}`
                      );

                      setSelectedSharedDocument(response.data);
                      setError("");
                    } catch (err: any) {
                      setError(
                        err.response?.data?.detail ||
                        "Unable to view document details."
                      );
                    }
                  }}
                >
                  View Details
                </button>

                <button
                  className="btn btn-success btn-sm mb-1"
                  onClick={() =>
                    downloadDocument(doc.id, doc.filename)
                  }
                >
                  Download
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )}

  {selectedSharedDocument && (
    <div className="alert alert-info mt-3">
      <div className="d-flex justify-content-between">
        <strong>Shared Document Details</strong>

        <button
          className="btn-close"
          onClick={() => setSelectedSharedDocument(null)}
        ></button>
      </div>

      <p className="mb-1 mt-2">
        <strong>Filename:</strong>{" "}
        {selectedSharedDocument.filename}
      </p>

      <p className="mb-1">
        <strong>Size:</strong>{" "}
        {selectedSharedDocument.file_size ?? "—"}
      </p>

      <p className="mb-0">
        <strong>Access:</strong> VIEWER
      </p>
    </div>
  )}

  <div className="border-top pt-3 mt-2">
    <small className="text-muted">
      <i className="bi bi-shield-lock me-1"></i>
      You can view and download these documents.
      Only the document owner can delete or manage access.
    </small>
  </div>
</div>
{viewingPermissionsId && (
  <div className="card shadow-sm p-4 mt-4">
    <div className="d-flex justify-content-between align-items-center mb-3">
      <h5>Shared Users & Permissions</h5>

      <button
        className="btn btn-secondary btn-sm"
        onClick={() => setViewingPermissionsId(null)}
      >
        Close
      </button>
    </div>

    {permissionsLoading ? (
      <p>Loading permissions...</p>
    ) : permissions.length === 0 ? (
      <p className="text-muted">No shared users found.</p>
    ) : (
      <div className="table-responsive">
        <table className="table table-bordered align-middle">
          <thead className="table-light">
            <tr>
              <th>Recipient</th>
              <th>Permission</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>

          <tbody>
            {permissions.map((permission) => (
              <tr key={permission.id}>
                <td>
                  {permission.recipient_email || permission.user_id}
                </td>
                <td>{permission.permission}</td>

                <td>
                  {permission.revoked_at ? (
                    <span className="badge bg-secondary">
                      Revoked
                    </span>
                  ) : (
                    <span className="badge bg-success">
                      Active
                    </span>
                  )}
                </td>

                <td>
                  {!permission.revoked_at && (
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => revokeAccess(permission.id)}
                    >
                      Revoke Access
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
)}
      </div>
    </div>
  );
}

export default Dashboard;