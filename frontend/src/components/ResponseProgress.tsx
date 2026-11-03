"use client";

import { useEffect, useState } from "react";

const THINKING_ROTATIONS: Record<string, string[]> = {
  "Menelaah pertanyaan…": [
    "Menelaah pertanyaan…",
    "Menelusuri regulasi & dokumen sumber…",
    "Memeriksa ketentuan pajak DKI Jakarta…",
  ],
  "Menghubungi model lokal…": [
    "Menelaah pertanyaan…",
    "Menelusuri regulasi & dokumen sumber…",
    "Memeriksa ketentuan pajak DKI Jakarta…",
  ],
  "Mencari sumber…": [
    "Mencari sumber regulasi…",
    "Menelusuri kutipan dokumen terkait…",
    "Memeriksa kecocokan pasal & data…",
  ],
  "Menyusun jawaban…": [
    "Menyusun jawaban…",
    "Memverifikasi rujukan & dasar hukum…",
    "Merangkum poin-poin utama…",
  ],
};

export default function ResponseProgress({
  text,
}: {
  messageId?: string;
  text: string;
}) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    setStepIndex(0);
  }, [text]);

  useEffect(() => {
    const variants = THINKING_ROTATIONS[text];
    if (!variants || variants.length <= 1) return;
    const rotate = window.setInterval(() => {
      setStepIndex((prev) => (prev + 1) % variants.length);
    }, 3200);
    return () => window.clearInterval(rotate);
  }, [text]);

  const variants = THINKING_ROTATIONS[text];
  const displayLabel = variants ? variants[stepIndex % variants.length] : text;

  return (
    <div className="jst-response-progress">
      <span key={displayLabel} className="jst-response-stage shimmer-status" role="status">
        {displayLabel}
      </span>
    </div>
  );
}
