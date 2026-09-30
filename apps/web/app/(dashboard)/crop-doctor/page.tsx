"use client";

import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Camera, Upload, Loader2 } from "lucide-react";
import { useFarms } from "@/lib/farm-context";
import { api, ApiError } from "@/lib/api";
import { DiseaseAnalysisResult } from "@/lib/types";
import { FarmSelector } from "@/components/FarmSelector";
import { DiseaseResult } from "@/components/DiseaseResult";
import { EmptyState } from "@/components/EmptyState";
import { formatRelativeTime, titleCase } from "@/lib/format";

const MAX_SIZE_MB = 8;

export default function CropDoctorPage() {
  const { farms, selectedFarmId, selectFarm, isLoading: farmsLoading } = useFarms();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [crop, setCrop] = useState("");
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiseaseAnalysisResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ["disease-history", selectedFarmId],
    queryFn: () => api.get<{ id: string; possible_disease: string; confidence: number; severity: string; created_at: string }[]>(
      `/api/v1/disease/history/${selectedFarmId}`
    ),
    enabled: !!selectedFarmId,
  });

  const onFileChange = (f: File | null) => {
    setError(null);
    setResult(null);
    if (!f) {
      setFile(null);
      setPreview(null);
      return;
    }
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) {
      setError("Please upload a JPEG, PNG, or WEBP image.");
      return;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Image must be smaller than ${MAX_SIZE_MB}MB.`);
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const submit = async () => {
    if (!file || !selectedFarmId) return;
    setStatus("uploading");
    setError(null);
    try {
      const form = new FormData();
      form.append("farm_id", selectedFarmId);
      if (crop) form.append("crop", crop);
      form.append("image", file);
      const res = await api.post<DiseaseAnalysisResult>("/api/v1/disease/analyze", form);
      setResult(res);
      refetchHistory();
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Analysis failed. Please try again.");
    }
  };

  if (farmsLoading) return null;
  if (farms.length === 0) return <EmptyState title="No farms yet" description="Add a farm before using Crop Doctor." />;

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-page-title text-text-primary">Crop Doctor</h1>
          <p className="text-sm text-text-secondary">Upload a photo of the affected leaf or plant for a possible-disease assessment.</p>
        </div>
        <FarmSelector farms={farms} selectedId={selectedFarmId} onSelect={selectFarm} />
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="rounded-card border border-border bg-surface p-5 shadow-subtle">
          <label
            htmlFor="crop-image-input"
            className="flex h-56 cursor-pointer flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-border bg-background text-text-muted transition hover:border-primary"
          >
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="Selected crop preview" className="h-full w-full rounded-card object-cover" />
            ) : (
              <>
                <Upload size={28} aria-hidden="true" />
                <span className="text-sm">Click to upload or take a photo</span>
                <span className="text-xs">JPEG, PNG, or WEBP &middot; up to {MAX_SIZE_MB}MB</span>
              </>
            )}
          </label>
          <input
            ref={inputRef}
            id="crop-image-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            className="hidden"
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          />

          <div className="mt-4 space-y-3">
            <label className="block text-xs font-medium text-text-secondary">
              Crop (optional)
              <input value={crop} onChange={(e) => setCrop(e.target.value)} placeholder="e.g. rice" className="input mt-1" />
            </label>
            {error && (
              <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-xs text-danger">
                {error}
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-text-primary hover:bg-background"
              >
                <Camera size={14} aria-hidden="true" /> Choose photo
              </button>
              <button
                type="button"
                disabled={!file || status === "uploading"}
                onClick={submit}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-deep disabled:opacity-50"
              >
                {status === "uploading" ? (
                  <>
                    <Loader2 size={14} className="animate-spin" aria-hidden="true" /> Analyzing…
                  </>
                ) : (
                  "Analyze crop"
                )}
              </button>
            </div>
          </div>
        </div>

        <div>
          {result ? (
            <DiseaseResult result={result} />
          ) : (
            <EmptyState title="No analysis yet" description="Upload a photo and click Analyze crop to see BHOOMI's assessment here." />
          )}
        </div>
      </div>

      <section>
        <h2 className="mb-2 text-section-title text-text-primary">Scan history</h2>
        <div className="rounded-card border border-border bg-surface shadow-subtle">
          {(!history || history.length === 0) && <p className="px-4 py-4 text-sm text-text-muted">No previous scans for this farm.</p>}
          {history?.map((h, i) => (
            <div key={h.id} className={`flex items-center justify-between px-4 py-3 text-sm ${i > 0 ? "border-t border-border" : ""}`}>
              <span className="text-text-primary">{titleCase(h.possible_disease)}</span>
              <span className="text-xs text-text-muted">
                {Math.round(h.confidence * 100)}% &middot; {formatRelativeTime(h.created_at)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
