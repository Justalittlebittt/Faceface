type Props = {
  path: string;
  frameWidth: number;
  frameHeight: number;
  progress: number;
  ready: boolean;
};

/**
 * The entire camera stage is the SVG coordinate system. Unlike a small
 * fixed oval, this path is derived from the participant's actual on-device
 * face mesh. Drawing starts at forehead top and proceeds clockwise.
 *
 * The path exists only during live preview and is never stored or sent.
 */
export function LiveFaceOverlay({ path, frameWidth, frameHeight, progress, ready }: Props) {
  return (
    <svg className={"live-face-svg" + (ready ? " live-face-svg--ready" : "")}
      data-guide-mode="front" data-ready={ready ? "true" : "false"}
      data-progress={progress.toFixed(2)}
      viewBox={`0 0 ${Math.max(1, frameWidth)} ${Math.max(1, frameHeight)}`}
      preserveAspectRatio="none" aria-hidden="true"
    >
      {path && (
        <>
          <path d={path} className="live-face-outline" />
          {progress > 0 && (
            <>
              <path d={path} className="live-face-progress-glow"
                pathLength={100} strokeDasharray="100 100"
                strokeDashoffset={100 - progress * 100}/>
              <path d={path} className="live-face-progress"
                pathLength={100} strokeDasharray="100 100"
                strokeDashoffset={100 - progress * 100}/>
            </>
          )}
        </>
      )}
    </svg>
  );
}
