export interface WizardStep {
  label: string;
}

const STEPS: WizardStep[] = [
  { label: "Project" },
  { label: "Source dataset" },
  { label: "Registry location" },
  { label: "Crawl & write" },
  { label: "Done" },
];

interface WizardStepperProps {
  currentStep: number; // 1-indexed
  completedUpTo: number; // steps <= this are done
}

export default function WizardStepper({ currentStep, completedUpTo }: WizardStepperProps) {
  return (
    <nav className="flex items-center gap-0 mb-8">
      {STEPS.map((step, idx) => {
        const num = idx + 1;
        const isCompleted = num <= completedUpTo;
        const isActive = num === currentStep;

        return (
          <div key={step.label} className="flex items-center">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0 ${
                  isCompleted
                    ? "bg-blue-600 text-white"
                    : isActive
                      ? "bg-blue-600 text-white"
                      : "bg-white border border-gray-300 text-gray-400"
                }`}
              >
                {isCompleted && !isActive ? (
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  num
                )}
              </span>
              <span
                className={`text-xs font-medium whitespace-nowrap ${
                  isActive ? "text-gray-900" : isCompleted ? "text-gray-600" : "text-gray-400"
                }`}
              >
                {step.label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className={`w-12 h-px mx-3 ${num < currentStep ? "bg-gray-400" : "border-t border-dashed border-gray-300"}`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
