import { useCallback, useEffect, useRef, useState } from "react";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { describeLandmarks, type Analysis } from "./descriptors";
import { makeReading, readingAsText } from "./reading";
import { localizeAnalysisMessage, localizeDescriptor, t, type Language } from "./i18n";

type Phase = "idle" | "camera" | "analyzing" | "result";

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
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<FaceLandmarker | null>(null);
  const loadingRef = useRef<Promise<FaceLandmarker> | null>(null);
  const mountedRef = useRef(false);
  const requestRef = useRef(0);
  const [language, setLanguage] = useState<Language>("en");
  const [phase, setPhase] = useState<Phase>("idle");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [cameraAspect, setCameraAspect] = useState<number | null>(null);
  const [photoSource, setPhotoSource] = useState<"camera" | "file" | null>(null);
  const [timing, setTiming] = useState<{ modelMs: number; inferenceMs: number } | null>(null);
  const reading = analysis ? makeReading(analysis, language) : null;
  const observations = analysis?.descriptors.map(d => localizeDescriptor(d, language)) ?? [];

  useEffect(() => {
    document.documentElement.lang = language === "en" ? "en" : "zh-CN";
    document.title = language === "en" ? "Faceface · Face patterns and cultural history" : "Faceface · 面部形态观察";
  }, [language]);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const reset = () => {
    requestRef.current += 1;
    stopCamera();
    setPhase("idle");
    setAnalysis(null);
    setError("");
    setShowMeasurements(false);
    setTiming(null);
    setCameraAspect(null);
    setPhotoSource(null);
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
      setTiming(null);
      setCameraAspect(null);
      setPhotoSource(null);
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
      const inferenceStart = performance.now();
      const result = model.detect(canvas);
      const inferenceMs = performance.now() - inferenceStart;
      if (request !== requestRef.current) return;
      setTiming({ modelMs: Math.round(modelMs), inferenceMs: Math.round(inferenceMs) });
      setAnalysis(describeLandmarks(result.faceLandmarks, { width: canvas.width, height: canvas.height }));
      setPhase("result");
    } catch (cause) {
      if (request !== requestRef.current) return;
      setError(cause instanceof Error ? t(language, "modelFailure") + ": " + cause.message : t(language, "modelUnknown"));
      setPhase("result");
    }
  };

  const capture = async () => {
    if (phase !== "camera") return;
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
    const file = new File([readingAsText(reading, language)], "faceface-reading.txt", { type: "text/plain;charset=utf-8" });
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
            {phase === "camera" && <div className="guide-oval" aria-hidden="true" />}
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
            {phase === "camera" && <><button className="primary" onClick={() => void capture()}>{t(language, "takePhoto")}</button><button className="secondary" onClick={reset}>{t(language, "closeCamera")}</button></>}
            {phase === "analyzing" && <button className="secondary" onClick={reset}>{t(language, "cancelAnalysis")}</button>}
            {phase === "result" && <button className="secondary" onClick={reset}>{t(language, "retake")}</button>}
          </div>
          <p className="privacy-detail">{t(language, "privacyDetail")}</p>
        </section>

        {analysis && phase === "result" && (
          <section className="report" aria-live="polite">
            <div className="stage-header"><div><span className="step-label">{t(language, "observationStep")}</span><h2>{t(language, "observationTitle")}</h2></div></div>
            <p className={analysis.status === "ok" ? "report-intro" : "error-message"}>{localizeAnalysisMessage(analysis, language)}</p>
            {timing && <p className="privacy-detail" role="status">{t(language, "modelTime")} {timing.modelMs} {t(language, "ms")} · {t(language, "inferenceTime")} {timing.inferenceMs} {t(language, "ms")}. {t(language, "timingNotice")}</p>}
            {analysis.status === "ok" && (
              <>
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
                    {reading.sourceLinks.every(link => link.status !== "related-observation") && (
                      <p className="privacy-detail">{language === "en"
                        ? "No checked historical phrase has even a limited directional resemblance to this photo. The detailed source notes remain available for context."
                        : "本次未找到满足局部形态相似条件的已核查古籍用语。仍可在详细报告中阅读原文及条件不足的原因。"}</p>
                    )}
                    <div className="source-highlights">
                      {reading.sourceLinks.filter(link => link.status === "related-observation").map(link => (
                        <article className="source-highlight" key={link.cardId}>
                          <span className="region">{link.organ} · {link.traditionalName}</span>
                          <strong>{t(language, "ancientPhrase")}: 「{link.historicalTerm}」{link.historicalGloss ? " — " + link.historicalGloss : ""}</strong>
                          <p>{link.observation}</p>
                          <small>{t(language, "relatedFootnote")}</small>
                        </article>
                      ))}
                    </div>
                    <p className="reflection">{reading.reflection}</p>
                    <details className="source-details">
                      <summary>{t(language, "expandedTitle")}</summary>
                      <p>{reading.evidenceNotice}</p>
                      {reading.sourceLinks.map(link => (
                        <article className="source-detail" key={link.cardId}>
                          <h4>{link.organ}: {link.historicalTerm} {link.historicalGloss ? " — " + link.historicalGloss : ""} <span>({language === "en" ? (link.status === "related-observation" ? "Related observation" : "Insufficient evidence") : (link.status === "related-observation" ? "相关观察" : "条件不足")})</span></h4>
                          <p>{t(language, "observed")}: {link.observation}</p>
                          <p>{link.explanation}</p>
                          <p>{t(language, "caution")}: {link.caveat}</p>
                          <a href={link.source.source_url} target="_blank" rel="noopener noreferrer">
                            {t(language, "originalScan")}: 《{link.source.work}》{link.source.volume}《{link.source.section}》 ({t(language, "pageIndex")} {link.source.pdf_page_zero_based})
                          </a>
                        </article>
                      ))}
                    </details>
                  </div>
                )}
                <div className="actions">
                  <button className="primary" onClick={() => void saveObservations()}>{t(language, "saveReport")}</button>
                  <button className="secondary" onClick={() => setShowMeasurements(value => !value)}>{t(language, showMeasurements ? "hideMeasurements" : "showMeasurements")}</button>
                </div>
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
