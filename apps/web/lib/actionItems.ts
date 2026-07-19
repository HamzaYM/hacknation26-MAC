// Static demo queue — a real backend endpoint for "what's still missing per
// case" doesn't exist yet (financial_profile is currently filled in the
// fixture, so this is illustrative of the pattern, not live-computed).
// TODO(Hamza). Every "unlocks" line names a $ or % figure tied to a specific
// bill, pulled from numbers shown on that bill's detail page — never
// invented here. Three interaction types on purpose: a one-click confirm
// is the wrong shape for "give us your income" (needs a constrained choice)
// or "apply for charity care" (needs several fields at once) — forcing
// everything through "Yes, go ahead" was the gap.
export type ActionItemType = "confirm" | "select" | "form";

interface Base {
  id: string;
  entity: string;
  question: string;
  why: string;
  unlocks: string;
}

export interface ConfirmItem extends Base {
  type: "confirm";
}

export interface SelectItem extends Base {
  type: "select";
  options: string[];
}

export interface FormField {
  key: string;
  label: string;
  kind: "number" | "select";
  options?: string[];
  placeholder?: string;
}

export interface FormItem extends Base {
  type: "form";
  fields: FormField[];
  submitLabel: string;
}

export type ActionItem = ConfirmItem | SelectItem | FormItem;

export const ACTION_ITEMS: ActionItem[] = [
  {
    id: "confirm-dos",
    entity: "Mercy General Hospital",
    type: "confirm",
    question: "Confirm your date of service",
    why: "Lets us match the itemized bill line-by-line against your insurance EOB.",
    unlocks: "Confirms the $412 (9.6%) duplicate-charge win already found on your Mercy General bill.",
  },
  {
    id: "charity-care-form",
    entity: "Mercy General Hospital",
    type: "form",
    question: "Complete your charity care application",
    why: "Mercy General is a nonprofit and must offer discounted or free care below certain income thresholds (IRS §501(r)), but the application needs a few specific numbers we don't have yet.",
    unlocks: "Could add charity-care eligibility to your Mercy General bill: potentially 50–100% off the remaining $3,875 (~$1,938–$3,875).",
    submitLabel: "Submit application",
    fields: [
      { key: "household_size", label: "Household size", kind: "number", placeholder: "2" },
      { key: "monthly_income", label: "Monthly household income", kind: "number", placeholder: "3,250" },
      {
        key: "employment_status",
        label: "Employment status",
        kind: "select",
        options: ["Employed full-time", "Employed part-time", "Unemployed", "Retired", "Unable to work"],
      },
    ],
  },
  {
    id: "authorize-bay-state",
    entity: "Bay State Emergency Physicians",
    type: "confirm",
    question: "Authorize us to dispute the ER physician charge",
    why: "This is a separate bill from a separate entity; we need your go-ahead per entity before we call.",
    unlocks: "Unlocks the call to Bay State Emergency Physicians: typical range is 15–35% off their $640 balance (~$96–$224).",
  },
  {
    id: "bay-state-income",
    entity: "Bay State Emergency Physicians",
    type: "select",
    question: "What's your household income range?",
    why: "Bay State screens separately from Mercy General for its own hardship/prompt-pay discount: this determines what you qualify for here specifically, not what you already told us at signup.",
    unlocks: "Could unlock a hardship discount on your $640 Bay State balance: typically 10–25% off (~$64–$160).",
    options: ["Under $30k", "$30k – $50k", "$50k – $75k", "$75k+"],
  },
  {
    id: "authorize-collections",
    entity: "Meridian Recovery Services",
    type: "confirm",
    question: "Authorize us to negotiate your collections account",
    why: "Collections settlements need explicit authorization since a lump-sum offer is binding once accepted.",
    unlocks: "Unlocks settlement negotiation on your $980 collections balance: typically 25–50% off (~$245–$490) via lump-sum settlement.",
  },
];

export function itemsForEntity(entityName: string): ActionItem[] {
  return ACTION_ITEMS.filter((i) => i.entity === entityName);
}
