import { useCallback, useEffect, useRef, useState } from "react";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { describeLandmarks, type Analysis } from "./descriptors";
import { makeReading, readingAsText } from "./reading";

type Phase = "idle" | "camera" | "analyzing" | "result";

function cameraFailure(cause: unknown): string {
  if (cause instanceof DOMException) {
    if (cause.name === "NotAllowedError" || cause.name === "PermissionDeniedError") {
      return "未获得摄像头权限。请在浏览器的网站设置中允许相机后重新尝试。";
    }
    if (cause.name === "NotFoundError" || cause.name === "DevicesNotFoundError") {
      return "没有检测到可用摄像头。请检查设备或连接外接摄像头。";
    }
    if (cause.name === "NotReadableError" || cause.name === "TrackStartError") {
      return "摄像头可能正被其他应用占用。请关闭占用摄像头的应用后重试。";
    }
  }
  return cause instanceof Error ? "无法打开相机：" + cause.message : "无法打开摄像头，请检查浏览器权限。";
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
  const [phase, setPhase] = useState<Phase>("idle");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [cameraAspect, setCameraAspect] = useState<number | null>(null);
  const [timing, setTiming] = useState<{ modelMs: number; inferenceMs: number } | null>(null);
  const reading = analysis ? makeReading(analysis) : null;

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
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError("摄像头需要 HTTPS（或本地 localhost）以及支持摄像头的浏览器。");
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
      if (!video) throw new Error("相机预览未初始化");
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
      setError(cameraFailure(cause));
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
      setError(cause instanceof Error ? "本地模型运行失败：" + cause.message : "模型初始化失败，请检查网络和浏览器。");
      setPhase("result");
    }
  };

  const capture = async () => {
    if (phase !== "camera") return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2 || video.videoWidth === 0) {
      setError("相机尚未准备好，请稍后再拍。");
      return;
    }
    const scale = Math.min(1, 960 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) {
      setError("浏览器无法读取相机画面。");
      return;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    await analyzeCanvas(canvas);
  };

  const selectLocalPhoto = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 12 * 1024 * 1024) {
      setError("请选择不超过 12MB 的本地图片。");
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
        throw new Error("无法读取这张图片，请选择另一张。");
      }
      const scale = Math.min(1, 960 / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.round(image.naturalWidth * scale);
      canvas.height = Math.round(image.naturalHeight * scale);
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) throw new Error("浏览器无法处理图片。");
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      setCameraAspect(canvas.width / canvas.height);
      await analyzeCanvas(canvas);
    } catch (cause) {
      if (request !== requestRef.current) return;
      setError(cause instanceof Error ? cause.message : "无法打开图片。");
      setPhase("idle");
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  };

  const saveObservations = async () => {
    if (!reading) return;
    const file = new File([readingAsText(reading)], "faceface-reading.txt", { type: "text/plain;charset=utf-8" });
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
    anchor.download = "faceface-observation.txt";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
  };

  return (
    <div className="site-shell">
      <header className="masthead">
        <div className="brand">faceface<span className="brand-dot">.</span></div>
        <span className="version-chip">M1/M2 · HTTPS 技术测试版</span>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">TRADITIONAL FACE CULTURE · VISUAL RESEARCH</p>
          <h1>让面部形态，<br /><em>成为可读的语言。</em></h1>
          <p className="subtitle">用真实的相机画面测试浏览器端特征提取。这一版本先验证“看见什么”，目前展示经过原页核对的少量历史用语关联，完整古籍报告仍在开发中。</p>
        </section>

        <section className="workbench" aria-label="面部观察">
          <div className="stage-header">
            <div><span className="step-label">01 / CAMERA</span><h2>拍摄正面照片</h2></div>
            <span className="privacy-mark">◌ 设备本地分析</span>
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
              aria-label="前置摄像头预览"
            />
            <canvas
              ref={canvasRef}
              className={phase === "analyzing" || phase === "result" ? "photo-canvas" : "offscreen"}
              aria-label="本次拍摄的内存画面"
            />
            {phase === "idle" && <div className="camera-placeholder"><span className="placeholder-icon">◎</span><p>相机尚未开启</p><small>光线均匀 · 面对镜头 · 不遮挡五官</small></div>}
            {phase === "analyzing" && <div className="processing-layer" role="status">正在本机加载模型并提取特征…<small>首次需要下载模型文件，不上传照片</small></div>}
            {phase === "camera" && <div className="guide-oval" aria-hidden="true" />}
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
          <div className="actions">
            {phase === "idle" && <>
              <button className="primary" onClick={() => void begin()}>开启前置摄像头</button>
              <label className="secondary file-action">
                摄像头不可用？从本地选择照片
                <input
                  className="file-input"
                  aria-label="从本地选择照片"
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
            {phase === "camera" && <><button className="primary" onClick={() => void capture()}>拍摄并本地分析</button><button className="secondary" onClick={reset}>关闭相机</button></>}
            {phase === "analyzing" && <button className="secondary" onClick={reset}>取消分析并清除画面</button>}
            {phase === "result" && <button className="secondary" onClick={reset}>清除画面 / 重新拍摄</button>}
          </div>
          <p className="privacy-detail">拍摄或分析期间切换到其他应用时会关闭相机并清除临时画面；已生成的结果仅保留在当前页面内存中，离开页面时清除。相机权限仅由你的操作触发；可选的本地照片直接由浏览器读取，不上传原图。照片与特征默认不写入浏览器存储或应用服务器。自拍预览和展示画面使用镜像，模型在未镜像的原始帧上计算。模型和运行文件会从第三方 CDN 下载，相关网络与 SDK 指标仍需上线前审计。</p>
        </section>

        {analysis && phase === "result" && (
          <section className="report" aria-live="polite">
            <div className="stage-header"><div><span className="step-label">02 / OBSERVATIONS</span><h2>面部形态描述</h2></div></div>
            <p className={analysis.status === "ok" ? "report-intro" : "error-message"}>{analysis.message}</p>
            {timing && <p className="privacy-detail" role="status">本机诊断：模型准备 {timing.modelMs} ms · 单帧推理 {timing.inferenceMs} ms。仅在本页面显示，不自动上传。</p>}
            {analysis.status === "ok" && (
              <>
                <div className="observations">
                  {analysis.descriptors.map(item => (
                    <article className="observation" key={item.id}>
                      <span className="region">{item.region}</span><strong>{item.text}</strong>
                      {showMeasurements && <small>{item.measurement}：{item.ratio}（实验阈值，未校准）</small>}
                    </article>
                  ))}
                </div>
                {reading && (
                  <div className="cultural-reading">
                    <div className="reading-heading">
                      <span className="step-label">03 / CULTURAL SOURCES</span>
                      <h3>简洁文化报告 <span className="preview-label">资料核对版</span></h3>
                    </div>
                    <p className="report-intro">{reading.overview}</p>
                    <div className="source-highlights">
                      {reading.sourceLinks.filter(link => link.status === "related-observation").map(link => (
                        <article className="source-highlight" key={link.cardId}>
                          <span className="region">{link.organ} · {link.traditionalName}</span>
                          <strong>古籍用语：「{link.historicalTerm}」</strong>
                          <p>{link.observation}</p>
                          <small>仅属于相关观察，不代表古籍相型已经成立。</small>
                        </article>
                      ))}
                    </div>
                    <p className="reflection">{reading.reflection}</p>
                    <details className="source-details">
                      <summary>展开详细报告：出处、条件与不足</summary>
                      <p>{reading.evidenceNotice}</p>
                      {reading.sourceLinks.map(link => (
                        <article className="source-detail" key={link.cardId}>
                          <h4>{link.organ}：{link.historicalTerm} <span>（{link.status === "related-observation" ? "相关观察" : "条件不足"}）</span></h4>
                          <p>本次照片：{link.observation}</p>
                          <p>{link.explanation}</p>
                          <p>注意：{link.caveat}</p>
                          <a href={link.source.source_url} target="_blank" rel="noopener noreferrer">
                            查看《{link.source.work}》{link.source.volume}《{link.source.section}》扫描原件（零起页{link.source.pdf_page_zero_based}）
                          </a>
                        </article>
                      ))}
                    </details>
                  </div>
                )}
                <div className="actions">
                  <button className="primary" onClick={() => void saveObservations()}>保存或分享文化报告</button>
                  <button className="secondary" onClick={() => setShowMeasurements(value => !value)}>{showMeasurements ? "隐藏" : "查看"}计算依据</button>
                </div>
                <p className="disclaimer">以上描述只表示此照片中测得的几何比例。单张自拍会受到姿态、光线、表情、相机透视与妆容影响；不能据此判断人格、健康、道德或命运。目前仅展示少量已核对的历史用语；不能把现代几何比例当作古籍完整相型。</p>
              </>
            )}
          </section>
        )}
      </main>
      <footer><span>Faceface · Technical preview · 不注册 / 无广告</span><a href="./privacy.html">隐私说明 / Privacy notice</a></footer>
    </div>
  );
}
