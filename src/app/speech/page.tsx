"use client";

import { useState, useRef } from "react";
import { useEffect } from "react";

export default function SpeechPage() {
  const [text, setText] = useState("");
  const [voice, setVoice] = useState("male_001");
  const [format, setFormat] = useState("mp3");
  const [speed, setSpeed] = useState<number | "">("");
  const [pitch, setPitch] = useState<number | "">("");
  const [clean, setClean] = useState(true);
  const [provider, setProvider] = useState<string>('minimax');
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string>("");
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    try {
      const cached = sessionStorage.getItem('speechText');
      if (cached) setText(cached);
    } catch {}
  }, []);

  const handleGenerate = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setAudioUrl("");
    try {
      const resp = await fetch("/api/speech/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          voice,
          format,
          speed: speed === "" ? undefined : Number(speed),
          pitch: pitch === "" ? undefined : Number(pitch),
          clean,
          provider,
        }),
      });
      if (!resp.ok) {
        const t = await resp.text();
        throw new Error(t || `HTTP ${resp.status}`);
      }
      // 如果返回的是音频流
      const ct = resp.headers.get("Content-Type") || "";
      if (ct.startsWith("audio/") || ct.includes("octet-stream")) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        setTimeout(() => audioRef.current?.play(), 300);
      } else {
        const data = await resp.json();
        if (data.url) {
          setAudioUrl(data.url);
        } else {
          throw new Error("未获取到音频");
        }
      }
    } catch (e: any) {
      alert(e.message || "生成失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen" style={{ backgroundColor: "var(--aws-gray-50)" }}>
      <div style={{ backgroundColor: "var(--aws-blue)" }} className="text-white py-8">
        <div className="max-w-7xl mx-auto px-4">
          <h1 className="text-3xl font-bold">Speech 合成</h1>
          <p className="text-gray-300">将文本快速转换为语音，可与视频生成联动</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="aws-card p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">文本</label>
            <textarea
              className="aws-input w-full"
              rows={6}
              placeholder="输入要合成的文本"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">提供商</label>
              <select className="aws-input w-full" value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="minimax">Minimax</option>
                <option value="azure">Azure Speech</option>
                <option value="openai">OpenAI</option>
                <option value="google">Google TTS</option>
                <option value="dashscope">DashScope(通义)</option>
                <option value="kimi">Kimi(直通)</option>
                <option value="grok">Grok(直通)</option>
                <option value="tiangong">天工(直通)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">音色</label>
              <select className="aws-input w-full" value={voice} onChange={(e) => setVoice(e.target.value)}>
                <option value="male_001">男声1</option>
                <option value="female_001">女声1</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">格式</label>
              <select className="aws-input w-full" value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="mp3">mp3</option>
                <option value="wav">wav</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">语速</label>
              <input className="aws-input w-full" type="number" value={speed as any} onChange={(e) => setSpeed(e.target.value ? Number(e.target.value) : "")} placeholder="1.0" step="0.1" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">音调</label>
              <input className="aws-input w-full" type="number" value={pitch as any} onChange={(e) => setPitch(e.target.value ? Number(e.target.value) : "")} placeholder="0.0" step="0.1" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={clean} onChange={(e) => setClean(e.target.checked)} />
              启用清洗（去除备案/版权/导航等噪声）
            </label>
            <button onClick={handleGenerate} disabled={loading || !text.trim()} className={`aws-btn-primary ${loading ? "opacity-50 cursor-not-allowed" : ""}`}>
              {loading ? "合成中..." : "开始合成"}
            </button>
          </div>

          {audioUrl && (
            <div className="mt-4 space-y-2">
              <audio ref={audioRef} controls src={audioUrl} className="w-full" />
              <a className="text-blue-600 hover:text-blue-800 text-sm" href={audioUrl} download>
                下载音频
              </a>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
