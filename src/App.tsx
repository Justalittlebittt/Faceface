import { useCallback, useEffect, useRef, useState } from "react";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { describeLandmarks, type Analysis } from "./descriptors";
import { comparePhotoAnalyses } from "./consistency";
import { FaceGuideOverlay } from "./FaceGuideOverlay";
import { LiveFaceOverlay } from "./LiveFaceOverlay";
import { advanceStationaryHold, clockwiseFacePath, projectFaceGuide,
  smoothFacePoints, EMPTY_HOLD, READY_HOLD_MS,
  type GuideMode, type GuideState, type FaceAnchor, type XY } from "./faceGuide";
import { makeReading, readingAsText, shortLifeReadingAsText } from "./reading";
import { localizeAnalysisMessage, localizeDescriptor, t, type Language } from "./i18n";

type Phase = "idle" | "camera" | "analyzing" | "result";

function evidenceLabel(value: "clear" | "borderline" | "unavailable" | undefined, language: Language) {
  return t(language, value === "clear" ? "compareEvidenceClear" :
    value === "borderline" ? "compareEvidenceBorderline" :
    value === "unavailable" ? "compareEvidenceUnavailable" : "compareEvidenceUnknown");
}

function cameraFailure(cause: unknown, language: Language): string {
  if (cause instanceof DOMException) {
    if (cause.name === "NotAllowedError" || cause.name === "PermissionDeniedError") {
      return t(language, "cameraDenied");
    }
    if (cause.name === "NotFoundError" || cause.name === "DevicesNotFoundError") {
      return t(language, "cameraMissing");
    }
    if (cause.name === "NotReadableError" || cause.name === "TrackStartError") {
      return t(language, "cameraBusy");
    }
  }
  return cause instanceof Error ? t(language, "cameraUnknown") + ": " + cause.message : t(language, "cameraUnknown");
}
const WASM_ROOT = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm";
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

