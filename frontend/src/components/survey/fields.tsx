import type { ReactNode } from "react";
import type { QuestionnaireOption } from "../../types";

export function FieldLabel({ children, note }: { children: ReactNode; note?: string }) {
  return (
    <div className="mb-3">
      <p className="text-sm font-medium text-white/90">{children}</p>
      {note && <p className="mt-1 text-xs text-white/40">{note}</p>}
    </div>
  );
}

export function NumericField({
  value,
  onChange,
  placeholder,
  suffix,
}: {
  value: number | "";
  onChange: (v: number | "") => void;
  placeholder?: string;
  suffix?: string;
}) {
  return (
    <div className="relative">
      <input
        type="number"
        inputMode="decimal"
        min={0}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        className="w-full rounded-lg border border-white/10 bg-ink-900 px-4 py-3 font-mono text-sm text-white outline-none transition focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20"
      />
      {suffix && (
        <span className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-xs text-white/40">
          {suffix}
        </span>
      )}
    </div>
  );
}

export function RadioGroup({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: QuestionnaireOption[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid gap-2">
      {options.map((opt) => (
        <label
          key={opt.value}
          className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm transition ${
            value === opt.value
              ? "border-brand-500/60 bg-brand-500/10 text-white"
              : "border-white/10 bg-ink-900 text-white/70 hover:border-white/20"
          }`}
        >
          <input
            type="radio"
            name={name}
            className="accent-brand-500"
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
          />
          {opt.label}
        </label>
      ))}
    </div>
  );
}

export function CheckboxGroup({
  options,
  value,
  onChange,
}: {
  options: QuestionnaireOption[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  function toggle(optValue: string) {
    if (optValue === "nada") {
      onChange(value.includes("nada") ? [] : ["nada"]);
      return;
    }
    const withoutNada = value.filter((v) => v !== "nada");
    onChange(
      withoutNada.includes(optValue)
        ? withoutNada.filter((v) => v !== optValue)
        : [...withoutNada, optValue],
    );
  }

  return (
    <div className="grid gap-2">
      {options.map((opt) => (
        <label
          key={opt.value}
          className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm transition ${
            value.includes(opt.value)
              ? "border-brand-500/60 bg-brand-500/10 text-white"
              : "border-white/10 bg-ink-900 text-white/70 hover:border-white/20"
          }`}
        >
          <input
            type="checkbox"
            className="accent-brand-500"
            checked={value.includes(opt.value)}
            onChange={() => toggle(opt.value)}
          />
          {opt.label}
        </label>
      ))}
    </div>
  );
}

export function SelectField({
  options,
  value,
  onChange,
  placeholder,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-white/10 bg-ink-900 px-4 py-3 text-sm text-white outline-none transition focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20"
    >
      <option value="" disabled className="text-white/40">
        {placeholder ?? "Seleccioná una opción"}
      </option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

export function TextField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-white/10 bg-ink-900 px-4 py-3 text-sm text-white outline-none transition placeholder:text-white/30 focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20"
    />
  );
}
