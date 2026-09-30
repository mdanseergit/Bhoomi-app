"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, X, MapPin, Trash2 } from "lucide-react";
import { useFarms } from "@/lib/farm-context";
import { api, ApiError } from "@/lib/api";
import { Farm } from "@/lib/types";
import { FarmMapClient } from "@/components/FarmMapClient";
import { EmptyState } from "@/components/EmptyState";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import { titleCase } from "@/lib/format";

const schema = z.object({
  name: z.string().min(2, "Farm name is required"),
  state: z.string().min(2, "State is required"),
  district: z.string().min(2, "District is required"),
  taluk: z.string().optional(),
  village: z.string().optional(),
  latitude: z.coerce.number().min(-90).max(90),
  longitude: z.coerce.number().min(-180).max(180),
  area_hectares: z.coerce.number().positive("Area must be greater than 0"),
  soil_type: z.string().optional(),
  irrigation_type: z.string().optional(),
  water_source: z.string().optional(),
  current_crop: z.string().optional(),
  crop_variety: z.string().optional(),
  crop_stage: z.string().optional(),
  previous_crop: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function FarmsPage() {
  const { farms, isLoading, selectedFarmId, selectFarm, refetch } = useFarms();
  const [showForm, setShowForm] = useState(false);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-page-title text-text-primary">My Farms</h1>
          <p className="text-sm text-text-secondary">Manage farm locations, boundaries, and crop details.</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary-deep"
        >
          <Plus size={16} aria-hidden="true" /> Add farm
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="space-y-3">
          {isLoading && <CardSkeleton />}
          {!isLoading && farms.length === 0 && (
            <EmptyState title="No farms yet" description="Add your first farm to get started." />
          )}
          {farms.map((farm) => (
            <FarmListItem key={farm.id} farm={farm} active={farm.id === selectedFarmId} onSelect={() => selectFarm(farm.id)} onDeleted={refetch} />
          ))}
        </div>

        <div className="h-[420px] lg:h-auto">
          <FarmMapClient farms={farms} selectedFarmId={selectedFarmId} onSelect={selectFarm} />
        </div>
      </div>

      {showForm && <FarmFormPanel onClose={() => setShowForm(false)} onCreated={refetch} />}
    </div>
  );
}

function FarmListItem({ farm, active, onSelect, onDeleted }: { farm: Farm; active: boolean; onSelect: () => void; onDeleted: () => void }) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete ${farm.name}? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await api.delete(`/api/v1/farms/${farm.id}`);
      onDeleted();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <button
      onClick={onSelect}
      className={`w-full rounded-card border p-4 text-left shadow-subtle transition ${
        active ? "border-primary bg-primary-soft" : "border-border bg-surface hover:border-text-muted"
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-card-title text-text-primary">{farm.name}</p>
          <p className="flex items-center gap-1 text-xs text-text-secondary">
            <MapPin size={12} aria-hidden="true" /> {farm.district}, {farm.state}
          </p>
        </div>
        <button
          onClick={handleDelete}
          disabled={deleting}
          aria-label={`Delete ${farm.name}`}
          className="rounded p-1 text-text-muted hover:bg-red-50 hover:text-danger"
        >
          <Trash2 size={14} aria-hidden="true" />
        </button>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-secondary">
        <span className="rounded-full bg-background px-2 py-0.5">{farm.area_hectares} ha</span>
        {farm.current_crop && <span className="rounded-full bg-background px-2 py-0.5">{titleCase(farm.current_crop)}</span>}
        {farm.crop_stage && <span className="rounded-full bg-background px-2 py-0.5">{titleCase(farm.crop_stage)}</span>}
      </div>
    </button>
  );
}

function FarmFormPanel({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const lat = watch("latitude");
  const lng = watch("longitude");

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    setSubmitting(true);
    try {
      await api.post("/api/v1/farms", values);
      onCreated();
      onClose();
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Unable to create farm.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-card border border-border bg-surface p-6 shadow-subtle">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-section-title text-text-primary">Add a new farm</h2>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-background">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
          <Field label="Farm name" error={errors.name?.message}>
            <input className="input" {...register("name")} />
          </Field>
          <Field label="State" error={errors.state?.message}>
            <input className="input" {...register("state")} />
          </Field>
          <Field label="District" error={errors.district?.message}>
            <input className="input" {...register("district")} />
          </Field>
          <Field label="Taluk">
            <input className="input" {...register("taluk")} />
          </Field>
          <Field label="Village">
            <input className="input" {...register("village")} />
          </Field>
          <Field label="Area (hectares)" error={errors.area_hectares?.message}>
            <input type="number" step="0.01" className="input" {...register("area_hectares")} />
          </Field>
          <Field label="Latitude" error={errors.latitude?.message}>
            <input type="number" step="0.0001" className="input" {...register("latitude")} />
          </Field>
          <Field label="Longitude" error={errors.longitude?.message}>
            <input type="number" step="0.0001" className="input" {...register("longitude")} />
          </Field>
          <Field label="Irrigation type">
            <select className="input" {...register("irrigation_type")}>
              <option value="">Select</option>
              <option value="drip">Drip</option>
              <option value="sprinkler">Sprinkler</option>
              <option value="flood">Flood</option>
              <option value="canal">Canal</option>
              <option value="rainfed">Rainfed</option>
            </select>
          </Field>
          <Field label="Water source">
            <input className="input" {...register("water_source")} />
          </Field>
          <Field label="Current crop">
            <input className="input" {...register("current_crop")} />
          </Field>
          <Field label="Crop stage">
            <input className="input" placeholder="e.g. vegetative" {...register("crop_stage")} />
          </Field>
          <Field label="Previous crop">
            <input className="input" {...register("previous_crop")} />
          </Field>

          <div className="col-span-full h-48">
            <p className="mb-1 text-xs font-medium text-text-secondary">Tap the map to set the farm location</p>
            <FarmMapClient
              farms={[]}
              pickable
              pickedLocation={lat && lng ? { lat, lng } : null}
              onPick={(pickedLat, pickedLng) => {
                setValue("latitude", pickedLat, { shouldValidate: true });
                setValue("longitude", pickedLng, { shouldValidate: true });
              }}
            />
          </div>

          {serverError && (
            <p role="alert" className="col-span-full rounded-md bg-red-50 px-3 py-2 text-xs text-danger">
              {serverError}
            </p>
          )}

          <div className="col-span-full flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-md border border-border px-4 py-2 text-sm font-medium text-text-primary hover:bg-background">
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-deep disabled:opacity-60"
            >
              {submitting ? "Saving…" : "Save farm"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-text-secondary">
      {label}
      <div className="mt-1">{children}</div>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </label>
  );
}
