// Tipos alineados con config/questionnaire.yaml y app/schemas/*.py del backend.

export interface QuestionnaireOption {
  value: string;
  label: string;
  score?: number;
}

export interface QuestionnaireBucket {
  max_inclusive: number | null;
  score: number;
}

export interface QuestionnaireQuestion {
  id: string;
  prompt: string;
  type:
    | "numeric"
    | "categorical"
    | "categorical_nominal"
    | "categorical_nominal_multiselect";
  unit?: string;
  enters_index: boolean;
  options?: QuestionnaireOption[];
  scoring?: { type: "bucket"; buckets: QuestionnaireBucket[] };
  note?: string;
}

export interface QuestionnaireDimension {
  label: string;
  index_formula: string;
  note?: string;
  questions: QuestionnaireQuestion[];
}

export interface SegmentationField {
  id: string;
  label: string;
  type: "categorical";
  options?: string[];
  note?: string;
}

export interface Questionnaire {
  version: string;
  dimensions: Record<string, QuestionnaireDimension>;
  segmentation_fields: SegmentationField[];
}

// ── Payload de envío (app/schemas/request.py) ─────────────────────────────

export interface ContextoOperador {
  facility_size: string;
  region: string;
  dc_type: string;
}

export interface RespuestasLatencia {
  p1_minutos: number;
  p2_minutos: number;
  p3: string;
}

export interface RespuestasVisibilidad {
  p1_sistemas: number;
  p2: string;
  p3: string;
}

export interface RespuestasAtribucion {
  p1: string;
  p2: string;
  p3: string;
}

export interface RespuestasAutoCuantificacion {
  p1_capacidad_total: number | null;
  p2_capacidad_utilizable: number | null;
  unidad: "mw" | "kw";
  p3: string;
}

export interface RespuestasBloqueantes {
  p1_bloqueantes: string[];
  p2_severidad: string | null;
}

export interface CuestionarioRequest {
  contexto: ContextoOperador;
  latencia: RespuestasLatencia;
  visibilidad: RespuestasVisibilidad;
  atribucion_friccion: RespuestasAtribucion;
  auto_cuantificacion: RespuestasAutoCuantificacion;
  bloqueantes: RespuestasBloqueantes;
}

// ── Respuesta (app/schemas/response.py) ───────────────────────────────────

export interface ScoreDimension {
  dimension: string;
  score: number;
  percentil: number;
  descripcion_breve: string;
  mediana_ref: number;
  p75_ref: number;
}

export interface ResultadoResponse {
  operator_id: string;
  perfil: string;
  friccion_principal: string;
  scores: ScoreDimension[];
  top_quartile_gaps: Record<string, string>;
  titular: string;
  diagnostico_texto: string;
  accion_sugerida: string;
  confianza_nivel: "alto" | "medio" | "bajo";
  confianza_descripcion: string;
  porcentaje_capacidad_varada: number | null;
  benchmark_version: string;
  dimension_version: string;
}
