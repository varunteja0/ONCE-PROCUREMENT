import { Activity as ActivityIcon, Home as HomeIcon, Receipt, Users } from "lucide-react";

import type { Screen } from "../../lib/store";

const TABS: ReadonlyArray<{
  id: Extract<Screen, "home" | "suppliers" | "submissions" | "receipts" | "activity">;
  label: string;
  Icon: typeof HomeIcon;
}> = [
  { id: "home", label: "Home", Icon: HomeIcon },
  { id: "suppliers", label: "Suppliers", Icon: Users },
  { id: "submissions", label: "Submissions", Icon: Receipt },
  { id: "receipts", label: "Receipts", Icon: Receipt },
  { id: "activity", label: "Activity", Icon: ActivityIcon },
];

export function Nav({ current, onChange }: { current: Screen; onChange: (s: Screen) => void }): JSX.Element {
  return (
    <nav className="flex border-b border-slate-200 bg-white" role="tablist" aria-label="Primary navigation">
      {TABS.map(({ id, label, Icon }) => {
        const active = current === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active}
            className={`tab ${active ? "tab-active" : ""}`}
            onClick={() => onChange(id)}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden /> {label}
          </button>
        );
      })}
    </nav>
  );
}
