import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, enviarRespuestas, fetchQuestionnaire } from "../../api";
import { draftIncompleto, draftToPayload, initialDraft, type SurveyDraft } from "../../lib/formState";
import { indexQuestionnaire, type IndexedDimension } from "../../lib/questionnaire";
import type { ResultadoResponse } from "../../types";
import { DimensionCard } from "./DimensionCard";
import { CheckboxGroup, FieldLabel, NumericField, RadioGroup, SelectField, TextField } from "./fields";

export function SurveySection({
  onResultado,
}: {
  onResultado: (r: ResultadoResponse) => void;
}) {
  const [dims, setDims] = useState<Record<string, IndexedDimension> | null>(null);
  const [facilityOptions, setFacilityOptions] = useState<string[]>([]);
  const [dcTypeOptions, setDcTypeOptions] = useState<string[]>([]);
  const [draft, setDraft] = useState<SurveyDraft>(initialDraft);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchQuestionnaire()
      .then((q) => {
        setDims(indexQuestionnaire(q));
        const facility = q.segmentation_fields.find((f) => f.id === "facility_size");
        const dcType = q.segmentation_fields.find((f) => f.id === "dc_type");
        setFacilityOptions(facility?.options ?? []);
        setDcTypeOptions(dcType?.options ?? []);
      })
      .catch(() => setLoadError("No pudimos conectar con el servidor. ¿Está corriendo el backend?"));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const resultado = await enviarRespuestas(draftToPayload(draft));
      onResultado(resultado);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Algo salió mal. Intentá de nuevo.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loadError) {
    return (
      <SectionShell>
        <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-6 py-5 text-sm text-red-300">
          {loadError}
        </p>
      </SectionShell>
    );
  }

  if (!dims) {
    return (
      <SectionShell>
        <p className="text-sm text-white/40">Cargando cuestionario…</p>
      </SectionShell>
    );
  }

  const vis = dims.visibilidad;
  const atr = dims.atribucion_friccion;
  const lat = dims.latencia;
  const auto = dims.auto_cuantificacion;
  const blk = dims.bloqueantes;
  const noSabria = draft.atribucion_friccion.p1 === "no_sabria_decir";
  const soloNada = draft.bloqueantes.p1_bloqueantes.length === 1 && draft.bloqueantes.p1_bloqueantes[0] === "nada";

  return (
    <SectionShell>
      <form onSubmit={handleSubmit} className="grid gap-6">
        {/* Contexto */}
        <DimensionCard index={0} title="Sobre tu facility">
          <div>
            <FieldLabel>Tamaño aproximado</FieldLabel>
            <SelectField
              options={facilityOptions}
              value={draft.contexto.facility_size}
              onChange={(v) => setDraft((d) => ({ ...d, contexto: { ...d.contexto, facility_size: v } }))}
            />
          </div>
          <div>
            <FieldLabel>Tipo de data center</FieldLabel>
            <SelectField
              options={dcTypeOptions}
              value={draft.contexto.dc_type}
              onChange={(v) => setDraft((d) => ({ ...d, contexto: { ...d.contexto, dc_type: v } }))}
            />
          </div>
          <div className="sm:col-span-2">
            <FieldLabel note="Continente o región amplia — no hace falta el país exacto.">Región</FieldLabel>
            <TextField
              value={draft.contexto.region}
              placeholder="ej. Latinoamérica"
              onChange={(v) => setDraft((d) => ({ ...d, contexto: { ...d.contexto, region: v } }))}
            />
          </div>
        </DimensionCard>

        {/* Visibilidad */}
        <DimensionCard index={1} title={vis.label}>
          <div>
            <FieldLabel>{vis.questions.p1.prompt}</FieldLabel>
            <NumericField
              value={draft.visibilidad.p1_sistemas}
              suffix="sistemas"
              onChange={(v) => setDraft((d) => ({ ...d, visibilidad: { ...d.visibilidad, p1_sistemas: v } }))}
            />
          </div>
          <div>
            <FieldLabel>{vis.questions.p2.prompt}</FieldLabel>
            <RadioGroup
              name="vis_p2"
              options={vis.questions.p2.options ?? []}
              value={draft.visibilidad.p2}
              onChange={(v) => setDraft((d) => ({ ...d, visibilidad: { ...d.visibilidad, p2: v } }))}
            />
          </div>
          <div className="sm:col-span-2">
            <FieldLabel>{vis.questions.p3.prompt}</FieldLabel>
            <RadioGroup
              name="vis_p3"
              options={vis.questions.p3.options ?? []}
              value={draft.visibilidad.p3}
              onChange={(v) => setDraft((d) => ({ ...d, visibilidad: { ...d.visibilidad, p3: v } }))}
            />
          </div>
        </DimensionCard>

        {/* Atribución */}
        <DimensionCard index={2} title={atr.label}>
          <div className="sm:col-span-2">
            <FieldLabel note={atr.questions.p1.note}>{atr.questions.p1.prompt}</FieldLabel>
            <RadioGroup
              name="atr_p1"
              options={atr.questions.p1.options ?? []}
              value={draft.atribucion_friccion.p1}
              onChange={(v) => setDraft((d) => ({ ...d, atribucion_friccion: { ...d.atribucion_friccion, p1: v } }))}
            />
          </div>
          {!noSabria && (
            <>
              <div>
                <FieldLabel>{atr.questions.p2.prompt}</FieldLabel>
                <RadioGroup
                  name="atr_p2"
                  options={atr.questions.p2.options ?? []}
                  value={draft.atribucion_friccion.p2}
                  onChange={(v) => setDraft((d) => ({ ...d, atribucion_friccion: { ...d.atribucion_friccion, p2: v } }))}
                />
              </div>
              <div>
                <FieldLabel>{atr.questions.p3.prompt}</FieldLabel>
                <RadioGroup
                  name="atr_p3"
                  options={atr.questions.p3.options ?? []}
                  value={draft.atribucion_friccion.p3}
                  onChange={(v) => setDraft((d) => ({ ...d, atribucion_friccion: { ...d.atribucion_friccion, p3: v } }))}
                />
              </div>
            </>
          )}
        </DimensionCard>

        {/* Latencia */}
        <DimensionCard index={3} title={lat.label}>
          <div>
            <FieldLabel>{lat.questions.p1.prompt}</FieldLabel>
            <NumericField
              value={draft.latencia.p1_minutos}
              suffix="min"
              onChange={(v) => setDraft((d) => ({ ...d, latencia: { ...d.latencia, p1_minutos: v } }))}
            />
          </div>
          <div>
            <FieldLabel>{lat.questions.p2.prompt}</FieldLabel>
            <NumericField
              value={draft.latencia.p2_minutos}
              suffix="min"
              onChange={(v) => setDraft((d) => ({ ...d, latencia: { ...d.latencia, p2_minutos: v } }))}
            />
          </div>
          <div className="sm:col-span-2">
            <FieldLabel>{lat.questions.p3.prompt}</FieldLabel>
            <RadioGroup
              name="lat_p3"
              options={lat.questions.p3.options ?? []}
              value={draft.latencia.p3}
              onChange={(v) => setDraft((d) => ({ ...d, latencia: { ...d.latencia, p3: v } }))}
            />
          </div>
        </DimensionCard>

        {/* Auto-cuantificación */}
        <DimensionCard index={4} title={auto.label}>
          <div className="sm:col-span-2">
            <FieldLabel note={auto.note}>Unidad de medida</FieldLabel>
            <div className="flex gap-2">
              {(["mw", "kw"] as const).map((u) => (
                <button
                  type="button"
                  key={u}
                  onClick={() => setDraft((d) => ({ ...d, auto_cuantificacion: { ...d.auto_cuantificacion, unidad: u } }))}
                  className={`rounded-lg border px-4 py-2 text-sm font-mono uppercase transition ${
                    draft.auto_cuantificacion.unidad === u
                      ? "border-brand-500/60 bg-brand-500/10 text-white"
                      : "border-white/10 bg-ink-900 text-white/50"
                  }`}
                >
                  {u}
                </button>
              ))}
            </div>
          </div>
          <div>
            <FieldLabel>{auto.questions.p1.prompt}</FieldLabel>
            <NumericField
              value={draft.auto_cuantificacion.p1_capacidad_total}
              suffix={draft.auto_cuantificacion.unidad}
              onChange={(v) => setDraft((d) => ({ ...d, auto_cuantificacion: { ...d.auto_cuantificacion, p1_capacidad_total: v } }))}
            />
          </div>
          <div>
            <FieldLabel>{auto.questions.p2.prompt}</FieldLabel>
            <NumericField
              value={draft.auto_cuantificacion.p2_capacidad_utilizable}
              suffix={draft.auto_cuantificacion.unidad}
              onChange={(v) => setDraft((d) => ({ ...d, auto_cuantificacion: { ...d.auto_cuantificacion, p2_capacidad_utilizable: v } }))}
            />
          </div>
          <div className="sm:col-span-2">
            <FieldLabel>{auto.questions.p3.prompt}</FieldLabel>
            <RadioGroup
              name="auto_p3"
              options={auto.questions.p3.options ?? []}
              value={draft.auto_cuantificacion.p3}
              onChange={(v) => setDraft((d) => ({ ...d, auto_cuantificacion: { ...d.auto_cuantificacion, p3: v } }))}
            />
          </div>
        </DimensionCard>

        {/* Bloqueantes */}
        <DimensionCard index={5} title={blk.label}>
          <div className="sm:col-span-2">
            <FieldLabel note={blk.questions.p1.note}>{blk.questions.p1.prompt}</FieldLabel>
            <CheckboxGroup
              options={blk.questions.p1.options ?? []}
              value={draft.bloqueantes.p1_bloqueantes}
              onChange={(v) => setDraft((d) => ({ ...d, bloqueantes: { ...d.bloqueantes, p1_bloqueantes: v } }))}
            />
          </div>
          {!soloNada && draft.bloqueantes.p1_bloqueantes.length > 0 && (
            <div className="sm:col-span-2">
              <FieldLabel>{blk.questions.p2.prompt}</FieldLabel>
              <RadioGroup
                name="blk_p2"
                options={blk.questions.p2.options ?? []}
                value={draft.bloqueantes.p2_severidad}
                onChange={(v) => setDraft((d) => ({ ...d, bloqueantes: { ...d.bloqueantes, p2_severidad: v } }))}
              />
            </div>
          )}
        </DimensionCard>

        {submitError && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-6 py-4 text-sm text-red-300">
            {submitError}
          </p>
        )}

        <button
          type="submit"
          disabled={draftIncompleto(draft) || submitting}
          className="justify-self-start rounded-full bg-gradient-to-r from-brand-500 to-accent-500 px-8 py-3.5 text-sm font-semibold text-ink-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          {submitting ? "Calculando tu diagnóstico…" : "Ver mi posición en el benchmark →"}
        </button>
      </form>
    </SectionShell>
  );
}

function SectionShell({ children }: { children: ReactNode }) {
  return (
    <section className="mx-auto max-w-3xl px-6 py-16 sm:px-8">
      <div className="mb-12">
        <span className="font-mono text-xs tracking-widest text-brand-400 uppercase">Tu diagnóstico</span>
        <h2 className="mt-3 text-3xl font-bold text-white sm:text-4xl">El diagnóstico</h2>
        <p className="mt-3 max-w-xl text-white/50">
          Menos de 10 minutos. Anónimo. Sin login, sin datos personales.
        </p>
      </div>
      {children}
    </section>
  );
}
