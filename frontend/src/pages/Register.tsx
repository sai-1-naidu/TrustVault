import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../services/api";

function Register() {
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("/api/auth/register", {
        name,
        email,
        password,
      });

      navigate("/login");
    } catch (err: any) {
  const detail = err.response?.data?.detail;

  setError(
    typeof detail === "string"
      ? detail
      : detail
        ? JSON.stringify(detail)
        : "Registration failed."
  );
} finally {
      setLoading(false);
    }
  };

  return (
    <div className="container min-vh-100 d-flex justify-content-center align-items-center">
      <div className="card shadow p-4" style={{ width: "400px" }}>
        <h2 className="text-center text-primary fw-bold">Create Account</h2>
        <p className="text-center text-muted">Join TrustVault</p>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={handleRegister}>
          <label className="form-label">Full Name</label>
          <input
            className="form-control mb-3"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <label className="form-label">Email</label>
          <input
            type="email"
            className="form-control mb-3"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label className="form-label">Password</label>
          <input
            type="password"
            className="form-control mb-3"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />

          <button className="btn btn-primary w-100" disabled={loading}>
            {loading ? "Creating account..." : "Register"}
          </button>
        </form>

        <p className="text-center mt-3">
          Already registered? <Link to="/login">Login</Link>
        </p>
      </div>
    </div>
  );
}

export default Register;