export default function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const previousFacePointsRef = useRef<XY[] | null>(null);
  const faceAnchorRef = useRef<FaceAnchor | null>(null);
  const guideFrameRef = useRef<number | null>(null);
  const guideHoldRef = useRef(EMPTY_HOLD);
  const guideReadyRef = useRef(false);
  const guideModeRef = useRef<GuideMode>("front");
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<FaceLandmarker | null>(null);
  const loadingRef = useRef<Promise<FaceLandmarker> | null>(null);
  const mountedRef = useRef(false);
  const requestRef = useRef(0);
  const [language, setLanguage] = useState<Language>("en");
  const [phase, setPhase] = useState<Phase>("idle");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  // Retain only the previous summary of user-chosen local analysis, never an
  // earlier photo or landmark array. Reset/pagehide discards this comparison.
  const [comparisonBaseline, setComparisonBaseline] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [reportMode, setReportMode] = useState<"brief" | "detailed">("brief");
  const [cameraAspect, setCameraAspect] = useState<number | null>(null);
  const [guideMode, setGuideMode] = useState<GuideMode>("front");
  const [guideStatus, setGuideStatus] = useState<GuideState>("loading");
  const [guideProgress, setGuideProgress] = useState(0);
  const [guideReady, setGuideReady] = useState(false);
  const [liveFace, setLiveFace] = useState({ path: "", width: 1, height: 1 });
  const [photoSource, setPhotoSource] = useState<"camera" | "file" | null>(null);
  const [timing, setTiming] = useState<{ modelMs: number; inferenceMs: number } | null>(null);
  const reading = analysis ? makeReading(analysis, language) : null;
  const observations = analysis?.descriptors.map(d => localizeDescriptor(d, language)) ?? [];
  const comparison = comparisonBaseline && analysis
    ? comparePhotoAnalyses(comparisonBaseline, analysis) : null;

  useEffect(() => {
    document.documentElement.lang = language === "en" ? "en" : "zh-CN";
    document.title = language === "en" ? "Faceface · Face patterns and cultural history" : "Faceface · 面部形态观察";
  }, [language]);

  const stopCamera = useCallback(() => {
    if (guideFrameRef.current !== null) cancelAnimationFrame(guideFrameRef.current);
    guideFrameRef.current = null;
    guideHoldRef.current = EMPTY_HOLD;
    guideReadyRef.current = false;
    previousFacePointsRef.current = null;
    faceAnchorRef.current = null;
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const reset = () => {
    requestRef.current += 1;
    stopCamera();
    setPhase("idle");
    setAnalysis(null);
    setComparisonBaseline(null);
    setError("");
    setShowMeasurements(false);
    setReportMode("brief");
    setTiming(null);
    setCameraAspect(null);
    setPhotoSource(null);
    setGuideStatus("loading");
    setGuideProgress(0);
    setGuideReady(false);
    setLiveFace({ path: "", width: 1, height: 1 });
    guideModeRef.current = "front";
    setGuideMode("front");
    const canvas = canvasRef.current;
    if (canvas) {
      // Resetting the backing size releases pixel data, not just the visible drawing.
      canvas.width = 0;
      canvas.height = 0;
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestRef.current += 1;
      stopCamera();
      landmarkerRef.current?.close();
      landmarkerRef.current = null;
    };
  }, [stopCamera]);

  // Suspend camera access and discard temporary captures whenever the page is hidden.
  // Mobile browsers can otherwise leave the camera active while switching apps.
  useEffect(() => {
    const discardOnLeave = () => {
      requestRef.current += 1;
      stopCamera();
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
      setPhase("idle");
      setAnalysis(null);
      setComparisonBaseline(null);
      setTiming(null);
      setCameraAspect(null);
      setPhotoSource(null);
      setGuideStatus("loading");
      setGuideProgress(0);
      setGuideReady(false);
      setLiveFace({ path: "", width: 1, height: 1 });
      guideModeRef.current = "front";
      setGuideMode("front");
      setError("");
    };
    const onVisibility = () => {
      // A native share sheet may background the browser; keep an already
      // generated report readable when the user returns.
      if (document.hidden && phase !== "result") discardOnLeave();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", discardOnLeave);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", discardOnLeave);
    };
  }, [stopCamera, phase]);

  const begin = async () => {
    const request = ++requestRef.current;
    setError("");
    setAnalysis(null);
    setTiming(null);
    setCameraAspect(null);
    setPhotoSource(null);
    setGuideStatus("loading");
    setGuideProgress(0);
    setGuideReady(false);
    guideHoldRef.current = EMPTY_HOLD;
    faceAnchorRef.current = null;
    previousFacePointsRef.current = null;
    setLiveFace({ path: "", width: 1, height: 1 });
    guideModeRef.current = "front";
    setGuideMode("front");
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError(t(language, "unsupported"));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: "user", width: { ideal: 720 }, height: { ideal: 960 } }
      });
      if (request !== requestRef.current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error(t(language, "cameraUnavailable"));
      video.srcObject = stream;
      setPhase("camera");
      // On mobile Safari, let React reveal the video before starting playback.
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
      if (request !== requestRef.current) return;
      await video.play();
      if (request !== requestRef.current) return;
      await startTracking(request);
    } catch (cause) {
      if (request !== requestRef.current) return;
      stopCamera();
      setPhase("idle");
      setError(cameraFailure(cause, language));
    }
  };

  const loadLandmarker = (): Promise<FaceLandmarker> => {
    if (landmarkerRef.current) return Promise.resolve(landmarkerRef.current);
    if (!loadingRef.current) {
      loadingRef.current = (async () => {
        const vision = await FilesetResolver.forVisionTasks(WASM_ROOT);
        const model = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
          runningMode: "IMAGE",
          numFaces: 2,
          outputFaceBlendshapes: false
        });
        // An in-flight model download can resolve after the browser route unmounts.
        // Close the completed instance instead of retaining a WASM runtime forever.
        if (!mountedRef.current) {
          model.close();
          throw new Error("本页面已关闭，模型加载已取消。");
        }
        landmarkerRef.current = model;
        return model;
      })().catch(cause => {
        loadingRef.current = null;
        throw cause;
      });
    }
    return loadingRef.current;
  };

  // Low-frequency, on-device VIDEO tracking informs manual capture readiness.
  // It never calls capture(), downloads images or sends facial geometry anywhere.
  const changeGuideMode = (mode: GuideMode) => {
    guideModeRef.current = mode;
    setGuideMode(mode);
    guideHoldRef.current = EMPTY_HOLD;
    guideReadyRef.current = false;
    faceAnchorRef.current = null;
    previousFacePointsRef.current = null;
    setLiveFace({ path: "", width: 1, height: 1 });
    setGuideReady(false);
    setGuideProgress(0);
    setGuideStatus(mode === "side" ? "side-preview" : "loading");
    setError("");
  };

  const startTracking = async (request: number): Promise<void> => {
    const model = await loadLandmarker();
    if (request !== requestRef.current) return;
    await model.setOptions({ runningMode: "VIDEO" });
    if (request !== requestRef.current) return;
    let lastRun = 0;
    const sample = (now: number) => {
      if (request !== requestRef.current || !streamRef.current) return;
      const video = videoRef.current;
      const stage = stageRef.current;

      if (guideModeRef.current === "side") {
        if (guideReadyRef.current) {
          guideReadyRef.current = false;
          setGuideReady(false);
        }
        guideHoldRef.current = EMPTY_HOLD;
        faceAnchorRef.current = null;
        previousFacePointsRef.current = null;
      } else if (video && stage && video.readyState >= 2 &&
                 video.videoWidth && video.videoHeight && now - lastRun >= 250) {
        lastRun = now;
        try {
          const detected = model.detectForVideo(video, now);
          const box = (element: Element) => {
            const r = element.getBoundingClientRect();
            return { x: r.x, y: r.y, width: r.width, height: r.height };
          };
          const stageBox = box(stage);
          const result = projectFaceGuide(
            detected.faceLandmarks, { width: video.videoWidth, height: video.videoHeight },
            stageBox, true
          );
          const tracking = advanceStationaryHold(
            guideHoldRef.current, faceAnchorRef.current,
            result.anchor, now, result.state === "aligned"
          );
          const smoothed = result.points.length
            ? smoothFacePoints(tracking.moved ? null : previousFacePointsRef.current,
                result.points)
            : [];
          previousFacePointsRef.current = smoothed.length ? smoothed : null;
          faceAnchorRef.current = tracking.anchor;
          guideHoldRef.current = tracking.hold;
          guideReadyRef.current = tracking.hold.complete;
          setLiveFace({
            path: clockwiseFacePath(smoothed),
            width: stageBox.width,
            height: stageBox.height
          });
          setGuideStatus(tracking.moved ? "moving" : result.state);
          setGuideProgress(tracking.hold.progress);
          setGuideReady(tracking.hold.complete);
        } catch (cause) {
          // A model failure cannot silently make the frame appear ready.
          guideHoldRef.current = EMPTY_HOLD;
          faceAnchorRef.current = null;
          previousFacePointsRef.current = null;
          setLiveFace({ path: "", width: 1, height: 1 });
          guideReadyRef.current = false;
          setGuideProgress(0);
          setGuideReady(false);
          setGuideStatus("loading");
          setError(cause instanceof Error
            ? t(language, "modelFailure") + ": " + cause.message
            : t(language, "modelUnknown"));
          return;
        }
      }
      guideFrameRef.current = requestAnimationFrame(sample);
    };
    guideFrameRef.current = requestAnimationFrame(sample);
  };

  // Both the camera frame and the optional local-file fallback use exactly the
  // same browser-only landmark inference and descriptive report path.
  const analyzeCanvas = async (canvas: HTMLCanvasElement) => {
    stopCamera();
    setPhase("analyzing");
    setError("");
    const request = ++requestRef.current;
    const modelStart = performance.now();
    try {
      const model = await loadLandmarker();
      const modelMs = performance.now() - modelStart;
      if (request !== requestRef.current) return;
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
      if (request !== requestRef.current) return;
      // Preview inference runs in VIDEO mode; still-image analysis must
      // explicitly return the shared model to IMAGE mode after capture.
      await model.setOptions({ runningMode: "IMAGE" });
      if (request !== requestRef.current) return;
      const inferenceStart = performance.now();
      const result = model.detect(canvas);
      const inferenceMs = performance.now() - inferenceStart;
      if (request !== requestRef.current) return;
      setTiming({ modelMs: Math.round(modelMs), inferenceMs: Math.round(inferenceMs) });
      setReportMode("brief");
      setAnalysis(describeLandmarks(result.faceLandmarks, { width: canvas.width, height: canvas.height }));
      setPhase("result");
    } catch (cause) {
      if (request !== requestRef.current) return;
      setError(cause instanceof Error ? t(language, "modelFailure") + ": " + cause.message : t(language, "modelUnknown"));
      setPhase("result");
    }
  };

  const capture = async () => {
    if (phase !== "camera" || guideModeRef.current !== "front" ||
        !guideReadyRef.current ||
        guideHoldRef.current.lastSeenAt === null ||
        performance.now() - guideHoldRef.current.lastSeenAt > 700) {
      setError(t(language, "guideOutside"));
      return;
    }
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2 || video.videoWidth === 0) {
      setError(t(language, "cameraNotReady"));
      return;
    }
    const scale = Math.min(1, 960 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) {
      setError(t(language, "canvasFailure"));
      return;
    }
    // Manual shutter only: the countdown unlocks this action, it never fires it.
    if (guideFrameRef.current !== null) cancelAnimationFrame(guideFrameRef.current);
    guideFrameRef.current = null;
    guideReadyRef.current = false;
    setGuideReady(false);
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    setPhotoSource("camera");
    await analyzeCanvas(canvas);
  };

  const selectLocalPhoto = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 12 * 1024 * 1024) {
      setError(t(language, "badPhoto"));
      return;
    }
    setAnalysis(null);
    setTiming(null);
    setError("");
    setPhase("analyzing");
    const request = ++requestRef.current;
    const objectUrl = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.src = objectUrl;
      await image.decode();
      if (request !== requestRef.current) return;
      const canvas = canvasRef.current;
      if (!canvas || !image.naturalWidth || !image.naturalHeight) {
        throw new Error(t(language, "badImage"));
      }
      const scale = Math.min(1, 960 / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.round(image.naturalWidth * scale);
      canvas.height = Math.round(image.naturalHeight * scale);
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) throw new Error(t(language, "canvasImageFailure"));
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      setPhotoSource("file");
      setCameraAspect(canvas.width / canvas.height);
      await analyzeCanvas(canvas);
    } catch (cause) {
      if (request !== requestRef.current) return;
      setError(cause instanceof Error ? cause.message : t(language, "imageUnknown"));
      setPhase("idle");
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  };

  const saveObservations = async () => {
    if (!reading) return;
    const file = new File([reportMode === "brief" ? shortLifeReadingAsText(reading, language) : readingAsText(reading, language)], "faceface-reading.txt", { type: "text/plain;charset=utf-8" });
    // iOS can use the native share sheet to save the text in Files.
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: "Faceface 传统文化参考报告" });
        return;
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        // Fall back to a regular browser download if native sharing fails.
      }
    }
    const objectUrl = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = "faceface-reading.txt";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
  };

  return (
    <div className="site-shell">
      <header className="masthead">
        <div className="brand">faceface<span className="brand-dot">.</span></div>
        <div className="header-controls"><span className="version-chip">{t(language, "version")}</span><button className="lang-switch" type="button" aria-label="Switch language / 切换语言" onClick={() => setLanguage(value => value === "en" ? "zh" : "en")}>{t(language, "switchLanguage")}</button></div>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">{t(language, "eyebrow")}</p>
          <h1>{t(language, "heroFirst")}<br /><em>{t(language, "heroSecond")}</em></h1>
          <p className="subtitle">{t(language, "subtitle")}</p>
        </section>

        <section className="workbench" aria-label={t(language, "cameraTitle")}>
          <div className="stage-header">
            <div><span className="step-label">{t(language, "cameraStep")}</span><h2>{t(language, "cameraTitle")}</h2></div>
            <span className="privacy-mark">{t(language, "privateLabel")}</span>
          </div>
          <div
            ref={stageRef}
            className="camera-stage"
            style={cameraAspect !== null && phase !== "idle" ? { aspectRatio: cameraAspect } : undefined}
          >
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              onLoadedMetadata={() => {
                const video = videoRef.current;
                if (video?.videoWidth && video.videoHeight) {
                  setCameraAspect(video.videoWidth / video.videoHeight);
                }
              }}
              className={phase === "camera" ? "camera-video" : "offscreen"}
              aria-label={t(language, "cameraTitle")}
            />
            <canvas
              ref={canvasRef}
              className={(phase === "analyzing" || phase === "result" ? "photo-canvas" : "offscreen") +
                (photoSource === "camera" ? " photo-canvas--selfie" : "")}
              aria-label={t(language, "observationTitle")}
            />
            {phase === "idle" && <div className="camera-placeholder"><span className="placeholder-icon">◎</span><p>{t(language, "cameraIdle")}</p><small>{t(language, "cameraHint")}</small></div>}
            {phase === "analyzing" && <div className="processing-layer" role="status">{t(language, "analyzing")}<small>{t(language, "analyzingHint")}</small></div>}
            {phase === "camera" && (
              <div className="face-guide-layer">
                {guideMode === "front"
                  ? <LiveFaceOverlay path={liveFace.path} frameWidth={liveFace.width}
                      frameHeight={liveFace.height} progress={guideProgress} ready={guideReady} />
                  : <FaceGuideOverlay mode="side" ready={false} progress={0} />}
                <div className={"guide-status" + (guideReady ? " guide-status--ready" : "")}
                     role="status" aria-live="polite" data-guide-status={guideReady ? "ready" : guideStatus}>
                  {guideMode === "side" ? t(language, "guideSideNotice") :
                    guideReady ? t(language, "guideReady") :
                    guideStatus === "aligned" ?
                      t(language, "guideHolding").replace("{seconds}",
                        Math.max(1, Math.ceil((READY_HOLD_MS * (1 - guideProgress)) / 1000)).toString()) :
                    t(language, ({
                      loading: "guideLoading",
                      "no-face": "guideNoFace",
                      multiple: "guideMultiple",
                      pose: "guidePose",
                      "too-small": "guideTooSmall",
                      "too-large": "guideTooLarge",
                      outside: "guideOutside",
                      moving: "guideMoving",
                      "side-preview": "guideSideNotice"
                    } as const)[guideStatus])}
                </div>
              </div>
            )}
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
          <div className="actions">
            {phase === "idle" && <>
              <button className="primary" onClick={() => void begin()}>{t(language, "openCamera")}</button>
              <label className="secondary file-action">
                {t(language, "galleryFallback")}
                <input
                  className="file-input"
                  aria-label={t(language, "choosePhoto")}
                  type="file"
                  accept="image/*"
                  onChange={event => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    void selectLocalPhoto(file);
                  }}
                />
              </label>
            </>}
            {phase === "camera" && <>
              <button className="primary" disabled={!guideReady || guideMode !== "front"}
                onClick={() => void capture()}>{t(language, "takePhoto")}</button>
              <button className="secondary" onClick={reset}>{t(language, "closeCamera")}</button>
            </>}
            {phase === "analyzing" && <button className="secondary" onClick={reset}>{t(language, "cancelAnalysis")}</button>}
            {phase === "result" && <button className="secondary" onClick={reset}>{t(language, "retake")}</button>}
          </div>
          {phase === "camera" && (
            <>
              <p className="camera-capture-help">{t(language, "guideReadyHint")}</p>
            </>
          )}
          <p className="privacy-detail">{t(language, "privacyDetail")}</p>
        </section>

        {analysis && phase === "result" && (
          <section className="report" aria-live="polite">
            <div className="stage-header"><div><span className="step-label">{language === "en" ? "YOUR FACE READING" : "你的面相解读"}</span><h2>{language === "en" ? "Your life reading" : "人生面相解读"}</h2></div></div>
            {analysis.status === "ok" && reading && (
              <div className="reading-mode-switch" role="group" aria-label={language === "en" ? "Report detail level" : "报告版本"}>
                <button type="button" aria-pressed={reportMode === "brief"}
                  className={reportMode === "brief" ? "active" : ""}
                  onClick={() => setReportMode("brief")}>{language === "en" ? "Quick Reading" : "简要版"}</button>
                <button type="button" aria-pressed={reportMode === "detailed"}
                  className={reportMode === "detailed" ? "active" : ""}
                  onClick={() => setReportMode("detailed")}>{language === "en" ? "Detailed Reading" : "详细版"}</button>
              </div>
            )}
            {analysis.status !== "ok" && <p className="error-message">{localizeAnalysisMessage(analysis, language)}</p>}
            {reportMode === "detailed" && <p className="report-intro">{localizeAnalysisMessage(analysis, language)}</p>}
            {reportMode === "detailed" && timing && <p className="privacy-detail" role="status">{t(language, "modelTime")} {timing.modelMs} {t(language, "ms")} · {t(language, "inferenceTime")} {timing.inferenceMs} {t(language, "ms")}. {t(language, "timingNotice")}</p>}
            {analysis.status === "ok" && (
              <>
                {reading && (
                  <div className="life-reading-brief" aria-label={language === "en" ? "Short life reading" : "简要面相解读"}>
                    <div className="life-reading-intro">
                      <span>{language === "en" ? "A READING OF LIFE'S CHAPTERS" : "生平与未来的传统解读"}</span>
                      <h3>{language === "en" ? "Your story, through an old lens" : "从面相意象，看人生篇章"}</h3>
                      <p>{language === "en"
                        ? "These are possible interpretations, not known facts about your past or dependable predictions of your future."
                        : "以下是传统面相主题的可能解读，不是已知的过去事实，也不是可靠的未来预言。"}</p>
                    </div>
                    {reading.lifeNarratives.length ? (
                      <div className="life-reading-card-list">
                        {reading.lifeNarratives.map((item,index) => (
                          <article className="life-reading-card" key={item.sourceCardId}>
                            <span className="life-reading-number">{String(index + 1).padStart(2,"0")}</span>
                            <h4>{item.title}</h4>
                            <div className="life-reading-segment">
                              <h5>{language === "en" ? "Traditional theme" : "传统解读主题"}</h5>
                              <p>{item.temperament}</p>
                            </div>
                            <div className="life-reading-segment">
                              <h5>{language === "en" ? "Reflecting on the past" : "回顾过往 · 自我思考"}</h5>
                              <p>{item.retrospective}</p>
                            </div>
                            <div className="life-reading-segment">
                              <h5>{language === "en" ? "Looking ahead · reflection" : "展望未来 · 生活启发"}</h5>
                              <p>{item.outlook}</p>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="life-reading-no-match">{language === "en"
                        ? "There is not enough matching facial-shape evidence in this photo to offer a specific reading. We won't invent a past for you."
                        : "这张照片没有足够的形态线索形成具体解读，我们不会凭空编造你的过往。"}</p>
                    )}
                    <p className="life-reading-footnote">{language === "en"
                      ? "Does any part feel familiar? Compare it with what really happened. A resemblance cannot establish that face reading works."
                      : "哪些描述与你的经历相似？请结合真实经历自行核对；描述相似并不能证明面相预测准确。"}</p>
                  </div>
                )}
                {reportMode === "detailed" && (<>
                <p className="report-intro">{language === "en"
                  ? "This reading is based on visible proportions of the eyes, nose, mouth and facial outline in your front-facing photo."
                  : "本次解读依据正脸照片中可观察的眼、鼻、口及面部轮廓比例。"}</p>
                <div className="observations">
                  {observations.map(item => (
                    <article className="observation" key={item.id}>
                      <span className="region">{item.region}</span><strong>{item.text}</strong>
                      {showMeasurements && <small>{item.measurement}: {item.ratio} {t(language, "measurementQualifier")}</small>}
                    </article>
                  ))}
                </div>
                {reading && (
                  <div className="cultural-reading">
                    <div className="reading-heading">
                      <span className="step-label">{t(language, "culturalStep")}</span>
                      <h3>{t(language, "culturalTitle")} <span className="preview-label">{t(language, "culturalVersion")}</span></h3>
                    </div>
                    <p className="report-intro">{reading.overview}</p>
                    <p className="report-intro">{reading.patternSummary}</p>
                    {reading.crossRegionStudy && (
                      <section className="cross-region-reading" aria-label={reading.crossRegionStudy.title}>
                        <h4>{reading.crossRegionStudy.title}</h4>
                        <p>{reading.crossRegionStudy.narrative}</p>
                        <div className="cross-region-citations">
                          {reading.featuredLinks.map(link => (
                            <a key={link.cardId} href={link.source.source_url}
                              target="_blank" rel="noopener noreferrer">
                              {link.organ} · {link.historicalTerm} · {link.source.volume}《{link.source.section}》
                              ({t(language, "pageIndex")} {link.source.pdf_page_zero_based})
                            </a>
                          ))}
                        </div>
                      </section>
                    )}
                    {reading.threeSections && (
                      <section className="three-sections-reading" aria-label={reading.threeSections.title}>
                        <h4>{reading.threeSections.title}</h4>
                        <p>{reading.threeSections.summary}</p>
                        <div className="three-sections-bar" role="img"
                          aria-label={reading.threeSections.summary}>
                          {reading.threeSections.parts.map(part => (
                            <div key={part.id} className={"three-sections-part three-sections-part--" + part.id}
                              style={{ width: (part.percent || .1) + "%" }} />
                          ))}
                        </div>
                        <div className="three-sections-labels">
                          {reading.threeSections.parts.map(part => (
                            <span key={part.id}>{part.label} · {part.percent}%</span>
                          ))}
                        </div>
                        <small>{reading.threeSections.caveat}</small>
                        <a href={reading.threeSections.source.source_url} target="_blank" rel="noopener noreferrer">
                          {t(language, "originalScan")}: {reading.threeSections.source.volume}《{reading.threeSections.source.section}》
                          ({t(language, "pageIndex")} {reading.threeSections.source.pdf_page_zero_based})
                        </a>
                      </section>
                    )}
                    <div className="reading-insights" aria-label={language === "en" ? "Cultural reading" : "本次文化解读"}>
                      {reading.briefInsights.map((paragraph, index) => (
                        <p key={index}>{paragraph}</p>
                      ))}
                    </div>
                    <div className="source-highlights">
                      {reading.featuredLinks.map(link => (
                        <article className="source-highlight" key={link.cardId}>
                          <span className="region">{link.organ} · {link.traditionalName}</span>
                          <strong>{t(language, "ancientPhrase")}: 「{link.historicalTerm}」{link.historicalGloss ? " — " + link.historicalGloss : ""}</strong>
                          <small>{t(language, "relatedFootnote")}</small>
                          <a href={link.source.source_url} target="_blank" rel="noopener noreferrer">
                            {t(language, "originalScan")}: {link.source.volume}《{link.source.section}》 ({t(language, "pageIndex")} {link.source.pdf_page_zero_based})
                          </a>
                        </article>
                      ))}
                    </div>
                    {reading.modernReflections.length > 0 && (
                      <section className="editorial-reflections"
                        aria-label={language === "en" ? "Everyday reflection prompts" : "日常反思卡片"}>
                        <div className="editorial-reflections-header">
                          <span className="editorial-kicker">
                            {language === "en" ? "A MOMENT TO REFLECT" : "一个值得想想的时刻"}
                          </span>
                          <h4>{language === "en" ? "See beyond the first impression" : "不止于第一眼的印象"}</h4>
                          <p>{language === "en"
                            ? "Inspired by the imagery of the old text, written in plain language for today. These are invitations to reflect, not personality facts inferred from your face."
                            : "借古籍的形态意象展开，用今天能理解的话说生活。以下是邀请你思考的场景，不是根据面相得出的性格事实。"}</p>
                        </div>
                        <div className="editorial-reflection-grid">
                          {reading.modernReflections.map((item, index) => (
                            <article className="editorial-story" key={item.sourceCardId}>
                              <span className="editorial-story-index">{String(index + 1).padStart(2, "0")} / {reading.modernReflections.length.toString().padStart(2, "0")}</span>
                              <h5>{item.theme}</h5>
                              {reading.featuredLinks.filter(link => link.cardId === item.sourceCardId).map(link => (
                                <div className="editorial-classical-bridge" key={link.cardId}>
                                  <span>{language === "en" ? "THE CLASSICAL IMAGE" : "古籍中的意象"}</span>
                                  <p>{language === "en"
                                    ? (link.historicalGloss || link.historicalTerm)
                                    : link.historicalTerm}</p>
                                  <small>{language === "en"
                                    ? "A partial appearance comparison, not a personality assessment."
                                    : "仅为外形的局部对照，不是性格判断。"}</small>
                                  <a href={link.source.source_url} target="_blank" rel="noopener noreferrer">
                                    {language === "en" ? "Original scanned page" : "查看原书扫描"} · {link.source.volume} · {link.source.pdf_page_zero_based + 1}
                                  </a>
                                </div>
                              ))}
                              <p className="editorial-story-scene">{item.scene}</p>
                              <div className="editorial-story-question">
                                <span>{language === "en" ? "A QUESTION FOR YOU" : "留给你的问题"}</span>
                                <p>{item.question}</p>
                              </div>
                              <div className="editorial-story-practice">
                                <span>{language === "en" ? "ONE SMALL THING TO TRY" : "一个可以试试的小行动"}</span>
                                <p>{item.practice}</p>
                              </div>
                            </article>
                          ))}
                        </div>
                        <p className="editorial-footnote">{language === "en"
                          ? "Contemporary editorial writing · Not an ancient quotation, diagnosis or prediction."
                          : "现代编辑文字 · 并非古籍原句、人格诊断或命运预测。"}</p>
                      </section>
                    )}
                    <p className="reflection">{reading.reflection}</p>
                    <details className="source-details">
                      <summary>{t(language, "expandedTitle")}</summary>
                      <p>{reading.evidenceNotice}</p>
                      <section className="classical-life-claims" aria-label={language === "en" ? "Historical life-outcome passages" : "古籍生平断语出处"}>
                        <h4>{language === "en" ? "What the original text actually says about life" : "原书记载的生平断语"}</h4>
                        <p>{language === "en"
                          ? "Archived traditional claims, quoted in context. These are not claims about your own past or future: an approximate photo measurement cannot verify an entire classical face type."
                          : "这里收录原书中的传统生平断语，并说明对应原页。局部照片相似不等于完整相型成立，不能将古籍说法当作你的真实过往或未来。"}</p>
                        {reading.classicalLifeOutcomes.map(item => (
                          <article className="classical-life-claim" key={item.id}>
                            <span className="historical-quote">「{item.historicalQuote}」</span>
                            <p>{item.explanation}</p>
                            <small>{language === "en"
                              ? (item.sourceCardMatchStatus === "related-observation"
                                ? "Photo: partial resemblance only; classical type not confirmed."
                                : "Photo: insufficient for this classical type.")
                              : (item.sourceCardMatchStatus === "related-observation"
                                ? "本次照片：仅有局部相似，不能确认完整古籍相型。"
                                : "本次照片：不能确认符合此古籍相型。")}</small>
                            <a href={item.source.source_url} target="_blank" rel="noopener noreferrer">
                              {language === "en" ? "View original scan" : "查看原书扫描"} · {item.source.volume}《{item.source.section}》 · {language === "en" ? "PDF page" : "PDF页码"} {item.source.pdf_page_zero_based + 1}
                            </a>
                          </article>
                        ))}
                      </section>
                      {reading.sourceLinks.map(link => (
                        <article className="source-detail" key={link.cardId}>
                          <h4>{link.organ}: {link.historicalTerm} {link.historicalGloss ? " — " + link.historicalGloss : ""} <span>({language === "en" ? (link.status === "related-observation" ? "Related observation" : "Insufficient evidence") : (link.status === "related-observation" ? "相关观察" : "条件不足")})</span></h4>
                          <p>{t(language, "observed")}: {link.observation}</p>
                          <p>{link.explanation}</p>
                          <p className="source-tradition">{language === "en" ? "Historic cultural reading (not a factual prediction): " : "古籍文化释义（非现实预测）："}{link.historicalView}</p>
                          <p>{t(language, "caution")}: {link.caveat}</p>
                          <a href={link.source.source_url} target="_blank" rel="noopener noreferrer">
                            {t(language, "originalScan")}: 《{link.source.work}》{link.source.volume}《{link.source.section}》 ({t(language, "pageIndex")} {link.source.pdf_page_zero_based})
                          </a>
                        </article>
                      ))}
                    <section className="historical-frameworks" aria-label={language === "en" ? "Historical framework" : "古籍取象背景"}>
                      <h4>{language === "en" ? "How the classic organizes facial regions" : "古籍如何组织面部部位"}</h4>
                      <p className="privacy-detail">{language === "en"
                        ? "These are historical metaphors, not personalized matches or predictions."
                        : "以下是历史文化取象说明，不是针对个人的相型匹配或未来预测。"}</p>
                      <div className="framework-grid">
                        {reading.frameworkNotes.map(note => (
                          <article className="framework-note" key={note.id}>
                            <strong>{note.title}</strong>
                            <span className="historical-quote">「{note.quote}」</span>
                            <p>{note.explanation}</p>
                            <a href={note.source.source_url} rel="noopener noreferrer" target="_blank">
                              {t(language, "originalScan")}: 《{note.source.section}》 ({t(language, "pageIndex")} {note.source.pdf_page_zero_based})
                            </a>
                          </article>
                        ))}
                      </div>
                    </section>
                    </details>
                  </div>
                )}
                </>)}
                {comparison && reportMode === "detailed" && (
                  <section className="consistency-panel" aria-label={t(language, "compareTitle")}>
                    <h3>{t(language, "compareTitle")}</h3>
                    <div className="consistency-totals" role="status">
                      <div><strong>{comparison.labelChangeCount} / {comparison.descriptors.length}</strong><span>{t(language, "compareLabels")}</span></div>
                      <div><strong>{comparison.historicalChangeCount} / {comparison.historical.length}</strong><span>{t(language, "compareSources")}</span></div>
                    </div>
                    {comparison.labelChangeCount === 0 && comparison.historicalChangeCount === 0 && (
                      <p className="privacy-detail">{t(language, "compareNone")}</p>
                    )}
                    <details className="consistency-details">
                      <summary>{t(language, "compareDetails")}</summary>
                      <div className="consistency-observations">
                        {comparison.descriptors.map(item => (
                          <article className={item.labelChanged ? "consistency-item consistency-changed" : "consistency-item"} key={item.id} data-field-id={item.id}>
                            <strong>{localizeDescriptor(item.first, language).region}</strong>
                            <p><span>{t(language, "compareFirst")}:</span> {localizeDescriptor(item.first, language).text}</p>
                            <p><span>{t(language, "compareSecond")}:</span> {item.second ? localizeDescriptor(item.second, language).text : t(language, "compareMissing")}</p>
                            {item.first.certainty !== item.second?.certainty && (
                              <p><span>{t(language, "compareEvidence")}:</span> {evidenceLabel(item.first.certainty, language)} → {evidenceLabel(item.second?.certainty, language)}</p>
                            )}
                            {item.ratioDelta !== null && <small>Δ {item.ratioDelta.toFixed(3)} {t(language, "measurementQualifier")}</small>}
                          </article>
                        ))}
                      </div>
                      {comparison.threeSections && (
                        <section className="consistency-observations" aria-label={t(language, "compareThreeSections")}>
                          <h4>{t(language, "compareThreeSections")}</h4>
                          <p className="privacy-detail">{t(language, "compareSectionLimits")}</p>
                          {comparison.threeSections.map(part => (
                            <p className="consistency-zone-row" key={part.id}>
                              <strong>{t(language, part.id === "upper" ? "compareUpperZone" : part.id === "middle" ? "compareMiddleZone" : "compareLowerZone")}</strong>:{" "}
                              {part.firstPercent === null ? t(language, "compareMissing") : part.firstPercent.toFixed(1) + "%"} →{" "}
                              {part.secondPercent === null ? t(language, "compareMissing") : part.secondPercent.toFixed(1) + "%"}
                              {part.deltaPoints !== null && <small> (Δ {part.deltaPoints.toFixed(1)} {language === "en" ? "percentage points" : "个百分点"})</small>}
                            </p>
                          ))}
                        </section>
                      )}
                      <h4>{t(language, "compareSourceChanges")}</h4>
                      {comparison.historicalChangeCount === 0
                        ? <p>{t(language, "compareNoSource")}</p>
                        : comparison.historical.filter(item => item.changed).map(item => (
                          <p className="consistency-source-change" key={item.cardId} data-source-id={item.cardId}>
                            「{item.historicalTerm}」: {item.firstRelated ? t(language, "compareRelated") : t(language, "compareNotRelated")} → {item.secondRelated ? t(language, "compareRelated") : t(language, "compareNotRelated")}
                          </p>
                        ))}
                    </details>
                  </section>
                )}
                <div className="actions">
                  <button className="primary" onClick={() => void saveObservations()}>{t(language, "saveReport")}</button>
                  {reportMode === "detailed" && <button className="secondary" onClick={() => setShowMeasurements(value => !value)}>{t(language, showMeasurements ? "hideMeasurements" : "showMeasurements")}</button>}
                  {reportMode === "detailed" && <label className="secondary file-action">
                    {t(language, "compareAction")}
                    <input
                      className="file-input"
                      type="file"
                      accept="image/*"
                      aria-label={t(language, "compareInput")}
                      onChange={event => {
                        const file = event.target.files?.[0];
                        event.target.value = "";
                        if (!file) return;
                        if (file.type.startsWith("image/") && file.size <= 12 * 1024 * 1024) {
                          setComparisonBaseline(analysis);
                        }
                        void selectLocalPhoto(file);
                      }}
                    />
                  </label>}
                </div>
                {reportMode === "detailed" && <p className="privacy-detail">{t(language, "compareNotice")}</p>}
                <p className="disclaimer">{t(language, "disclaimer")}</p>
              </>
            )}
          </section>
        )}
      </main>
      <footer><span>{t(language, "footer")}</span><a href="./privacy.html">{t(language, "privacyLink")}</a></footer>
    </div>
  );
}
