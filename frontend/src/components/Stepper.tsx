const STEPS = ['העלאה', 'זיהוי ערכים', 'סקירה ואישור', 'יצירה ומילוי', 'הורדה']

export function Stepper({ active }: { active: number }) {
  return (
    <ol className="mb-6 flex flex-wrap gap-2">
      {STEPS.map((name, i) => {
        const state = i < active ? 'done' : i === active ? 'active' : 'todo'
        return (
          <li
            key={name}
            className={
              'flex min-w-[110px] flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold ' +
              (state === 'active'
                ? 'bg-gradient-to-br from-accent to-accent-700 text-white shadow-[0_8px_22px_rgba(124,92,255,0.35)]'
                : state === 'done'
                  ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300'
                  : 'card text-slate-400')
            }
          >
            <span className="opacity-70">{i + 1}</span>
            {name}
          </li>
        )
      })}
    </ol>
  )
}
