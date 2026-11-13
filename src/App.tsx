import { useCallback, useEffect, useRef, useState } from "react";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { describeLandmarks, type Analysis } from "./descriptors";

type Phase = "idle" | "camera" | "analyzing" | "result";
const WASM_ROOT = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm";
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

export default function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<FaceLandmarker | null>(null);
  const loadingRef = useRef<Promise<FaceLandmarker> | null>(null);
  const requestRef = useRef(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [cameraAspect, setCameraAspect] = useState<number | null>(null);
  const [timing, setTiming] = useState<{ modelMs: number; inferenceMs: number } | null>(null);

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

  useEffect(() => () => {
    requestRef.current += 1;
    stopCamera();
    landmarkerRef.current?.close();
    landmarkerRef.current = null;
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
      if (document.hidden) discardOnLeave();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", discardOnLeave);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", discardOnLeave);
    };
  }, [stopCamera]);

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
      setError(cause instanceof Error ? "无法打开相机：" + cause.message : "无法打开摄像头，请检查浏览器权限。");
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
        landmarkerRef.current = model;
        return model;
      })().catch(cause => {
        loadingRef.current = null;
        throw cause;
      });
    }
    return loadingRef.current;
  };

  const capture = async () => {
    if (phase !== "camera") return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2 || video.videoWidth === 0) {
      setError("相机尚未准备好，请稍后再拍。");
      return;
    }
    const maxSide = 960;
    const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) {
      setError("浏览器无法读取相机画面。");
      return;
    }
    // Draw to an in-memory canvas, never to a server or browser persistence API.
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    stopCamera();
    setPhase("analyzing");
    setError("");
    const request = ++requestRef.current;
    const modelStart = performance.now();
    try {
      const model = await loadLandmarker();
      const modelMs = performance.now() - modelStart;
      if (request !== requestRef.current) return;
      // Let the analyzing state paint before synchronous single-frame inference.
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

  const saveObservations = () => {
    if (!analysis || analysis.status !== "ok") return;
    const lines = [
      "Faceface — 面部形态观察（技术验证）",
      "这只是实验性几何描述，不是已校验的传统相法报告，也不是人格/命运判断。",
      "",
      ...analysis.descriptors.map(item =>
        item.region + "：" + item.text + "\n计算：" + item.measurement + " = " + item.ratio + "\n说明：" + item.caveat + "\n"
      )
    ];
    const objectUrl = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }));
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
        <span className="version-chip">M1 · 本地识别实验版</span>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">TRADITIONAL FACE CULTURE · VISUAL RESEARCH</p>
          <h1>让面部形态，<br /><em>成为可读的语言。</em></h1>
          <p className="subtitle">用真实的相机画面测试浏览器端特征提取。这一版本先验证“看见什么”，古籍解读将在来源核验后接入。</p>
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
            {phase === "idle" && <button className="primary" onClick={() => void begin()}>开启前置摄像头</button>}
            {phase === "camera" && <><button className="primary" onClick={() => void capture()}>拍摄并本地分析</button><button className="secondary" onClick={reset}>关闭相机</button></>}
            {phase === "analyzing" && <button className="secondary" onClick={reset}>取消分析并清除画面</button>}
            {phase === "result" && <button className="secondary" onClick={reset}>清除画面 / 重新拍摄</button>}
          </div>
          <p className="privacy-detail">切换到其他应用或隐藏页面时会停止相机并清除临时画面。相机权限仅由你的操作触发；照片与特征默认不写入浏览器存储或应用服务器。自拍预览和展示画面使用镜像，模型在未镜像的原始帧上计算。模型和运行文件会从第三方 CDN 下载，相关网络与 SDK 指标仍需上线前审计。</p>
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
                <div className="actions">
                  <button className="primary" onClick={saveObservations}>保存文字观察结果</button>
                  <button className="secondary" onClick={() => setShowMeasurements(value => !value)}>{showMeasurements ? "隐藏" : "查看"}计算依据</button>
                </div>
                <p className="disclaimer">以上描述只表示此照片中测得的几何比例。单张自拍会受到姿态、光线、表情、相机透视与妆容影响；不能据此判断人格、健康、道德或命运。古籍规则尚未接入，不会伪造典籍出处。</p>
              </>
            )}
          </section>
        )}
      </main>
      <footer><span>Faceface · Research build 0.1</span><span>不注册 · 不设照片上传端点 · 无广告</span></footer>
    </div>
  );
}
