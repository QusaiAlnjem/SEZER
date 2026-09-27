"use client";
import { useEffect, useState } from "react";

const WORD = "SEZER";

/** Timings, in ms — kept together so the sequence is readable at a glance. */
const LETTER_START = 420;   // begins while the ink is still spreading
const LETTER_STEP = 85;     // overlap between letters, so it reads as one motion
const RULE_AT = 1180;       // the line under the word
const FADE_AT = 1750;
const END_AT = 2200;

/** Green floods out from the centre, then SEZER springs up letter by letter.
 *
 *  Lives on the sign-in screen, so it plays whenever someone is not signed in
 *  — including a cold start while the app is still waking up — and never once
 *  they are inside, where a refresh would otherwise replay it every time.
 */
export function Splash() {
  const [done, setDone] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const fade = setTimeout(() => setLeaving(true), FADE_AT);
    const finish = setTimeout(() => setDone(true), END_AT);
    return () => { clearTimeout(fade); clearTimeout(finish); };
  }, []);

  if (done) return null;

  return (
    <div
      className={`splash ${leaving ? "splash-out" : ""}`}
      role="presentation"
      aria-hidden="true"
      /* Inline, so the overlay covers on the very first paint. The stylesheet
         lands a frame later, which was long enough to show the form beneath. */
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "#ffffff",
        display: "grid",
        placeItems: "center",
        overflow: "hidden",
      }}
    >
      {/* scaled from nothing inline too, so it can't appear as a bare box */}
      <div className="splash-ink" style={{ transform: "scale(0)" }} />

      <div className="splash-stage">
        <div className="splash-word" dir="ltr">
          {WORD.split("").map((letter, i) => (
            <span
              key={i}
              className="splash-letter"
              /* `opacity: 0` is inline so raw text can't flash before the
                 stylesheet lands — the keyframes outrank it once they run. */
              style={{ opacity: 0, animationDelay: `${LETTER_START + i * LETTER_STEP}ms` }}
            >
              {letter}
            </span>
          ))}
        </div>
        <div className="splash-rule" style={{ animationDelay: `${RULE_AT}ms` }} />
      </div>

      <style jsx>{`
        /* layout lives inline above; this only adds the exit */
        .splash {
          transition: opacity 430ms ease, transform 430ms cubic-bezier(0.4, 0, 1, 1);
        }
        .splash-out {
          opacity: 0;
          transform: scale(1.08);   /* pulls the viewer through into the app */
          pointer-events: none;
        }

        /* a circle bigger than any viewport, scaled up from nothing */
        .splash-ink {
          position: absolute;
          top: 50%;
          left: 50%;
          width: 220vmax;
          height: 220vmax;
          margin: -110vmax 0 0 -110vmax;
          border-radius: 50%;
          background: #0f766e;
          transform: scale(0);
          /* fast out of the gate, long gentle tail — reads as a flood, not a wipe */
          animation: ink 900ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes ink {
          from { transform: scale(0); }
          to   { transform: scale(1); }
        }

        .splash-stage {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.22em;
          font-size: clamp(2.4rem, 13vw, 5.5rem);
        }

        .splash-word {
          display: flex;
          /* the app runs RTL, which would lay these flex items out right to
             left and spell the brand backwards */
          direction: ltr;
          font-weight: 900;
          letter-spacing: 0.01em;
          color: #ffffff;
          line-height: 1;
        }
        .splash-letter {
          display: inline-block;
          transform-origin: bottom center;
          /* squashed flat against the baseline before it springs */
          transform: scaleY(0.08) translateY(0.1em);
          opacity: 0;
          animation: rise 620ms cubic-bezier(0.18, 1.5, 0.35, 1) forwards;
        }
        @keyframes rise {
          0%   { transform: scaleY(0.08) scaleX(1.06) translateY(0.1em); opacity: 0; }
          40%  { opacity: 1; }
          60%  { transform: scaleY(1.1) scaleX(0.97) translateY(0);      opacity: 1; }
          80%  { transform: scaleY(0.97) scaleX(1.01) translateY(0);     opacity: 1; }
          100% { transform: scaleY(1) scaleX(1) translateY(0);           opacity: 1; }
        }

        /* a hairline that draws out from the centre once the word has landed */
        .splash-rule {
          width: 100%;
          height: 2px;
          background: rgba(255, 255, 255, 0.55);
          transform: scaleX(0);
          animation: rule 520ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes rule {
          from { transform: scaleX(0); opacity: 0; }
          to   { transform: scaleX(1); opacity: 1; }
        }

        @media (prefers-reduced-motion: reduce) {
          .splash-ink { animation-duration: 1ms; }
          .splash-letter,
          .splash-rule {
            animation: none;
            opacity: 1;
            transform: none;
          }
          .splash-out { transform: none; }
        }
      `}</style>
    </div>
  );
}
