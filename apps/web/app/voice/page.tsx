"use client";

import { useEffect, useRef, useState } from "react";
import { getDemoCase } from "../../lib/api";
import { VOICES, getVoicePref, setVoicePref, voiceById } from "../../lib/voice";
import type { Voice } from "../../lib/voice";

// The voice the negotiator uses on calls, chosen per case. Grounded in our own
// voice research (see the "why" card below). Selection persists to Supabase when
// the column exists and to localStorage always, so it survives a reload either way.
export default function VoicePicker() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});

  useEffect(() => {
    getDemoCase()
      .then((spec) => {
        setCaseId(spec.case_id);
        return getVoicePref(spec.case_id);
      })
      .then((voiceId) => setSelected(voiceId))
      .catch(() => setSelected(VOICES[0].voiceId));
  }, []);

  function togglePlay(voice: Voice) {
    const el = audioRefs.current[voice.key];
    if (!el) return;
    if (playing === voice.key) {
      el.pause();
      setPlaying(null);
      return;
    }
    Object.values(audioRefs.current).forEach((a) => a && a.pause());
    el.currentTime = 0;
    void el.play();
    setPlaying(voice.key);
  }

  function choose(voice: Voice) {
    if (!caseId) return;
    setSelected(voice.voiceId);
    void setVoicePref(caseId, voice.voiceId);
  }

  if (selected === null) return <p className="todo">Loading voices…</p>;

  const current = voiceById(selected);

  return (
    <div>
      <h1 style={{ fontSize: 28, margin: "16px 0 4px" }}>Pick your negotiator&apos;s voice</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, maxWidth: 640 }}>
        This is the voice a billing rep hears when we call for you. Three of them, each tuned
        for a different kind of call. Have a listen, then pick the one that fits. You can change
        it any time before we dial.
      </p>

      <div className="voice-current">
        <span className="voice-current-label">On calls we&apos;ll use</span>
        <span className="voice-current-name">
          {current?.name}
          <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}> · {current?.tagline}</span>
        </span>
      </div>

      <div className="card voice-why">
        <h3 style={{ marginBottom: 8 }}>Why these three</h3>
        <p style={{ fontSize: 14, color: "var(--text-secondary)", margin: "0 0 12px", lineHeight: 1.6 }}>
          We built one negotiator, then spent our voice research making it not sound like a bot.
          Three things we learned from our own test calls shaped these voices.
        </p>
        <ul className="voice-why-points">
          <li>
            Casual and warm reads as human; polished and formal reads as a bot reading a card. The
            humanization techniques we wrote (fillers, self-corrections, a breath before a big
            number) came out of calls where flawless delivery got flagged as AI.
          </li>
          <li>
            Numbers get said slowly and clean, with the pitch falling at the end, so a dollar
            figure or a CPT code lands as authority instead of getting garbled.
          </li>
          <li>
            Warmth gets more out of a front-line rep; a firmer, evidence-first register does better
            with a supervisor or a collector. So the voice should match who you expect to argue with.
          </li>
        </ul>
        <p style={{ fontSize: 13, color: "var(--text-tertiary)", margin: "12px 0 0" }}>
          Each voice below is matched to what worked in those test calls, with the honest tradeoff
          for when it is the wrong pick.
        </p>
      </div>

      <div className="voice-grid">
        {VOICES.map((voice) => {
          const isSelected = voice.voiceId === selected;
          const isPlaying = playing === voice.key;
          return (
            <div key={voice.key} className={`card voice-card${isSelected ? " selected" : ""}`}>
              <div className="voice-card-head">
                <div>
                  <div className="voice-name">
                    {voice.name}
                    {voice.isDefault && <span className="pill pill-muted voice-tag">Default</span>}
                  </div>
                  <div className="voice-tagline">{voice.tagline}</div>
                </div>
                {isSelected && <span className="pill pill-accent voice-tag">In use ✓</span>}
              </div>

              <p className="voice-angle">{voice.angle}</p>

              <button
                type="button"
                className="btn btn-secondary voice-play"
                onClick={() => togglePlay(voice)}
                aria-label={isPlaying ? `Pause ${voice.name} sample` : `Play ${voice.name} sample`}
              >
                <span aria-hidden>{isPlaying ? "❚❚" : "▶"}</span>
                {isPlaying ? "Playing…" : "Hear a call opener"}
              </button>
              <audio
                ref={(el) => {
                  audioRefs.current[voice.key] = el;
                }}
                src={voice.preview}
                preload="none"
                onEnded={() => setPlaying((p) => (p === voice.key ? null : p))}
              />

              <div className="voice-proscons">
                <div className="voice-list">
                  <span className="voice-list-head">Where it wins</span>
                  {voice.pros.map((pro, i) => (
                    <div className="voice-list-item pro" key={i}>
                      <span className="voice-marker" aria-hidden>✓</span>
                      <span>{pro}</span>
                    </div>
                  ))}
                </div>
                <div className="voice-list">
                  <span className="voice-list-head">Where it costs you</span>
                  {voice.cons.map((con, i) => (
                    <div className="voice-list-item con" key={i}>
                      <span className="voice-marker" aria-hidden>–</span>
                      <span>{con}</span>
                    </div>
                  ))}
                </div>
              </div>

              {isSelected ? (
                <div className="voice-chosen">This is your negotiator&apos;s voice</div>
              ) : (
                <button type="button" className="btn btn-primary voice-choose" onClick={() => choose(voice)}>
                  Use {voice.name}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
