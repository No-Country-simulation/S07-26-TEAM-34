import type { Questionnaire, QuestionnaireQuestion } from "../types";

// Mapea los ids largos de config/questionnaire.yaml a los ids cortos
// usados internamente (misma convención que app/config/loader.py del backend).
export const DIMENSION_ID_MAP: Record<string, string> = {
  latencia_coordinacion: "latencia",
  visibilidad_cross_layer: "visibilidad",
  atribucion_friccion: "atribucion_friccion",
  auto_cuantificacion: "auto_cuantificacion",
  bloqueantes: "bloqueantes",
};

const SHORT_ID_RE = /(?:^|_)(p\d+)(?:_|$)/;

export function shortQuestionId(fullId: string): string {
  const match = SHORT_ID_RE.exec(fullId);
  if (!match) throw new Error(`No se pudo extraer el id corto de "${fullId}"`);
  return match[1];
}

export interface IndexedDimension {
  shortId: string;
  label: string;
  note?: string;
  questions: Record<string, QuestionnaireQuestion>;
}

export function indexQuestionnaire(q: Questionnaire): Record<string, IndexedDimension> {
  const out: Record<string, IndexedDimension> = {};
  for (const [longId, dim] of Object.entries(q.dimensions)) {
    const shortId = DIMENSION_ID_MAP[longId] ?? longId;
    const questions: Record<string, QuestionnaireQuestion> = {};
    for (const question of dim.questions) {
      questions[shortQuestionId(question.id)] = question;
    }
    out[shortId] = { shortId, label: dim.label, note: dim.note, questions };
  }
  return out;
}

export const PERFIL_LABELS: Record<string, string> = {
  operacion_optimizada: "Operación con alta coordinación entre capas",
  coordinacion_parcial: "Coordinación cross-layer en desarrollo",
  operacion_reactiva: "Operación reactiva con coordinación manual",
  visibilidad_limitada: "Visibilidad y coordinación cross-layer limitadas",
};

export const DIMENSION_LABELS: Record<string, string> = {
  latencia: "Latencia de coordinación",
  visibilidad: "Visibilidad cross-layer",
  atribucion_friccion: "Atribución de fricción",
  auto_cuantificacion: "Auto-cuantificación",
  bloqueantes: "Bloqueantes",
};

export const DIMENSION_ORDER = [
  "visibilidad",
  "atribucion_friccion",
  "latencia",
  "auto_cuantificacion",
  "bloqueantes",
];
