"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type Skill = { id: string; slug: string; name: string; description: string };
type Version = { id: string; skill_id: string; version: string; status: string; artifact_hash: string };
type Dataset = { id: string; name: string; dataset_type: string; split: "dev" | "holdout"; is_locked: boolean };
type Release = { id: string; skill_version_id: string; release_state: string; released_at: string };
type Gate = { decision: "passed" | "failed" | "incomplete"; summary: { failures?: string[]; missing_holdout?: string[] } };
type Job = { id: string; status: string; job_type: string };
type EngineHealth = Record<string, { available: boolean; detail: string }>;
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [status, setStatus] = useState("Loading registry…");
  const [file, setFile] = useState<File | null>(null);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [engines, setEngines] = useState<EngineHealth>({});
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [releases, setReleases] = useState<Release[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
  const [gate, setGate] = useState<Gate | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadSkills() {
    const response = await fetch(`${apiUrl}/skills`);
    if (!response.ok) throw new Error("Registry unavailable");
    const data = await response.json() as Skill[];
    setSkills(data); setStatus(data.length ? `${data.length} registered` : "No Skills registered");
  }

  useEffect(() => {
    void loadSkills().catch(() => setStatus("API offline — start FastAPI to load the registry"));
    void fetch(`${apiUrl}/settings/engines`).then((r) => r.json() as Promise<EngineHealth>).then(setEngines).catch(() => undefined);
  }, []);

  async function selectVersion(version: Version) {
    setSelectedVersion(version);
    try { const response = await fetch(`${apiUrl}/versions/${version.id}/eval-summary`); setGate(response.ok ? await response.json() as Gate | null : null); }
    catch { setGate(null); }
  }

  async function selectSkill(skill: Skill) {
    setSelectedSkill(skill); setGate(null); setSelectedVersion(null);
    try {
      const [versionData, datasetData, releaseData] = await Promise.all([
        fetch(`${apiUrl}/skills/${skill.id}/versions`).then((r) => r.json() as Promise<Version[]>),
        fetch(`${apiUrl}/eval-datasets?skill_id=${skill.id}`).then((r) => r.json() as Promise<Dataset[]>),
        fetch(`${apiUrl}/skills/${skill.id}/releases`).then((r) => r.json() as Promise<Release[]>),
      ]);
      setVersions(versionData); setDatasets(datasetData); setReleases(releaseData);
      if (versionData[0]) await selectVersion(versionData[0]);
    } catch { setStatus("Could not load the version workbench."); }
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null; setFile(selected);
    if (selected && !slug) setSlug(selected.name.replace(/\.zip$/i, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
    if (selected && !name) setName(selected.name.replace(/\.zip$/i, ""));
  }

  async function importSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!file) return setStatus("Choose a .zip Skill package first.");
    const form = new FormData(); form.set("archive", file); form.set("slug", slug); form.set("name", name); form.set("description", "Imported through the governed registry.");
    setStatus("Validating and registering immutable artifact…");
    const response = await fetch(`${apiUrl}/skills/import`, { method: "POST", body: form });
    const body = await response.json().catch(() => null) as { detail?: string; skill?: Skill } | null;
    if (!response.ok || !body?.skill) return setStatus(body?.detail ?? "Import failed.");
    setSkills((current) => [body.skill!, ...current]); setStatus(`Registered ${body.skill.name} as version 0.1.0.`); setFile(null);
  }

  async function queueJob(event: FormEvent<HTMLFormElement>, route: string) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const payload: Record<string, unknown> = Object.fromEntries(form.entries());
    if (typeof payload.constraints === "string") payload.constraints = payload.constraints.split("\n").filter(Boolean);
    setStatus("Queueing isolated engine job…");
    const response = await fetch(`${apiUrl}${route}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const body = await response.json().catch(() => null) as Job & { detail?: string } | null;
    if (!response.ok || !body?.id) return setStatus(body?.detail ?? "Could not queue job.");
    setJob(body); setStatus(`Job ${body.id.slice(0, 8)} queued. Start the worker to process it.`);
  }

  async function operate(action: "evaluate" | "promote" | "rollback", releaseId?: string) {
    if (!selectedSkill || !selectedVersion) return; setBusy(true);
    const active = releases.find((release) => release.release_state === "active");
    const request = action === "evaluate"
      ? { url: `/versions/${selectedVersion.id}/evaluate-holdouts`, body: { engine: "fixture", baseline_version_id: active?.skill_version_id } }
      : action === "promote" ? { url: `/versions/${selectedVersion.id}/promote`, body: { reason: "Approved from the version workbench", manual_override: false } }
      : { url: `/skills/${selectedSkill.id}/rollback`, body: { target_release_id: releaseId, reason: "Operator-selected release history rollback" } };
    try {
      const response = await fetch(`${apiUrl}${request.url}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request.body) });
      const body = await response.json().catch(() => null) as { detail?: string; decision?: Gate } | null;
      if (!response.ok) throw new Error(body?.detail ?? "Operation failed.");
      setStatus(action === "evaluate" ? `Holdout gate: ${body?.decision?.decision ?? "recorded"}.` : action === "promote" ? "Production pointer updated atomically." : "Rollback pointer updated atomically.");
      await selectSkill(selectedSkill);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Operation failed."); }
    finally { setBusy(false); }
  }

  const activeRelease = releases.find((release) => release.release_state === "active");
  return <main className="shell">
    <section className="masthead"><p className="eyebrow">OPC / SKILL OPS</p><h1>Make skill changes<br /><em>earn</em> production.</h1><p className="lede">A registry where every artifact has a hash, a history, and a way home.</p><div className="signal"><span className="signal-dot" /> {status}</div></section>
    <section className="control-panel" aria-labelledby="import-title"><div><p className="eyebrow">V1.0 / FOUNDATION</p><h2 id="import-title">Register a portable Skill</h2><p>Import is inert: scripts are retained but never executed. The package is normalized, hashed, and stored as an immutable version.</p></div><form onSubmit={importSkill} className="import-form"><label className="file-drop"><input type="file" accept=".zip,application/zip" onChange={chooseFile} /><span>{file?.name ?? "Choose .zip package"}</span></label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Skill name" required /><input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="skill-slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" required /><button type="submit">Normalize & register <span>↗</span></button></form></section>
    <section className="creation-grid" aria-label="Skill creation routes"><form className="route-card" onSubmit={(e) => queueJob(e, "/jobs/distill/open-world")}><p className="eyebrow">ROUTE B / OPEN WORLD</p><h2>Brief → Skill</h2><p>Discover a capability from an underspecified objective. Fixture mode is safe for first verification.</p><input name="skill_name" placeholder="Skill name" required /><input name="skill_slug" placeholder="skill-slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" required /><textarea name="brief" placeholder="What should this Skill reliably accomplish?" required /><textarea name="constraints" placeholder="Constraints, one per line (optional)" /><select name="engine" defaultValue="fixture"><option value="fixture">Fixture / no model calls</option><option value="skillalchemy">SkillAlchemy / agent CLI</option></select><button type="submit">Queue creation <span>↗</span></button></form><form className="route-card repo-card" onSubmit={(e) => queueJob(e, "/jobs/distill/repo")}><p className="eyebrow">ROUTE A / REPOSITORY</p><h2>Repo → Skill</h2><p>Distill operating knowledge with source provenance retained from the start.</p><input name="repo_url" type="url" placeholder="https://github.com/org/repo" required /><input name="ref" placeholder="Branch, tag, or commit (optional)" /><textarea name="objective" placeholder="What operating capability should be distilled?" /><select name="engine" defaultValue="fixture"><option value="fixture">Fixture / no model calls</option><option value="arex">AREX / DisCo</option></select><button type="submit">Queue distillation <span>↗</span></button></form></section>
    <section className="engine-strip" aria-label="Engine health"><p className="eyebrow">ENGINE HEALTH</p>{Object.entries(engines).map(([engine, health]) => <span key={engine} className={health.available ? "engine-up" : "engine-down"}>{engine}: {health.available ? "ready" : "unavailable"}</span>)}{job && <span className="job-pill">latest job · {job.status} · {job.id.slice(0, 8)}</span>}</section>
    <section className="registry" aria-labelledby="registry-title"><div className="registry-heading"><div><p className="eyebrow">REGISTRY</p><h2 id="registry-title">Skill library</h2></div><p className="registry-note">Select one to open its version workbench.</p></div><div className="skill-list">{skills.length === 0 ? <p className="empty">No registered artifacts yet. Start with an existing Skill package.</p> : skills.map((skill, index) => <button className={`skill-card ${selectedSkill?.id === skill.id ? "selected" : ""}`} onClick={() => void selectSkill(skill)} key={skill.id}><span className="index">{String(index + 1).padStart(2, "0")}</span><div><h3>{skill.name}</h3><p>{skill.description || skill.slug}</p></div><code>{skill.slug}</code></button>)}</div></section>
    {selectedSkill && <section className="workbench" aria-labelledby="workbench-title"><header><div><p className="eyebrow">VERSION WORKBENCH / {selectedSkill.slug}</p><h2 id="workbench-title">Gate before release.</h2></div><p>Production: <strong>{activeRelease ? versions.find((v) => v.id === activeRelease.skill_version_id)?.version ?? "resolved release" : "no active release"}</strong></p></header><div className="workbench-grid"><div className="version-rail"><p className="eyebrow">IMMUTABLE VERSIONS</p>{versions.map((version) => <button key={version.id} onClick={() => void selectVersion(version)} className={`version-row ${selectedVersion?.id === version.id ? "selected" : ""}`}><span>v{version.version}</span><i className={`state ${version.status}`} /> {version.status}</button>)}</div><div className="gate-card"><p className="eyebrow">CANDIDATE DECISION</p><h3>v{selectedVersion?.version ?? "—"}</h3><p className={`gate-state ${gate?.decision ?? "unknown"}`}>{gate?.decision ?? "not evaluated"}</p><p className="gate-detail">{gate?.summary.failures?.join(" · ") || gate?.summary.missing_holdout?.join(" · ") || "Run all holdout datasets to produce a release decision."}</p><div className="action-row"><button disabled={busy || !selectedVersion} onClick={() => void operate("evaluate")}>Run holdouts <span>↗</span></button><button disabled={busy || gate?.decision !== "passed"} className="release" onClick={() => void operate("promote")}>Promote <span>↗</span></button></div><small>Fixture grader only. Model graders can be added without weakening this gate.</small></div><div className="history"><p className="eyebrow">RELEASE HISTORY</p>{releases.length === 0 ? <p className="empty">No release recorded.</p> : releases.map((release) => <div className="release-row" key={release.id}><span>{versions.find((v) => v.id === release.skill_version_id)?.version ?? "version"}</span><em>{release.release_state}</em>{release.release_state !== "active" && <button disabled={busy} onClick={() => void operate("rollback", release.id)}>Revert here</button>}</div>)}</div></div><footer><span>{datasets.filter((d) => d.split === "holdout").length} holdout dataset(s)</span><span>{datasets.filter((d) => d.split === "dev").length} dev dataset(s)</span><span>Artifacts remain immutable</span></footer></section>}
  </main>;
}
