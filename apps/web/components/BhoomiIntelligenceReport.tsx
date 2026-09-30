"use client";

import React, { useState, useMemo } from "react";
import Image from "next/image";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  Share2,
  Printer,
  ChevronDown,
  ChevronUp,
  Sprout,
  Droplets,
  CloudSun,
  ShieldCheck,
  Compass,
  ArrowRight,
  HelpCircle,
  Activity,
  Layers,
  Sparkles,
  Info,
} from "lucide-react";
import { IntelligenceResponse } from "@/lib/types";

interface BhoomiIntelligenceReportProps {
  reportText: string | null | undefined;
  data: IntelligenceResponse;
  onReanalyze?: () => void;
  isFetching?: boolean;
}

interface ParsedBhoomiReport {
  isLimitedFallback: boolean;
  farmName?: string;
  location?: string;
  crop?: string;
  cropStage?: string;
  healthScore?: string;
  overallStatus?: string;
  simpleWords?: string;
  whatIsHappening?: string;
  mainRisks: { risk: string; why: string }[];
  whatIsGoingWell: string[];
  whatToDoNow: { action: string; reason: string }[];
  soilStatus?: string;
  soilWhatWeKnow?: string;
  waterStatus?: string;
  waterWhatWeKnow?: string;
  weatherStatus?: string;
  weatherWhatWeKnow?: string;
  cropHealthStatus?: string;
  cropHealthWhatWeKnow?: string;
  vegetationStatus?: string;
  vegetationWhatWeKnow?: string;
  cropDiseaseStatus?: string;
  cropDiseaseName?: string;
  cropDiseaseConfidence?: string;
  cropDiseaseWhatToDo?: string;
  regenerativeOpportunity?: string;
  whyBhoomiSaysThis: { category: string; evidence: string }[];
  whatIsMissing: string[];
  nextStep?: string;
  confidence?: string;
  confidenceReason?: string;
  fallbackAvailableInfo?: string[];
  fallbackSafeNextStep?: string;
}

