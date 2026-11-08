"use client";

import { useState, useCallback, useRef } from "react";
import { apiFetch, userFacingError } from "@/lib/network";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export function useVoice(onTranscript: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", blob, "audio.webm");

        try {
          const res = await apiFetch(`${API_BASE}/api/voice`, {
            method: "POST",
            body: formData,
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || res.statusText || "Transcription failed");
          }
          const data = await res.json();
          setError(null);
          onTranscript(data.text || "");
        } catch (e) {
          setError(userFacingError(e, "Voice transcription failed"));
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
      setError(null);
    } catch (e) {
      setError("Microphone access denied");
    }
  }, [onTranscript]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  }, []);

  return { recording, error, startRecording, stopRecording };
}
