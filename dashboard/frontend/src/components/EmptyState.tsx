// Shown in a dashboard panel while nothing is selected, so an empty panel explains itself.

import React from "react";
import { MousePointerClick } from "lucide-react";

const EmptyState: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-input-border px-4 py-8 text-center">
    <MousePointerClick aria-hidden className="h-6 w-6 text-muted" />
    <p className="max-w-xs text-sm text-muted">{children}</p>
  </div>
);

export default EmptyState;
