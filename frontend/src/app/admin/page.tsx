"use client";

import React from "react";
import { useRouter } from "next/navigation";
import IntelligenceAuditDashboard from "@/components/IntelligenceAuditDashboard";

export default function AdminAuditPage() {
  const router = useRouter();
  return (
    <div style={{ display: "flex", height: "100dvh", width: "100vw", overflow: "hidden" }}>
      <IntelligenceAuditDashboard onBackToChat={() => router.push("/")} />
    </div>
  );
}