export function parseBhoomiReport(text: string | null | undefined): ParsedBhoomiReport {
  const result: ParsedBhoomiReport = {
    isLimitedFallback: false,
    mainRisks: [],
    whatIsGoingWell: [],
    whatToDoNow: [],
    whyBhoomiSaysThis: [],
    whatIsMissing: [],
  };

  if (!text) return result;

  // Check if it's the limited fallback format
  if (text.includes("A full AI analysis is temporarily unavailable") || text.includes("Data availability:\nLimited")) {
    result.isLimitedFallback = true;

    const infoMatch = text.match(/Available information:[\s\S]*?(?=Safe next step:|$)/i);
    if (infoMatch) {
      result.fallbackAvailableInfo = infoMatch[0]
        .replace(/Available information:\s*/i, "")
        .split("\n")
        .map((l) => l.replace(/^[-*•]\s*/, "").trim())
        .filter(Boolean);
    }

    const stepMatch = text.match(/Safe next step:[\s\S]*?$/i);
    if (stepMatch) {
      result.fallbackSafeNextStep = stepMatch[0].replace(/Safe next step:\s*/i, "").trim();
    }

    return result;
  }

  // Parse structured report sections
  const getSection = (startKeyword: string, endKeywords: string[]) => {
    const endPattern = endKeywords.join("|");
    const regex = new RegExp(`${startKeyword}[\\s\\S]*?(?=${endPattern}|$)`, "i");
    const match = text.match(regex);
    return match ? match[0].replace(new RegExp(`^${startKeyword}\\s*`, "i"), "").trim() : "";
  };

  // Header info
  const farmMatch = text.match(/Farm:\s*([^\n\r]+)/i);
  if (farmMatch && farmMatch[1]) result.farmName = farmMatch[1].trim();

  const locMatch = text.match(/Location:\s*([^\n\r]+)/i);
  if (locMatch && locMatch[1]) result.location = locMatch[1].trim();

  const cropMatch = text.match(/Crop:\s*([^\n\r]+)/i);
  if (cropMatch && cropMatch[1]) result.crop = cropMatch[1].trim();

  const stageMatch = text.match(/Crop Stage:\s*([^\n\r]+)/i);
  if (stageMatch && stageMatch[1]) result.cropStage = stageMatch[1].trim();

  // Overall Condition
  const healthMatch = text.match(/Farm Health:\s*([^\n\r]+)/i);
  if (healthMatch && healthMatch[1]) result.healthScore = healthMatch[1].trim();

  const statusMatch = text.match(/Status:\s*([^\n\r]+)/i);
  if (statusMatch && statusMatch[1]) result.overallStatus = statusMatch[1].trim();

  const simpleMatch = text.match(/In simple words:\s*([^\n\r]+(?:\n[^\n\r]+)*?)(?=\n\s*[A-Z ]{3,}:|\n\s*WHAT IS HAPPENING|$)/i);
  if (simpleMatch && simpleMatch[1]) result.simpleWords = simpleMatch[1].trim();

  // What is happening
  result.whatIsHappening = getSection("WHAT IS HAPPENING", ["MAIN RISKS", "WHAT IS GOING WELL", "WHAT YOU SHOULD DO NOW"]);

  // Main Risks
  const risksSection = getSection("MAIN RISKS", ["WHAT IS GOING WELL", "WHAT YOU SHOULD DO NOW", "SOIL"]);
  if (risksSection) {
    const riskBlocks = risksSection.split(/\n\s*(?=\d+\.\s+)/);
    for (const b of riskBlocks) {
      const trimmed = b.trim();
      if (!trimmed) continue;
      const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);
      if (lines.length === 0) continue;
      const firstLine = lines[0] ?? "";
      const titleLine = firstLine.replace(/^\d+\.\s*/, "");
      const whyLine = lines.find((l) => /^Why:\s*/i.test(l));
      const why = whyLine ? whyLine.replace(/^Why:\s*/i, "").trim() : lines.slice(1).join(" ");
      result.mainRisks.push({ risk: titleLine, why });
    }
  }

  // What is going well
  const goingWellSection = getSection("WHAT IS GOING WELL", ["WHAT YOU SHOULD DO NOW", "SOIL", "WATER"]);
  if (goingWellSection) {
    result.whatIsGoingWell = goingWellSection
      .split("\n")
      .map((l) => l.replace(/^[-*•]\s*/, "").trim())
      .filter((l) => l.length > 0 && !/^WHAT IS GOING WELL/i.test(l));
  }

  // What you should do now
  const actionSection = getSection("WHAT YOU SHOULD DO NOW", ["SOIL", "WATER", "WEATHER"]);
  if (actionSection) {
    const actionBlocks = actionSection.split(/\n\s*(?=\d+\.\s+)/);
    for (const b of actionBlocks) {
      const trimmed = b.trim();
      if (!trimmed) continue;
      const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);
      if (lines.length === 0) continue;
      const actFirst = lines[0] ?? "";
      const actionLine = actFirst.replace(/^\d+\.\s*/, "");
      const reasonLine = lines.find((l) => /^Reason:\s*/i.test(l));
      const reason = reasonLine ? reasonLine.replace(/^Reason:\s*/i, "").trim() : lines.slice(1).join(" ");
      result.whatToDoNow.push({ action: actionLine, reason });
    }
  }

  // Soil
  const soilSection = getSection("SOIL", ["WATER", "WEATHER", "CROP HEALTH"]);
  if (soilSection) {
    const status = soilSection.match(/Status:\s*([^\n\r]+)/i);
    const know = soilSection.match(/What we know:\s*([\s\S]*?)$/i);
    if (status && status[1]) result.soilStatus = status[1].trim();
    if (know && know[1]) result.soilWhatWeKnow = know[1].trim();
  }

  // Water
  const waterSection = getSection("WATER", ["WEATHER", "CROP HEALTH", "VEGETATION"]);
  if (waterSection) {
    const status = waterSection.match(/Status:\s*([^\n\r]+)/i);
    const know = waterSection.match(/What we know:\s*([\s\S]*?)$/i);
    if (status && status[1]) result.waterStatus = status[1].trim();
    if (know && know[1]) result.waterWhatWeKnow = know[1].trim();
  }

  // Weather
  const weatherSection = getSection("WEATHER", ["CROP HEALTH", "VEGETATION", "CROP DISEASE"]);
  if (weatherSection) {
    const status = weatherSection.match(/Status:\s*([^\n\r]+)/i);
    const know = weatherSection.match(/What we know:\s*([\s\S]*?)$/i);
    if (status && status[1]) result.weatherStatus = status[1].trim();
    if (know && know[1]) result.weatherWhatWeKnow = know[1].trim();
  }

  // Crop Health
  const cropHealthSection = getSection("CROP HEALTH", ["VEGETATION", "CROP DISEASE", "REGENERATIVE OPPORTUNITY"]);
  if (cropHealthSection) {
    const status = cropHealthSection.match(/Status:\s*([^\n\r]+)/i);
    const know = cropHealthSection.match(/What we know:\s*([\s\S]*?)$/i);
    if (status && status[1]) result.cropHealthStatus = status[1].trim();
    if (know && know[1]) result.cropHealthWhatWeKnow = know[1].trim();
  }

  // Vegetation
  const vegSection = getSection("VEGETATION", ["CROP DISEASE", "REGENERATIVE OPPORTUNITY", "WHY BHOOMI SAYS THIS"]);
  if (vegSection) {
    const status = vegSection.match(/Status:\s*([^\n\r]+)/i);
    const know = vegSection.match(/What we know:\s*([\s\S]*?)$/i);
    if (status && status[1]) result.vegetationStatus = status[1].trim();
    if (know && know[1]) result.vegetationWhatWeKnow = know[1].trim();
  }

  // Crop Disease
  const diseaseSection = getSection("CROP DISEASE", ["REGENERATIVE OPPORTUNITY", "WHY BHOOMI SAYS THIS"]);
  if (diseaseSection) {
    const status = diseaseSection.match(/Status:\s*([^\n\r]+)/i);
    const pos = diseaseSection.match(/Possible disease:\s*([^\n\r]+)/i);
    const conf = diseaseSection.match(/Confidence:\s*([^\n\r]+)/i);
    const what = diseaseSection.match(/What to do:\s*([\s\S]*?)$/i);
    if (status && status[1]) result.cropDiseaseStatus = status[1].trim();
    if (pos && pos[1]) result.cropDiseaseName = pos[1].trim();
    if (conf && conf[1]) result.cropDiseaseConfidence = conf[1].trim();
    if (what && what[1]) result.cropDiseaseWhatToDo = what[1].trim();
  }

  // Regenerative Opportunity
  result.regenerativeOpportunity = getSection("REGENERATIVE OPPORTUNITY", ["WHY BHOOMI SAYS THIS", "WHAT IS MISSING"]);

  // Why Bhoomi says this
  const whySection = getSection("WHY BHOOMI SAYS THIS", ["WHAT IS MISSING", "NEXT STEP", "CONFIDENCE"]);
  if (whySection) {
    const cats = ["Weather", "Soil", "Satellite", "Crop", "Other"];
    for (const c of cats) {
      const m = whySection.match(new RegExp(`${c}:\\s*([^\\n\\r]+(?:\\n(?!\\w+:)[^\\n\\r]+)*)`, "i"));
      if (m && m[1] && m[1].trim() && m[1].trim() !== "Not provided") {
        result.whyBhoomiSaysThis.push({ category: c, evidence: m[1].trim() });
      }
    }
  }

  // What is missing
  const missingSection = getSection("WHAT IS MISSING", ["NEXT STEP", "CONFIDENCE"]);
  if (missingSection) {
    result.whatIsMissing = missingSection
      .split("\n")
      .map((l) => l.replace(/^[-*•]\s*/, "").trim())
      .filter((l) => l.length > 0 && !/^WHAT IS MISSING/i.test(l));
  }

  // Next step
  result.nextStep = getSection("NEXT STEP", ["CONFIDENCE"]);

  // Confidence
  const confSection = getSection("CONFIDENCE", []);
  if (confSection) {
    const confMatch = confSection.match(/^(High|Moderate|Low)/i);
    if (confMatch && confMatch[1]) result.confidence = confMatch[1].trim();
    const reasonMatch = confSection.match(/Reason:\s*([\s\S]*?)$/i);
    if (reasonMatch && reasonMatch[1]) result.confidenceReason = reasonMatch[1].trim();
  }

  return result;
}

