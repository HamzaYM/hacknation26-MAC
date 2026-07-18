export default function Home() {
  return (
    <>
      <div className="card">
        <h1>The Negotiator — scaffold</h1>
        <p>
          An AI advocate that reads your hospital bill, finds the errors and the law on your
          side, calls the billing office, and talks the price down on a live call.
        </p>
        <p>
          Start with <code>PRD.md</code> at the repo root, then your own file in{" "}
          <code>docs/workplans/</code>.
        </p>
      </div>
      <div className="card">
        <h2>The six screens (PRD §11)</h2>
        <ol>
          <li><a href="/onboard">Onboard / Authorize</a></li>
          <li><a href="/intake">Intake — upload + voice interview</a></li>
          <li><a href="/confirm">Action Plan / Spec Confirm</a></li>
          <li><a href="/warroom">War Room — live calls</a></li>
          <li><a href="/report">Report (+ Case Timeline tab)</a></li>
        </ol>
        <p className="todo">Fixture case: <code>GET /api/cases/demo</code> (FastAPI must be running on :8000).</p>
      </div>
    </>
  );
}
