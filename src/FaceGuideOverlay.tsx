import { forwardRef } from "react";
import type { GuideMode } from "./faceGuide";

type GuideProps = {
  mode: GuideMode;
  ready: boolean;
  progress: number;
};

/**
 * Visual reference only. The fitting decision is computed separately from
 * MediaPipe's detected face oval; no camera pixels enter this SVG.
 */
export const FaceGuideOverlay = forwardRef<SVGSVGElement, GuideProps>(
  function FaceGuideOverlay({ mode, ready, progress }, ref) {
    return (
      <svg
        ref={ref}
        className={"face-guide-svg " + (ready ? "face-guide-svg--ready" : "face-guide-svg--waiting")}
        data-guide-mode={mode}
        data-ready={ready ? "true" : "false"}
        data-progress={progress.toFixed(2)}
        viewBox="0 0 300 420"
        role="img"
        aria-label={mode === "front" ? "Front-face positioning silhouette" : "Side-profile positioning silhouette"}
      >
        <defs>
          <filter id="face-guide-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5"/>
          </filter>
        </defs>
        {mode === "front" ? (
          <>
            {/* Realistic, tapered facial outline: crown, temples, cheeks, jaw and chin. */}
            <path
              className="face-guide-outline face-guide-glow"
              d="M150 46 C119 43 92 56 78 79 C64 102 61 130 66 171
                 C67 197 71 225 81 255 C90 283 108 317 131 348
                 Q150 370 169 348 C192 317 210 283 219 255
                 C229 225 233 197 234 171 C239 130 236 102 222 79
                 C208 56 181 43 150 46 Z"
            />
            <path
              className="face-guide-outline"
              d="M150 46 C119 43 92 56 78 79 C64 102 61 130 66 171
                 C67 197 71 225 81 255 C90 283 108 317 131 348
                 Q150 370 169 348 C192 317 210 283 219 255
                 C229 225 233 197 234 171 C239 130 236 102 222 79
                 C208 56 181 43 150 46 Z"
            />
            <path className="face-guide-helper" d="M85 181 Q150 176 215 181 M150 115 V293"/>
            <path className="face-guide-helper" d="M109 276 Q150 289 191 276"/>
          </>
        ) : (
          <>
            {/* Right-facing side profile with forehead, nose bridge, tip,
                philtrum, lips, chin and a softly curved rear skull. */}
            <path
              className="face-guide-outline face-guide-glow"
              d="M146 44 C111 41 81 58 66 91 C49 128 48 184 59 227
                 C69 267 85 310 104 344 Q132 368 167 354
                 C184 348 195 339 203 322 L209 303
                 Q211 295 222 293 L239 290 Q248 285 244 277
                 L238 269 Q250 261 245 251 L233 245
                 Q249 234 246 226 L230 217 Q220 210 223 196
                 L241 183 Q248 177 239 170 L217 164
                 Q206 158 205 143 L205 112
                 C205 79 180 47 146 44 Z"
            />
            <path
              className="face-guide-outline"
              d="M146 44 C111 41 81 58 66 91 C49 128 48 184 59 227
                 C69 267 85 310 104 344 Q132 368 167 354
                 C184 348 195 339 203 322 L209 303
                 Q211 295 222 293 L239 290 Q248 285 244 277
                 L238 269 Q250 261 245 251 L233 245
                 Q249 234 246 226 L230 217 Q220 210 223 196
                 L241 183 Q248 177 239 170 L217 164
                 Q206 158 205 143 L205 112
                 C205 79 180 47 146 44 Z"
            />
            <path className="face-guide-helper" d="M150 148 Q178 135 204 150"/>
          </>
        )}
        {/* Progress along the bottom: visual feedback only, never a shutter. */}
        {mode === "front" && progress > 0 && progress < 1 && (
          <path className="face-guide-progress" d="M75 396 H225" pathLength={100}
            strokeDasharray={100} strokeDashoffset={100 - Math.round(progress * 100)}/>
        )}
      </svg>
    );
  }
);
