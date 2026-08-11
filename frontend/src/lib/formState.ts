import type { CuestionarioRequest } from "../types";

export interface SurveyDraft {
  contexto: { facility_size: string; region: string; dc_type: string };
  latencia: { p1_minutos: number | ""; p2_minutos: number | ""; p3: string };
  visibilidad: { p1_sistemas: number | ""; p2: string; p3: string };
  atribucion_friccion: { p1: string; p2: string; p3: string };
  auto_cuantificacion: {
    p1_capacidad_total: number | "";
    p2_capacidad_utilizable: number | "";
    unidad: "mw" | "kw";
    p3: string;
  };
  bloqueantes: { p1_bloqueantes: string[]; p2_severidad: string };
}

export const initialDraft: SurveyDraft = {
  contexto: { facility_size: "", region: "", dc_type: "" },
  latencia: { p1_minutos: "", p2_minutos: "", p3: "" },
  visibilidad: { p1_sistemas: "", p2: "", p3: "" },
  atribucion_friccion: { p1: "", p2: "", p3: "" },
  auto_cuantificacion: {
    p1_capacidad_total: "",
    p2_capacidad_utilizable: "",
    unidad: "mw",
    p3: "",
  },
  bloqueantes: { p1_bloqueantes: [], p2_severidad: "" },
};

/** Falta completar algo obligatorio (fuera de los casos borde). */
export function draftIncompleto(d: SurveyDraft): boolean {
  const { contexto, latencia, visibilidad, atribucion_friccion, auto_cuantificacion, bloqueantes } = d;

  const contextoOk = contexto.facility_size && contexto.region.trim() && contexto.dc_type;
  const latenciaOk = latencia.p1_minutos !== "" && latencia.p2_minutos !== "" && latencia.p3;
  const visibilidadOk = visibilidad.p1_sistemas !== "" && visibilidad.p2 && visibilidad.p3;

  const noSabria = atribucion_friccion.p1 === "no_sabria_decir";
  const atribucionOk = atribucion_friccion.p1 && (noSabria || (atribucion_friccion.p2 && atribucion_friccion.p3));

  const autoCuantOk = auto_cuantificacion.p3;

  const soloNada = bloqueantes.p1_bloqueantes.length === 1 && bloqueantes.p1_bloqueantes[0] === "nada";
  const bloqueantesOk =
    bloqueantes.p1_bloqueantes.length > 0 && (soloNada || bloqueantes.p2_severidad);

  return !(contextoOk && latenciaOk && visibilidadOk && atribucionOk && autoCuantOk && bloqueantesOk);
}

/** Convierte el draft del formulario al payload exacto que espera POST /respuestas. */
export function draftToPayload(d: SurveyDraft): CuestionarioRequest {
  const noSabria = d.atribucion_friccion.p1 === "no_sabria_decir";
  const soloNada =
    d.bloqueantes.p1_bloqueantes.length === 1 && d.bloqueantes.p1_bloqueantes[0] === "nada";

  return {
    contexto: d.contexto,
    latencia: {
      p1_minutos: Number(d.latencia.p1_minutos),
      p2_minutos: Number(d.latencia.p2_minutos),
      p3: d.latencia.p3,
    },
    visibilidad: {
      p1_sistemas: Number(d.visibilidad.p1_sistemas),
      p2: d.visibilidad.p2,
      p3: d.visibilidad.p3,
    },
    atribucion_friccion: {
      p1: d.atribucion_friccion.p1,
      // El engine fuerza estos a 0 si p1='no_sabria_decir' — cualquier valor válido sirve.
      p2: noSabria ? "sin_evidencia" : d.atribucion_friccion.p2,
      p3: noSabria ? "nunca_revisada" : d.atribucion_friccion.p3,
    },
    auto_cuantificacion: {
      p1_capacidad_total: d.auto_cuantificacion.p1_capacidad_total === "" ? null : Number(d.auto_cuantificacion.p1_capacidad_total),
      p2_capacidad_utilizable: d.auto_cuantificacion.p2_capacidad_utilizable === "" ? null : Number(d.auto_cuantificacion.p2_capacidad_utilizable),
      unidad: d.auto_cuantificacion.unidad,
      p3: d.auto_cuantificacion.p3,
    },
    bloqueantes: {
      p1_bloqueantes: d.bloqueantes.p1_bloqueantes,
      p2_severidad: soloNada ? null : d.bloqueantes.p2_severidad,
    },
  };
}