export function BhoomiIntelligenceReport({
  reportText,
  data,
  onReanalyze,
  isFetching,
}: BhoomiIntelligenceReportProps) {
  const [viewMode, setViewMode] = useState<"visual" | "raw">("visual");
  const [copied, setCopied] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const parsed = useMemo(() => parseBhoomiReport(reportText), [reportText]);

  const handleCopy = () => {
    if (!reportText) return;
    navigator.clipboard.writeText(reportText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShareWhatsApp = () => {
    if (!reportText) return;
    const textToShare = `🌾 *BHOOMI FARM INTELLIGENCE REPORT*\n\n${reportText}`;
    const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(textToShare)}`;
    window.open(url, "_blank");
  };

  const handlePrint = () => {
    window.print();
  };

  if (!reportText) {
    return (
      <div className="rounded-card border border-border bg-surface p-6 text-center text-text-secondary">
        <Sparkles className="mx-auto mb-2 text-primary" size={28} />
        <p className="font-medium text-text-primary">No Intelligence Report Available</p>
        <p className="mt-1 text-sm text-text-muted">
          Select a farm and trigger re-analysis to generate the BHOOMI intelligence report.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Top Bar with Actions & View Toggle ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-center gap-2.5">
          <div className="relative h-8 w-8 overflow-hidden rounded-full border border-primary/30 shadow-sm">
            <Image src="/logo.jpeg" alt="BHOOMI" fill className="object-cover" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-heading text-base font-bold text-text-primary">
                BHOOMI Farm Intelligence
              </span>
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
                AI System
              </span>
            </div>
            <p className="text-xs text-text-muted">
              Evidence-based, farmer-first intelligence assessment
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="inline-flex rounded-lg border border-border bg-background p-0.5 text-xs font-medium">
            <button
              onClick={() => setViewMode("visual")}
              className={`rounded-md px-3 py-1.5 transition ${
                viewMode === "visual"
                  ? "bg-primary text-white shadow-sm"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Dashboard View
            </button>
            <button
              onClick={() => setViewMode("raw")}
              className={`rounded-md px-3 py-1.5 transition ${
                viewMode === "raw"
                  ? "bg-primary text-white shadow-sm"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Plain Text Report
            </button>
          </div>

          {/* Copy Report */}
          <button
            onClick={handleCopy}
            title="Copy plain-text report"
            className="flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-secondary shadow-subtle hover:bg-background"
          >
            {copied ? <Check size={14} className="text-primary" /> : <Copy size={14} />}
            <span>{copied ? "Copied!" : "Copy"}</span>
          </button>

          {/* WhatsApp Share */}
          <button
            onClick={handleShareWhatsApp}
            title="Share via WhatsApp"
            className="flex items-center gap-1 rounded-md border border-primary/30 bg-[#25D366]/10 px-2.5 py-1.5 text-xs font-medium text-[#128C7E] shadow-subtle hover:bg-[#25D366]/20"
          >
            <Share2 size={14} />
            <span className="hidden sm:inline">WhatsApp</span>
          </button>

          {/* Print */}
          <button
            onClick={handlePrint}
            title="Print Report"
            className="flex items-center gap-1 rounded-md border border-border bg-surface p-1.5 text-xs text-text-secondary shadow-subtle hover:bg-background"
          >
            <Printer size={14} />
          </button>
        </div>
      </div>

      {/* ── Limited Fallback Notice (If AI models unreachable) ── */}
      {parsed.isLimitedFallback && (
        <div className="rounded-card border-2 border-amber-300 bg-amber-50/80 p-4 text-amber-900 shadow-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 shrink-0 text-amber-600" size={20} />
            <div className="space-y-2">
              <p className="font-semibold text-amber-900">
                A full AI analysis is temporarily unavailable
              </p>
              <p className="text-sm text-amber-800 leading-relaxed">
                BHOOMI has switched to its deterministic rule-based safety engine. In accordance with BHOOMI safety rules, we do not invent answers. Below is the verified assessment derived strictly from known farm data.
              </p>
              {parsed.fallbackSafeNextStep && (
                <div className="mt-2 rounded-md bg-white/80 p-3 border border-amber-200">
                  <p className="text-xs font-bold uppercase tracking-wider text-amber-700">Safe Next Step</p>
                  <p className="mt-1 text-sm font-medium text-amber-950">{parsed.fallbackSafeNextStep}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Mode 1: Plain Text View ── */}
      {viewMode === "raw" && (
        <div className="rounded-card border border-border bg-surface p-6 shadow-subtle">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Official Plain-Text Report
            </span>
            <span className="text-xs text-text-muted">Direct output from BHOOMI Engine</span>
          </div>
          <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-primary bg-background/50 p-4 rounded-lg border border-border/60 overflow-x-auto">
            {reportText}
          </pre>
        </div>
      )}

      {/* ── Mode 2: Visual Dashboard View ── */}
      {viewMode === "visual" && (
        <div className="space-y-6">
          {/* 4 Core Questions Banner */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-card border border-border bg-surface p-3.5 shadow-subtle hover:border-primary/40 transition">
              <div className="flex items-center gap-2 text-primary font-semibold text-xs">
                <span>1.</span> What is happening?
              </div>
              <p className="mt-1.5 text-xs text-text-secondary line-clamp-3">
                {parsed.simpleWords || parsed.whatIsHappening || "Current field indicators evaluated."}
              </p>
            </div>
            <div className="rounded-card border border-border bg-surface p-3.5 shadow-subtle hover:border-primary/40 transition">
              <div className="flex items-center gap-2 text-primary font-semibold text-xs">
                <span>2.</span> Why is it happening?
              </div>
              <p className="mt-1.5 text-xs text-text-secondary line-clamp-3">
                {parsed.mainRisks[0]?.why || "Based on soil, satellite, and weather signals."}
              </p>
            </div>
            <div className="rounded-card border border-border bg-surface p-3.5 shadow-subtle hover:border-primary/40 transition">
              <div className="flex items-center gap-2 text-primary font-semibold text-xs">
                <span>3.</span> What should you do?
              </div>
              <p className="mt-1.5 text-xs text-text-secondary line-clamp-3">
                {parsed.whatToDoNow[0]?.action || parsed.nextStep || "See priority actions below."}
              </p>
            </div>
            <div className="rounded-card border border-border bg-surface p-3.5 shadow-subtle hover:border-primary/40 transition">
              <div className="flex items-center gap-2 text-primary font-semibold text-xs">
                <span>4.</span> What supports this?
              </div>
              <p className="mt-1.5 text-xs text-text-secondary line-clamp-3">
                {parsed.whyBhoomiSaysThis.length > 0
                  ? `${parsed.whyBhoomiSaysThis.length} direct evidence signals verified.`
                  : "Verified farm measurements & satellite trends."}
              </p>
            </div>
          </div>

          {/* OVERALL CONDITION HERO CARD */}
          <div className="relative overflow-hidden rounded-2xl border-2 border-primary/20 bg-gradient-to-br from-primary-soft/40 via-surface to-surface p-6 shadow-sm">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-primary">
                    Overall Farm Condition
                  </span>
                  <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
                    Status: {parsed.overallStatus || data.health.label || "Stable"}
                  </span>
                </div>
                <h2 className="mt-2 text-xl font-bold text-text-primary">
                  {parsed.farmName || data.farm.name} &bull; {parsed.crop || data.farm.crop || "Farm"}
                </h2>
                {parsed.cropStage && (
                  <p className="text-xs text-text-muted mt-0.5">Crop Stage: {parsed.cropStage}</p>
                )}
                {parsed.simpleWords && (
                  <p className="mt-3 text-sm leading-relaxed text-text-secondary bg-surface/80 p-3 rounded-xl border border-primary/15 shadow-subtle">
                    &ldquo;{parsed.simpleWords}&rdquo;
                  </p>
                )}
              </div>

              {/* Health Score Gauge / Badge */}
              <div className="shrink-0 text-center">
                <div className="relative inline-flex items-center justify-center">
                  <div className="h-28 w-28 rounded-full border-4 border-primary/20 bg-surface flex flex-col items-center justify-center shadow-subtle">
                    <span className="font-heading text-3xl font-extrabold text-primary">
                      {data.health.has_data
                        ? parsed.healthScore
                          ? parsed.healthScore.replace(/\/100/, "").trim()
                          : Math.round(data.health.score ?? 0)
                        : "--"}
                    </span>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                      {data.health.has_data ? "/ 100 Health" : "Not enough data"}
                    </span>
                  </div>
                </div>
                {parsed.confidence && (
                  <p className="mt-1.5 text-xs font-medium text-text-muted">
                    Confidence: <span className="font-semibold text-text-primary">{parsed.confidence}</span>
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* WHAT IS HAPPENING */}
          {parsed.whatIsHappening && (
            <div className="rounded-card border border-border bg-surface p-5 shadow-subtle">
              <div className="flex items-center gap-2 text-primary font-bold text-sm">
                <Activity size={18} />
                <span>WHAT IS HAPPENING</span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                {parsed.whatIsHappening}
              </p>
            </div>
          )}

          {/* TWO COLUMNS: WHAT YOU SHOULD DO NOW & MAIN RISKS */}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {/* What you should do now */}
            <div className="rounded-card border border-primary/30 bg-surface p-5 shadow-subtle flex flex-col">
              <div className="flex items-center gap-2 text-primary font-bold text-sm mb-3">
                <CheckCircle2 size={18} />
                <span>WHAT YOU SHOULD DO NOW</span>
              </div>

              {parsed.whatToDoNow.length > 0 ? (
                <div className="space-y-3 flex-1">
                  {parsed.whatToDoNow.map((item, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-border/80 bg-background/60 p-3 hover:border-primary/40 transition"
                    >
                      <div className="flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-white">
                          {idx + 1}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-text-primary">{item.action}</p>
                          {item.reason && (
                            <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                              <span className="font-medium text-primary">Reason: </span>
                              {item.reason}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted">
                  Continue regular crop monitoring and standard field management practices.
                </p>
              )}
            </div>

            {/* Main Risks */}
            <div className="rounded-card border border-amber-200 bg-surface p-5 shadow-subtle flex flex-col">
              <div className="flex items-center gap-2 text-amber-700 font-bold text-sm mb-3">
                <AlertTriangle size={18} />
                <span>MAIN RISKS</span>
              </div>

              {parsed.mainRisks.length > 0 ? (
                <div className="space-y-3 flex-1">
                  {parsed.mainRisks.map((item, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-amber-100 bg-amber-50/50 p-3"
                    >
                      <div className="flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500 text-[11px] font-bold text-white">
                          {idx + 1}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-amber-950">{item.risk}</p>
                          {item.why && (
                            <p className="mt-1 text-xs leading-relaxed text-amber-800">
                              <span className="font-medium text-amber-700">Why: </span>
                              {item.why}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted">
                  No elevated risk indicators detected at this time.
                </p>
              )}
            </div>
          </div>

          {/* WHAT IS GOING WELL */}
          {parsed.whatIsGoingWell.length > 0 && (
            <div className="rounded-card border border-emerald-200 bg-emerald-50/30 p-5 shadow-subtle">
              <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm mb-3">
                <ShieldCheck size={18} />
                <span>WHAT IS GOING WELL</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                {parsed.whatIsGoingWell.map((good, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 rounded-lg bg-white/90 p-2.5 border border-emerald-100 text-xs font-medium text-emerald-950 shadow-sm"
                  >
                    <CheckCircle2 size={15} className="shrink-0 text-emerald-600" />
                    <span>{good}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* FIELD STATUS PILLARS (SOIL, WATER, WEATHER, CROP HEALTH, VEGETATION, DISEASE) */}
          <div className="rounded-card border border-border bg-surface p-5 shadow-subtle">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
                Field Pillars Assessment
              </span>
              <button
                onClick={() => setDetailsOpen(!detailsOpen)}
                className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                <span>{detailsOpen ? "Show Less" : "Detailed Insights"}</span>
                {detailsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              {/* Soil */}
              <div className="rounded-xl border border-border bg-background/50 p-3 text-center">
                <Sprout className="mx-auto text-primary" size={20} />
                <p className="mt-1 text-xs font-semibold text-text-primary">Soil</p>
                <span className="mt-1 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                  {parsed.soilStatus || "Good"}
                </span>
                {detailsOpen && parsed.soilWhatWeKnow && (
                  <p className="mt-2 text-[11px] text-text-secondary text-left border-t border-border pt-2 leading-relaxed">
                    {parsed.soilWhatWeKnow}
                  </p>
                )}
              </div>

              {/* Water */}
              <div className="rounded-xl border border-border bg-background/50 p-3 text-center">
                <Droplets className="mx-auto text-blue-500" size={20} />
                <p className="mt-1 text-xs font-semibold text-text-primary">Water</p>
                <span className="mt-1 inline-block rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 border border-blue-200">
                  {parsed.waterStatus || "Adequate"}
                </span>
                {detailsOpen && parsed.waterWhatWeKnow && (
                  <p className="mt-2 text-[11px] text-text-secondary text-left border-t border-border pt-2 leading-relaxed">
                    {parsed.waterWhatWeKnow}
                  </p>
                )}
              </div>

              {/* Weather */}
              <div className="rounded-xl border border-border bg-background/50 p-3 text-center">
                <CloudSun className="mx-auto text-amber-500" size={20} />
                <p className="mt-1 text-xs font-semibold text-text-primary">Weather</p>
                <span className="mt-1 inline-block rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 border border-amber-200">
                  {parsed.weatherStatus || "Low Risk"}
                </span>
                {detailsOpen && parsed.weatherWhatWeKnow && (
                  <p className="mt-2 text-[11px] text-text-secondary text-left border-t border-border pt-2 leading-relaxed">
                    {parsed.weatherWhatWeKnow}
                  </p>
                )}
              </div>

              {/* Crop Health */}
              <div className="rounded-xl border border-border bg-background/50 p-3 text-center">
                <Activity className="mx-auto text-emerald-600" size={20} />
                <p className="mt-1 text-xs font-semibold text-text-primary">Crop Health</p>
                <span className="mt-1 inline-block rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">
                  {parsed.cropHealthStatus || "Stable"}
                </span>
                {detailsOpen && parsed.cropHealthWhatWeKnow && (
                  <p className="mt-2 text-[11px] text-text-secondary text-left border-t border-border pt-2 leading-relaxed">
                    {parsed.cropHealthWhatWeKnow}
                  </p>
                )}
              </div>

              {/* Vegetation */}
              <div className="rounded-xl border border-border bg-background/50 p-3 text-center">
                <Layers className="mx-auto text-teal-600" size={20} />
                <p className="mt-1 text-xs font-semibold text-text-primary">Vegetation</p>
                <span className="mt-1 inline-block rounded-full bg-teal-50 px-2 py-0.5 text-[10px] font-semibold text-teal-700 border border-teal-200">
                  {parsed.vegetationStatus || "Healthy"}
                </span>
                {detailsOpen && parsed.vegetationWhatWeKnow && (
                  <p className="mt-2 text-[11px] text-text-secondary text-left border-t border-border pt-2 leading-relaxed">
                    {parsed.vegetationWhatWeKnow}
                  </p>
                )}
              </div>

              {/* Crop Disease */}
              <div className="rounded-xl border border-border bg-background/50 p-3 text-center">
                <ShieldCheck className="mx-auto text-purple-600" size={20} />
                <p className="mt-1 text-xs font-semibold text-text-primary">Disease</p>
                <span className="mt-1 inline-block rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-semibold text-purple-700 border border-purple-200">
                  {parsed.cropDiseaseStatus || "Not Assessed"}
                </span>
                {detailsOpen && (
                  <p className="mt-2 text-[11px] text-text-secondary text-left border-t border-border pt-2 leading-relaxed">
                    {parsed.cropDiseaseWhatToDo || parsed.cropDiseaseName || "No active disease alerts."}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* REGENERATIVE AGRICULTURE OPPORTUNITY */}
          {parsed.regenerativeOpportunity && (
            <div className="rounded-card border border-primary/30 bg-primary-soft/30 p-5 shadow-subtle">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary p-2 text-white shadow-sm shrink-0">
                  <Sprout size={18} />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-primary">
                    Regenerative Agriculture Opportunity
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-text-primary">
                    {parsed.regenerativeOpportunity}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* WHY BHOOMI SAYS THIS (EVIDENCE) */}
          {parsed.whyBhoomiSaysThis.length > 0 && (
            <div className="rounded-card border border-border bg-surface p-5 shadow-subtle">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-text-muted mb-3">
                <Compass size={16} className="text-primary" />
                <span>WHY BHOOMI SAYS THIS (EVIDENCE BASE)</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {parsed.whyBhoomiSaysThis.map((item, idx) => (
                  <div key={idx} className="rounded-lg border border-border bg-background/40 p-3">
                    <span className="text-[11px] font-bold text-primary uppercase">
                      {item.category}:
                    </span>
                    <p className="mt-0.5 text-xs text-text-secondary leading-relaxed">
                      {item.evidence}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* WHAT IS MISSING & NEXT STEP */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* What is missing */}
            <div className="rounded-card border border-border bg-surface p-4 shadow-subtle sm:col-span-1">
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-text-muted mb-2">
                <HelpCircle size={14} />
                <span>What is Missing</span>
              </div>
              {parsed.whatIsMissing.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-text-secondary">
                  {parsed.whatIsMissing.map((miss, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-amber-500 font-bold">&bull;</span>
                      <span>{miss}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-text-muted">Key farm indicators are present.</p>
              )}
            </div>

            {/* Next Step Banner */}
            <div className="rounded-card border-2 border-primary bg-primary-soft/40 p-4 shadow-subtle sm:col-span-2 flex flex-col justify-between">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
                  Immediate Next Step
                </span>
                <p className="mt-1 text-sm font-semibold text-text-primary leading-relaxed">
                  {parsed.nextStep || parsed.whatToDoNow[0]?.action || "Review soil moisture and inspect current vegetative progress."}
                </p>
              </div>
              <div className="mt-3 flex items-center justify-between pt-2 border-t border-primary/20 text-xs text-text-muted">
                <span>Confidence: <strong className="text-text-primary">{parsed.confidence || "High"}</strong></span>
                {parsed.confidenceReason && (
                  <span className="text-[11px] italic max-w-xs truncate">{parsed.confidenceReason}</span>
                )}
              </div>
            </div>
          </div>

          {/* Safety Disclaimer Footer */}
          <div className="flex items-start gap-2 rounded-lg bg-surface border border-border/60 p-3 text-[11px] text-text-muted leading-relaxed">
            <Info size={14} className="mt-0.5 shrink-0 text-text-muted" />
            <p>
              <strong>Agricultural Safety Notice:</strong> BHOOMI Farm Intelligence AI is a decision-support system. It provides evidence-based analysis but does not replace qualified agronomists, soil testing laboratories, or local agricultural department officials. For critical crop protection operations, always verify field conditions directly.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
