import type { FactsInput } from "../api/types";

interface ScenarioFactsProps {
  value: FactsInput;
  onChange: (value: FactsInput) => void;
}

interface Option {
  value: string;
  label: string;
}

const ACTION_OPTIONS: Option[] = [
  { value: "use", label: "Use the component" },
  { value: "modify", label: "Modify the component" },
  { value: "copy", label: "Copy the component" },
  { value: "link", label: "Link against the component" },
  { value: "aggregate", label: "Aggregate with other software" },
  { value: "redistribute", label: "Redistribute the component" },
  { value: "sublicense", label: "Sublicense the component" },
];

const DISTRIBUTION_FORM_OPTIONS: Option[] = [
  { value: "none", label: "No distribution" },
  { value: "source", label: "Source code" },
  { value: "binary", label: "Binary / compiled" },
  { value: "container", label: "Container image" },
  { value: "network_service", label: "Network service" },
  { value: "client_side", label: "Client-side delivery" },
];

const RECIPIENT_OPTIONS: Option[] = [
  { value: "employees", label: "Employees" },
  { value: "contractors", label: "Contractors" },
  { value: "customers", label: "Customers" },
  { value: "public", label: "Public" },
];

function SelectField(props: {
  id: string;
  label: string;
  value: string;
  options: Option[];
  placeholder: string;
  onValue: (value: string) => void;
}) {
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <select
        id={props.id}
        value={props.value}
        onChange={(event) => props.onValue(event.target.value)}
      >
        <option value="">{props.placeholder}</option>
        {props.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function TriStateField(props: {
  id: string;
  label: string;
  value: boolean | undefined;
  onValue: (value: boolean | undefined) => void;
}) {
  const raw = props.value === undefined ? "" : String(props.value);
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <select
        id={props.id}
        value={raw}
        onChange={(event) => {
          const next = event.target.value;
          props.onValue(next === "" ? undefined : next === "true");
        }}
      >
        <option value="">Not sure / not specified</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    </div>
  );
}

function TextField(props: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  onValue: (value: string) => void;
}) {
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <input
        id={props.id}
        type="text"
        value={props.value}
        placeholder={props.placeholder}
        onChange={(event) => props.onValue(event.target.value)}
      />
    </div>
  );
}

/** Structured scenario form. Every field defaults to "unknown" and is omitted when unknown. */
export function ScenarioFacts({ value, onChange }: ScenarioFactsProps) {
  const set = (patch: Partial<FactsInput>) => onChange({ ...value, ...patch });

  const distribution = value.distribution;
  const showDistributionDetails = distribution === true;

  return (
    <fieldset className="fact-form">
      <legend>Scenario facts</legend>
      <div className="field-grid">
        <SelectField
          id="fact-action"
          label="What are you doing with the component?"
          value={value.action ?? ""}
          options={ACTION_OPTIONS}
          placeholder="Select an action…"
          onValue={(v) => set({ action: v || undefined })}
        />
        <TriStateField
          id="fact-distribution"
          label="Are you distributing the component?"
          value={distribution}
          onValue={(v) => set({ distribution: v })}
        />
        {showDistributionDetails && (
          <>
            <SelectField
              id="fact-distribution-form"
              label="In what form?"
              value={value.distribution_form ?? ""}
              options={DISTRIBUTION_FORM_OPTIONS}
              placeholder="Select a form…"
              onValue={(v) => set({ distribution_form: v || undefined })}
            />
            <SelectField
              id="fact-recipient"
              label="Who receives it?"
              value={value.recipient ?? ""}
              options={RECIPIENT_OPTIONS}
              placeholder="Select a recipient…"
              onValue={(v) => set({ recipient: v || undefined })}
            />
            <TriStateField
              id="fact-modified"
              label="Did you modify the component?"
              value={value.modified}
              onValue={(v) => set({ modified: v })}
            />
          </>
        )}
        <TextField
          id="fact-outbound-license"
          label="Outbound license (if aggregating, linking, or sublicensing)"
          value={value.outbound_license ?? ""}
          placeholder="e.g. MIT"
          onValue={(v) => set({ outbound_license: v || undefined })}
        />
        <TextField
          id="fact-selected-branch"
          label="Selected license branch (for OR expressions)"
          value={value.selected_branch ?? ""}
          placeholder="e.g. Apache-2.0"
          onValue={(v) => set({ selected_branch: v || undefined })}
        />
      </div>
    </fieldset>
  );
}
