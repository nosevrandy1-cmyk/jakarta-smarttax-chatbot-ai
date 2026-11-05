"use client";

export default function ResponseProgress({ text }: { messageId?: string; text: string }) {
  return (
    <div className="jst-response-progress">
      <span className="jst-response-stage shimmer-status" role="status">{text}</span>
    </div>
  );
}
