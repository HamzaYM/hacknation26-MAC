"use client";

import { useEffect, useState } from "react";
import { getDemoCase } from "../../lib/api";
import type { JobSpec } from "../../lib/types";

// Read-only reference: onboarding info + every authorization/detail collected
// since, in one place. Real accumulation of "additional info provided during
// negotiation" (e.g. answers from Action Items) isn't persisted anywhere yet
// — this renders what's actually in job_spec today and is structured so new
// fields slot in as that grows, rather than being a one-off static page.
export default function Profile() {
  const [spec, setSpec] = useState<JobSpec | null>(null);

  useEffect(() => {
    getDemoCase().then(setSpec);
  }, []);

  if (!spec) return <p className="todo">Loading profile…</p>;

  const patient = spec.patient as { legal_name?: string; dob?: string };
  const insurance = spec.insurance as { payer_name?: string; member_id?: string; plan_type?: string };
  const financial = spec.financial_profile as {
    household_income?: number;
    household_size?: number;
    fpl_percent?: number;
    employment_status?: string;
    lump_sum_available?: number;
    max_monthly_payment?: number;
  };

  return (
    <div>
      <div className="user-strip">
        <span className="avatar">{(patient.legal_name ?? "?").charAt(0)}</span>
        <span><strong>{patient.legal_name}</strong></span>
      </div>

      <h1 style={{ fontSize: 28, margin: "16px 0 4px" }}>Profile</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24 }}>
        Everything you&apos;ve told us, in one place — for your reference, and so you never have to
        re-answer something you&apos;ve already given us.
      </p>

      <ProfileSection title="Identity">
        <Field label="Full name" value={patient.legal_name} />
        <Field label="Date of birth" value={patient.dob} mono />
      </ProfileSection>

      <ProfileSection title="Insurance">
        <Field label="Payer" value={insurance.payer_name} />
        <Field label="Member ID" value={insurance.member_id} mono />
        <Field label="Plan type" value={insurance.plan_type} />
      </ProfileSection>

      <ProfileSection title="Authorizations" subtitle="Given at signup — see /onboard for what each one unlocks">
        {Object.entries(spec.authorizations).map(([key, value]) => (
          <Field key={key} label={key.replace(/_/g, " ")} value={value} pill />
        ))}
      </ProfileSection>

      <ProfileSection title="Financial snapshot" subtitle="Powers charity-care and hardship-based levers across every bill">
        <Field
          label="Household income"
          value={financial.household_income != null ? `$${financial.household_income.toLocaleString()}` : undefined}
          mono
        />
        <Field label="Household size" value={financial.household_size} mono />
        <Field label="% of federal poverty line" value={financial.fpl_percent != null ? `${financial.fpl_percent}%` : undefined} mono />
        <Field label="Employment status" value={financial.employment_status?.replace(/_/g, " ")} />
        <Field
          label="Available today (lump sum)"
          value={financial.lump_sum_available != null ? `$${financial.lump_sum_available.toLocaleString()}` : undefined}
          mono
        />
        <Field
          label="Max monthly payment"
          value={financial.max_monthly_payment != null ? `$${financial.max_monthly_payment.toLocaleString()}` : undefined}
          mono
        />
      </ProfileSection>

      <p className="todo">
        This page only shows onboarding data today — answers you give through Action Items during a
        negotiation (e.g. confirming a date of service, authorizing a specific call) aren&apos;t written
        back to a persistent profile yet. TODO(Hamza): once those are persisted, surface them here
        too, grouped by which bill they came from.
      </p>
    </div>
  );
}

function ProfileSection({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h2 style={{ fontSize: 16, marginBottom: subtitle ? 2 : 12 }}>{title}</h2>
      {subtitle && <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>{subtitle}</div>}
      <div className="profile-fields">{children}</div>
    </div>
  );
}

function Field({ label, value, mono, pill }: { label: string; value?: string | number; mono?: boolean; pill?: boolean }) {
  if (value == null || value === "") return null;
  return (
    <div className="profile-field">
      <dt>{label}</dt>
      <dd className={mono ? "mono-figure" : ""}>
        {pill ? <span className="pill pill-accent">{value}</span> : value}
      </dd>
    </div>
  );
}
