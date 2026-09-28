export type WizardAnswer = string | string[] | boolean;
export type WizardField = {
  name: string; label: string; kind: 'text' | 'textarea' | 'email' | 'number' | 'choice' | 'tags' | 'boolean';
  required: boolean; max_length: number | null; choices: { value: string; label: string }[];
};
export type VendorWizard = {
  answers: Record<string, WizardAnswer>; step: number; revision: number;
  sections: { number: number; title: string; fields: WizardField[] }[];
  review: { step: number; title: string; rows: { label: string; value: string }[] }[];
  approval_status: string; approval_label: string; review_feedback: string; submitted: boolean;
  logo_url: string | null; cover_url: string | null;
  photos: { id: string; url: string; caption: string }[]; pricing_listing_title: string;
  service_catalogue: { value: string; label: string; types: string[]; saved: boolean }[];
  errors?: Record<string, string[]>;
};

export function stepAnswers(wizard: VendorWizard, answers: VendorWizard['answers']) {
  return Object.fromEntries(wizard.sections[wizard.step - 1].fields.map((field) => [field.name, answers[field.name] ?? (field.kind === 'tags' ? [] : field.kind === 'boolean' ? false : '')]));
}

export function visibleField(field: WizardField, answers: VendorWizard['answers']) {
  if (field.name === 'other_services') return answers.other_enabled || answers.vendor_type === 'OTHER';
  if (field.name === 'price') return answers.pricing_type !== 'CONTACT_FOR_QUOTE';
  return true;
}

export function fieldChoices(field: WizardField, wizard: VendorWizard, answers: VendorWizard['answers']) {
  return field.name === 'specific_services'
    ? wizard.service_catalogue.filter((item) => item.saved || item.types.includes(String(answers.vendor_type)))
    : field.choices.filter((item) => item.value !== '');
}
