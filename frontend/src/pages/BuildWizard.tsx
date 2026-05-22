import { useState } from "react";
import WizardStepper from "../components/WizardStepper";
import StepProject from "./wizard/StepProject";
import StepRegistry, { RegistryConfig } from "./wizard/StepRegistry";
import StepCrawl from "./wizard/StepCrawl";
import { ActivityEvent } from "../components/ActivityPanel";

interface BuildWizardProps {
  onBack: () => void;
  onAddEvent: (event: Omit<ActivityEvent, "id">) => void;
}

// 1 = project entry, 2 = dataset picker, 3 = registry, 4 = crawl & write, 5 = done
type WizardStep = 1 | 2 | 3 | 4 | 5;

export default function BuildWizard({ onBack, onAddEvent }: BuildWizardProps) {
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [stepperStep, setStepperStep] = useState<number>(1);

  const [projectId, setProjectId] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [registry, setRegistry] = useState<RegistryConfig>({
    project: "",
    dataset: "",
    table: "data_catalog_registry",
  });

  function handleDatasetsListed(pid: string, dataset: string) {
    setProjectId(pid);
    setSelectedDataset(dataset);
    setRegistry({ project: pid, dataset: dataset.includes(":") ? dataset.split(":")[1] : dataset, table: "data_catalog_registry" });
    setWizardStep(3);
    setStepperStep(3);
  }

  function handleRegistryConfirmed(reg: RegistryConfig) {
    setRegistry(reg);
    setWizardStep(4);
    setStepperStep(4);
  }

  function handleBackFromRegistry() {
    setWizardStep(1);
    setStepperStep(2);
  }

  function handleBackFromCrawl() {
    setWizardStep(3);
    setStepperStep(3);
  }

  return (
    <div className="p-8">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-6 transition-colors"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back
      </button>

      <WizardStepper currentStep={stepperStep} completedUpTo={stepperStep - 1} />

      {(wizardStep === 1 || wizardStep === 2) && (
        <StepProject
          initialProjectId={projectId}
          onDatasetsListed={handleDatasetsListed}
          onSubStepChange={(s) => setStepperStep(s)}
          onAddEvent={onAddEvent}
        />
      )}

      {wizardStep === 3 && (
        <StepRegistry
          projectId={projectId}
          selectedDataset={selectedDataset}
          onConfirm={handleRegistryConfirmed}
          onBack={handleBackFromRegistry}
        />
      )}

      {wizardStep === 4 && (
        <StepCrawl
          sourceProjectId={projectId}
          selectedDataset={selectedDataset}
          registry={registry}
          onAddEvent={onAddEvent}
          onBack={handleBackFromCrawl}
        />
      )}
    </div>
  );
}
