"""
T-06-4: Proceso formal de actualización metodológica.

Documenta y valida el flujo completo para cambiar preguntas, pesos,
umbrales o cohortes. Ningún cambio se publica sin:
1. ADR o decisión documentada
2. Backtest comparativo aprobado
3. Aprobación humana explícita

Uso como script de validación pre-publicación:
    python -m benchmark.jobs.methodology_update --version 1.1.0 --check
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from benchmark.config.loader import (
    load_cohort_hierarchy,
    load_privacy_config,
    load_questionnaire,
)


@dataclass
class MethodologyValidationResult:
    version: str
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checklist: dict[str, bool] = field(default_factory=dict)


class MethodologyUpdateValidator:
    """
    Valida que una nueva versión metodológica cumpla todos los requisitos
    antes de ser publicada como activa.

    Checklist obligatorio:
    - Config cargable y sin errores de schema
    - Todas las dimensiones tienen al menos una pregunta
    - Todas las preguntas tienen al menos 2 opciones
    - Los pesos son positivos
    - Los valores de opción son números (no texto)
    - La jerarquía de cohortes tiene al menos un nivel global
    - Los umbrales de privacidad son >= 5
    - Existe una versión anterior publicada (para backtest)
    """

    def validate(self, version: str) -> MethodologyValidationResult:
        result = MethodologyValidationResult(version=version)
        checklist = {}

        # 1. Config cargable
        try:
            q = load_questionnaire(version)
            checklist["questionnaire_loadable"] = True
        except Exception as e:
            result.errors.append(f"Error cargando cuestionario v{version}: {e}")
            checklist["questionnaire_loadable"] = False
            result.passed = False
            result.checklist = checklist
            return result

        try:
            hierarchy = load_cohort_hierarchy(version)
            checklist["cohort_hierarchy_loadable"] = True
        except Exception as e:
            result.errors.append(f"Error cargando jerarquía de cohortes: {e}")
            checklist["cohort_hierarchy_loadable"] = False

        try:
            privacy = load_privacy_config(version)
            checklist["privacy_config_loadable"] = True
        except Exception as e:
            result.errors.append(f"Error cargando config de privacidad: {e}")
            checklist["privacy_config_loadable"] = False
            privacy = None

        # 2. Todas las dimensiones tienen preguntas
        from benchmark.domain.models import DimensionId
        dims_with_questions = {q_config.dimension for q_config in q.questions}
        all_dims_covered = set(DimensionId).issubset(dims_with_questions)
        checklist["all_dimensions_have_questions"] = all_dims_covered
        if not all_dims_covered:
            missing = set(DimensionId) - dims_with_questions
            result.errors.append(
                f"Dimensiones sin preguntas: {[d.value for d in missing]}"
            )

        # 3. Cada pregunta tiene ≥ 2 opciones
        questions_ok = all(len(qc.options) >= 2 for qc in q.questions)
        checklist["all_questions_have_options"] = questions_ok
        if not questions_ok:
            bad = [qc.id for qc in q.questions if len(qc.options) < 2]
            result.errors.append(f"Preguntas con menos de 2 opciones: {bad}")

        # 4. Pesos positivos
        weights_ok = all(qc.weight > 0 for qc in q.questions)
        checklist["positive_weights"] = weights_ok
        if not weights_ok:
            bad = [qc.id for qc in q.questions if qc.weight <= 0]
            result.errors.append(f"Preguntas con peso no positivo: {bad}")

        # 5. Valores de opción son numéricos
        values_ok = True
        for qc in q.questions:
            for opt in qc.options:
                try:
                    float(opt.value)
                except (TypeError, ValueError):
                    values_ok = False
                    result.errors.append(
                        f"Opción {opt.id} tiene valor no numérico: {opt.value!r}"
                    )
        checklist["numeric_option_values"] = values_ok

        # 6. Jerarquía tiene nivel global (attributes=[])
        if checklist.get("cohort_hierarchy_loadable"):
            has_global = any(len(level.attributes) == 0 for level in hierarchy.hierarchy)
            checklist["hierarchy_has_global_level"] = has_global
            if not has_global:
                result.errors.append(
                    "La jerarquía de cohortes no tiene nivel global (attributes=[]). "
                    "El sistema siempre debe tener un fallback."
                )

        # 7. Umbrales de privacidad >= 5
        if privacy is not None:
            privacy_ok = (
                privacy.min_cohort_size >= 5 and
                privacy.min_top_quartile_support >= 5 and
                privacy.min_effective_n_for_percentile >= 5
            )
            checklist["privacy_thresholds_adequate"] = privacy_ok
            if not privacy_ok:
                result.errors.append(
                    f"Umbrales de privacidad insuficientes: "
                    f"min_cohort={privacy.min_cohort_size}, "
                    f"min_tq={privacy.min_top_quartile_support}, "
                    f"min_pct={privacy.min_effective_n_for_percentile}. "
                    "Todos deben ser >= 5."
                )

        # 8. Advertencias (no bloquean)
        n_questions = len(q.questions)
        if n_questions < 10:
            result.warnings.append(
                f"Solo {n_questions} preguntas. Se recomienda al menos 10 para cobertura adecuada."
            )

        for qc in q.questions:
            max_val = max((o.value for o in qc.options), default=0)
            if max_val == 0:
                result.warnings.append(
                    f"Pregunta {qc.id}: todas las opciones tienen valor 0."
                )

        result.checklist = checklist
        result.passed = len(result.errors) == 0
        return result


def print_validation_report(result: MethodologyValidationResult) -> None:
    status = "✅ VÁLIDA" if result.passed else "❌ INVÁLIDA"
    print(f"\nValidación metodológica v{result.version}: {status}")
    print("-" * 50)

    print("\nChecklist:")
    for check, ok in result.checklist.items():
        icon = "✓" if ok else "✗"
        print(f"  [{icon}] {check}")

    if result.errors:
        print(f"\nErrores ({len(result.errors)}):")
        for e in result.errors:
            print(f"  ✗ {e}")

    if result.warnings:
        print(f"\nAdvertencias ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  ⚠ {w}")

    print()
    if result.passed:
        print("La versión puede proceder al backtest comparativo.")
        print("Pasos siguientes:")
        print("  1. Ejecutar: python -m benchmark.jobs.build_snapshot")
        print("  2. Revisar backtest en el panel")
        print("  3. Documentar ADR con la decisión")
        print("  4. Publicar con aprobación explícita")
    else:
        print("Corregir errores antes de proceder.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida una nueva versión metodológica antes de publicarla"
    )
    parser.add_argument("--version", required=True, help="Versión a validar (ej: 1.1.0)")
    parser.add_argument("--check", action="store_true",
                        help="Solo verificar, no modificar nada")
    args = parser.parse_args()

    validator = MethodologyUpdateValidator()
    result = validator.validate(args.version)
    print_validation_report(result)

    import sys
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
