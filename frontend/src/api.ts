import type { CuestionarioRequest, Questionnaire, ResultadoResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchQuestionnaire(): Promise<Questionnaire> {
  const res = await fetch(`${API_URL}/api/v1/questionnaire`);
  if (!res.ok) {
    throw new ApiError("No se pudo cargar el cuestionario.", res.status);
  }
  return res.json();
}

export async function enviarRespuestas(
  payload: CuestionarioRequest,
): Promise<ResultadoResponse> {
  const res = await fetch(`${API_URL}/api/v1/respuestas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detalle =
      body?.detail && typeof body.detail === "string"
        ? body.detail
        : "Revisá las respuestas del formulario e intentá de nuevo.";
    throw new ApiError(detalle, res.status);
  }

  return res.json();
}
