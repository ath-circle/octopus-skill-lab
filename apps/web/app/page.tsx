"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type Skill = {
  id: string;
  slug: string;
  name: string;
  description: string;
  created_at: string;
};

type Job = { id: string; status: string; job_type: string; output?: { skill_id?: string } | null; error?: string | null };
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

  useEffect(() => {
    void fetch(`${apiUrl}/skills`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Registry unavailable");
        return response.json() as Promise<Skill[]>;
      })
      .then((data) => {
        setSkills(data);
        setStatus(data.length ? `${data.length} registered` : "No Skills registered");
      })
      .catch(() => setStatus("API offline — start FastAPI to load the registry"));
    void fetch(`${apiUrl}/settings/engines`).then((response) => response.json() as Promise<EngineHealth>).then(setEngines).catch(() => undefined);
  }, []);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    if (selected && !slug) setSlug(selected.name.replace(/\.zip$/i, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
    if (selected && !name) setName(selected.name.replace(/\.zip$/i, ""));
  }

  async function importSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return setStatus("Choose a .zip Skill package first.");
    const form = new FormData();
    form.set("archive", file);
    form.set("slug", slug);
    form.set("name", name);
    form.set("description", "Imported through the V1.0 registry.");
    setStatus("Validating and registering immutable artifact…");
    const response = await fetch(`${apiUrl}/skills/import`, { method: "POST", body: form });
    const body = await response.json().catch(() => null) as { detail?: string; skill?: Skill } | null;
    if (!response.ok || !body?.skill) return setStatus(body?.detail ?? "Import failed.");
    setSkills((current) => [body.skill!, ...current]);
    setStatus(`Registered ${body.skill.name} as version 0.1.0.`);
    setFile(null);
  }

  async function queueJob(event: FormEvent<HTMLFormElement>, route: string) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = Object.fromEntries(form.entries());
    if (typeof payload.constraints === "string") payload.constraints = payload.constraints.split("\n").filter(Boolean);
    setStatus("Queueing isolated engine job…");
    const response = await fetch(`${apiUrl}${route}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const body = await response.json().catch(() => null) as Job & { detail?: string } | null;
    if (!response.ok || !body?.id) return setStatus(body?.detail ?? "Could not queue job.");
    setJob(body);
    setStatus(`Job ${body.id.slice(0, 8)} queued. Start the worker to process it.`);
  }

  return (
    <main className="shell">
      <section className="masthead">
        <p className="eyebrow">OPC / SKILL OPS</p>
        <h1>Make skill changes<br /><em>earn</em> production.</h1>
        <p className="lede">A registry where every artifact has a hash, a history, and a way home.</p>
        <div className="signal"><span className="signal-dot" /> {status}</div>
      </section>

      <section className="control-panel" aria-labelledby="import-title">
        <div>
          <p className="eyebrow">V1.0 / FOUNDATION</p>
          <h2 id="import-title">Register a portable Skill</h2>
          <p>Import is inert: scripts are retained but never executed. The package is normalized, hashed, and stored as an immutable version.</p>
        </div>
        <form onSubmit={importSkill} className="import-form">
          <label className="file-drop">
            <input type="file" accept=".zip,application/zip" onChange={chooseFile} />
            <span>{file?.name ?? "Choose .zip package"}</span>
          </label>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Skill name" required />
          <input value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="skill-slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" required />
          <button type="submit">Normalize & register <span>↗</span></button>
        </form>
      </section>

      <section className="creation-grid" aria-label="Skill creation routes">
        <form className="route-card" onSubmit={(event) => queueJob(event, "/jobs/distill/open-world")}>
          <p className="eyebrow">ROUTE B / OPEN WORLD</p>
          <h2>Brief → Skill</h2>
          <p>Discover a capability from an underspecified objective. Fixture mode is safe for first verification.</p>
          <input name="skill_name" placeholder="Skill name" required />
          <input name="skill_slug" placeholder="skill-slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" required />
          <textarea name="brief" placeholder="What should this Skill reliably accomplish?" required />
          <textarea name="constraints" placeholder="Constraints, one per line (optional)" />
          <select name="engine" defaultValue="fixture"><option value="fixture">Fixture / no model calls</option><option value="skillalchemy">SkillAlchemy / agent CLI</option></select>
          <button type="submit">Queue creation <span>↗</span></button>
        </form>

        <form className="route-card repo-card" onSubmit={(event) => queueJob(event, "/jobs/distill/repo")}>
          <p className="eyebrow">ROUTE A / REPOSITORY</p>
          <h2>Repo → Skill</h2>
          <p>Distill operating knowledge with source provenance retained from the start.</p>
          <input name="repo_url" type="url" placeholder="https://github.com/org/repo" required />
          <input name="ref" placeholder="Branch, tag, or commit (optional)" />
          <textarea name="objective" placeholder="What operating capability should be distilled?" />
          <select name="engine" defaultValue="fixture"><option value="fixture">Fixture / no model calls</option><option value="arex">AREX / DisCo</option></select>
          <button type="submit">Queue distillation <span>↗</span></button>
        </form>
      </section>

      <section className="engine-strip" aria-label="Engine health">
        <p className="eyebrow">ENGINE HEALTH</p>
        {Object.entries(engines).map(([engine, health]) => <span key={engine} className={health.available ? "engine-up" : "engine-down"}>{engine}: {health.available ? "ready" : "unavailable"}</span>)}
        {job && <span className="job-pill">latest job · {job.status} · {job.id.slice(0, 8)}</span>}
      </section>

      <section className="registry" aria-labelledby="registry-title">
        <div className="registry-heading">
          <p className="eyebrow">REGISTRY</p>
          <h2 id="registry-title">Skill library</h2>
        </div>
        <div className="skill-list">
          {skills.length === 0 ? <p className="empty">No registered artifacts yet. Start with an existing Skill package.</p> : skills.map((skill, index) => (
            <article className="skill-card" key={skill.id}>
              <span className="index">{String(index + 1).padStart(2, "0")}</span>
              <div><h3>{skill.name}</h3><p>{skill.description || skill.slug}</p></div>
              <code>{skill.slug}</code>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
