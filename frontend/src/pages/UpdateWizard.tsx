import { useState } from "react";
import { ActivityEvent } from "../components/ActivityPanel";
import UpdateStepIdentify, { UpdateIdentifyConfig } from "./wizard/UpdateStepIdentify";
import UpdateStepRun from "./wizard/UpdateStepRun";

interface UpdateWizardProps {
  onBack: () => void;
  onAddEvent: (event: Omit<ActivityEvent, "id">) => void;
}

// Step 1 = identify, Step 2 = running/done
type WizardStep = 1 | 2;

// ── Minimal stepper for the update flow (3 labels) ─────────────────────────

const UPDATE_STEPS = ["Identify dataset", "Update registry", "Done"];

function UpdateStepper({ currentStep }: { currentStep: number }) {
  return (
    <nav className="flex items-center gap-0 mb-8">
      {UPDATE_STEPS.map((label, idx) => {
        const num = idx + 1;
        const isCompleted = num < currentStep;
        const isActive = num === currentStep;

        return (
          <div key={label} className="flex items-center">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0 ${
                  isCompleted || isActive
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-gray-300 text-gray-400"
                }`}
              >
                {isCompleted ? (
                  <svg
                    className="w-3.5 h-3.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  num
                )}
              </span>
              <span
                className={`text-xs font-medium whitespace-nowrap ${
                  isActive
                    ? "text-gray-900"
                    : isCompleted
                      ? "text-gray-600"
                      : "text-gray-400"
                }`}
              >
                {label}
              </span>
            </div>
            {idx < UPDATE_STEPS.length - 1 && (
              <div
                className={`w-12 h-px mx-3 ${
                  num < currentStep
                    ? "bg-gray-400"
                    : "border-t border-dashed border-gray-300"
                }`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}

// ── Main wizard ────────────────────────────────────────────────────────────

export default function UpdateWizard({ onBack, onAddEvent }: UpdateWizardProps) {
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [stepperStep, setStepperStep] = useState(1);
  const [config, setConfig] = useState<UpdateIdentifyConfig | null>(null);

  function handleIdentifySubmit(cfg: UpdateIdentifyConfig) {
    setConfig(cfg);
    setWizardStep(2);
    setStepperStep(2);
  }

  function handleRunDone() {
    setStepperStep(3);
  }

  function handleBackFromRun() {
    setWizardStep(1);
    setStepperStep(1);
  }

  return (
    <div className="p-8">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-6 transition-colors"
      >
        <svg
          className="w-4 h-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back
      </button>

      <UpdateStepper currentStep={stepperStep} />

      {wizardStep === 1 && (
        <UpdateStepIdentify onSubmit={handleIdentifySubmit} onBack={onBack} />
      )}

      {wizardStep === 2 && config && (
        <UpdateStepRun
          config={config}
          onAddEvent={onAddEvent}
          onBack={handleBackFromRun}
          onDone={handleRunDone}
        />
      )}
    </div>
  );
}
