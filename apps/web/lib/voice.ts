import { API_BASE } from "./api";

// The three negotiator voices in our ElevenLabs workspace: Alex and Riley are
// cloned from Susy's voice designs; Adam is a stock workspace voice (swapped in
// for Morgan, Hamza 2026-07-18: wanted a more assertive male option). voice_id is the same
// string the backend allowlists (app/services/voice_prefs.py) — keep in sync.
export interface Voice {
  key: string;
  voiceId: string;
  name: string;
  tagline: string; // one-line register, matches the design-system card-title job
  angle: string; // when to reach for it
  pros: string[];
  cons: string[];
  preview: string; // mp3 under /public/voices
  isDefault?: boolean;
}

export const VOICES: Voice[] = [
  {
    key: "alex",
    voiceId: "jTWqplUkOPQwOegNjhal",
    name: "Alex",
    tagline: "Warm and polite",
    angle: "Opening calls and front-line reps, where being liked gets you further.",
    pros: [
      "Positive politeness and a little hardship framing get more out of a front-line rep, which is where most calls start.",
      "Warmth is what gets a rep to put you through to a supervisor, so it opens the door to escalation.",
      "Closest match to the fillers and pacing our humanization work already runs, so it reads as a real person, not a script.",
    ],
    cons: [
      "Warmth can read as soft in a hardball escalation, where a supervisor only moves on the numbers.",
      "Against a collector working a quota, friendly can be taken as an opening to brush you off.",
    ],
    preview: "/voices/alex.mp3",
  },
  {
    key: "adam",
    voiceId: "pNInz6obpgDQGcFmaJgB",
    name: "Adam",
    tagline: "Assertive and unbudging",
    angle: "Supervisors and benchmark moments, where a number has to land with authority.",
    pros: [
      "Carries a dollar figure with weight, so an anchor or a benchmark cite lands as a position, not a suggestion.",
      "Assertive without heat, which is the escalation register our research backs: pressure reads fine, anger backfires.",
      "A deeper voice reads as seniority to many reps, which helps when asking for someone with authority to resolve it.",
    ],
    cons: [
      "Dominance up front can put a friendly rep on the defensive and slow the early rapport plays.",
      "Less natural room for the fillers and softeners our humanization layer leans on, so small talk can read scripted.",
    ],
    preview: "/voices/adam.mp3",
    isDefault: true,
  },
  {
    key: "riley",
    voiceId: "saQ3GQHMonWJoYcm6AJJ",
    name: "Riley",
    tagline: "Firm and direct",
    angle: "Collections and reps who have already stonewalled, where warmth reads as weakness.",
    pros: [
      "Brisk and confident, which holds up against a collector working month-end quotas.",
      "Does not linger, so a rep who stonewalled once gets a straight ask instead of another opening to deflect.",
      "Firm without anger, which our research is clear about: anger backfires for a disclosed AI.",
    ],
    cons: [
      "Direct can come off cold on a first, friendly call and cost you a front-line rep's goodwill.",
      "Fewer rapport cues in the voice, so it is the wrong pick for building toward an escalation ask.",
    ],
    preview: "/voices/riley.mp3",
  },
];

export const DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"; // Adam (Hamza's pick, 07-18 late)

export function voiceById(voiceId: string | null | undefined): Voice | undefined {
  return VOICES.find((v) => v.voiceId === voiceId);
}

const lsKey = (caseId: string) => `haggl.voice.${caseId}`;

// Read the chosen voice. The server wins when it actually persisted; otherwise
// we fall back to the localStorage mirror (covers the DB-before-migration case),
// then to the default. So the picker is correct with or without migration 0002.
export async function getVoicePref(caseId: string): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/voice`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      if (data.persisted && data.voice_id) return data.voice_id as string;
    }
  } catch {
    // API unreachable — fall through to the mirror.
  }
  if (typeof window !== "undefined") {
    const mirrored = window.localStorage.getItem(lsKey(caseId));
    if (mirrored && voiceById(mirrored)) return mirrored;
  }
  return DEFAULT_VOICE_ID;
}

// Write the choice to localStorage first (instant, always works), then best-effort
// to the API. A failed/absent DB never breaks the UI.
export async function setVoicePref(caseId: string, voiceId: string): Promise<void> {
  if (typeof window !== "undefined") window.localStorage.setItem(lsKey(caseId), voiceId);
  try {
    await fetch(`${API_BASE}/cases/${caseId}/voice`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice_id: voiceId }),
    });
  } catch {
    // best-effort; localStorage already holds the choice
  }
}

// Overrides block for a browser-session call via the ElevenLabs web SDK:
//   conversation.startSession({ agentId, ...browserSessionOverrides(voiceId) })
// The agent must allow the tts.voice_id override (see scripts/provision_elevenlabs.py).
export function browserSessionOverrides(voiceId: string): { overrides: { tts: { voiceId: string } } } {
  return { overrides: { tts: { voiceId } } };
}
