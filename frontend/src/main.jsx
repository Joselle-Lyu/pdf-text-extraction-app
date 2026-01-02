import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

const API_BASE = "http://localhost:8000";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [me, setMe] = useState(null);

  const [file, setFile] = useState(null);
  const [engine, setEngine] = useState("markitdown");

  const [uploadId, setUploadId] = useState("");
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");

  const headers = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);

  // Capture token from OAuth redirect
  useEffect(() => {
    const url = new URL(window.location.href);
    const t = url.searchParams.get("token");
    if (t) {
      localStorage.setItem("token", t);
      setToken(t);
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url.toString());
    }
  }, []);

  // Load /me
  useEffect(() => {
    async function loadMe() {
      if (!token) return;
      const res = await fetch(`${API_BASE}/me`, { headers });
      if (!res.ok) return;
      setMe(await res.json());
    }
    loadMe();
  }, [token, headers]);

  // Poll job status
  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`, { headers });
      if (!res.ok) return;
      const data = await res.json();
      setJob(data);
      if (data.status === "succeeded" || data.status === "failed") clearInterval(interval);
    }, 800);
    return () => clearInterval(interval);
  }, [jobId, headers]);

  async function doUpload() {
    setError("");
    setUploadId("");
    setJobId("");
    setJob(null);

    if (!file) return setError("Please choose a PDF file first.");

    const form = new FormData();
    form.append("file", file);

    const res = await fetch(`${API_BASE}/uploads`, {
      method: "POST",
      headers,
      body: form,
    });

    if (!res.ok) return setError(`Upload failed: ${await res.text()}`);

    const data = await res.json();
    setUploadId(data.upload_id);
  }

  async function startJob() {
    setError("");
    setJob(null);
    if (!uploadId) return setError("Upload a PDF first.");

    const res = await fetch(`${API_BASE}/jobs`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ upload_id: uploadId, engine }),
    });

    if (!res.ok) return setError(`Create job failed: ${await res.text()}`);

    const data = await res.json();
    setJobId(data.job_id);
  }

  function signOut() {
    localStorage.removeItem("token");
    setToken("");
    setMe(null);
    setFile(null);
    setEngine("markitdown");
    setUploadId("");
    setJobId("");
    setJob(null);
    setError("");
  }

  return (
    <div style={{ fontFamily: "system-ui", padding: 24, maxWidth: 900 }}>
      <h1>PDF Extractor</h1>

      {!token ? (
        <a href={`${API_BASE}/auth/github/login`}>
          <button>Sign in with GitHub</button>
        </a>
      ) : (
        <>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div>
              Signed in as <b>{me?.login || "..."}</b>
            </div>
            <button onClick={signOut}>Sign out</button>
          </div>

          <hr style={{ margin: "18px 0" }} />

          <h2>Upload PDF</h2>
          <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <div style={{ marginTop: 10 }}>
            <button onClick={doUpload} disabled={!file}>
              Upload
            </button>
          </div>
          {uploadId && (
            <p>
              ✅ Uploaded. <code>{uploadId}</code>
            </p>
          )}

          <h2>Choose engine</h2>
          <select value={engine} onChange={(e) => setEngine(e.target.value)}>
            <option value="markitdown">markitdown (fast)</option>
            <option value="mineru">MinerU (medium)</option>
            <option value="tesseract">Tesseract OCR (slow)</option>
          </select>

          <div style={{ marginTop: 10 }}>
            <button onClick={startJob} disabled={!uploadId}>
              Start extraction
            </button>
          </div>

          <h2>Job status</h2>
          {jobId ? <p>Tracking: <code>{jobId}</code></p> : <p>No job yet.</p>}

          {job && (
            <div style={{ border: "1px solid #ddd", padding: 12, borderRadius: 8 }}>
              <div>
                Status: <b>{job.status}</b> (engine: {job.engine})
              </div>
              {job.error && <pre style={{ whiteSpace: "pre-wrap" }}>{job.error}</pre>}
              {job.result ? (
                <pre style={{ whiteSpace: "pre-wrap", maxHeight: 360, overflow: "auto" }}>{job.result}</pre>
              ) : (
                <p style={{ color: "#666" }}>Waiting for result...</p>
              )}
            </div>
          )}

          {error && (
            <p style={{ color: "crimson" }}>
              <b>{error}</b>
            </p>
          )}
        </>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);