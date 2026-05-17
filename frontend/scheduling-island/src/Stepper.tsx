type Props = {
  current: 1 | 2 | 3 | 4;
};

const STEPS = [
  { n: 1, label: "Type" },
  { n: 2, label: "Date" },
  { n: 3, label: "Time" },
  { n: 4, label: "Details" },
];

export function Stepper({ current }: Props) {
  return (
    <ol className="flex items-center justify-between text-xs sm:text-sm mb-6">
      {STEPS.map((s, idx) => {
        const done = s.n < current;
        const active = s.n === current;
        return (
          <li key={s.n} className="flex items-center flex-1 last:flex-none">
            <div
              className={`flex items-center gap-2 ${
                active ? "text-summit-700 font-semibold" : done ? "text-slate-600" : "text-slate-400"
              }`}
            >
              <span
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full border text-xs ${
                  done
                    ? "border-summit-600 bg-summit-600 text-white"
                    : active
                      ? "border-summit-600 text-summit-700"
                      : "border-slate-300"
                }`}
              >
                {done ? "\u2713" : s.n}
              </span>
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            {idx < STEPS.length - 1 && (
              <span
                className={`mx-2 sm:mx-3 h-px flex-1 ${
                  done ? "bg-summit-500" : "bg-slate-200"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
