// A short message in place of a chart card's charts when the picked days have no readings at all for what is
// selected, so the card doesn't stand ~500 px tall around empty axes.

import React from "react";

const ChartsEmpty: React.FC = () => (
  <div className="flex min-h-24 items-center justify-center rounded-lg border border-dashed border-gray-300 px-4 py-6 text-center">
    <p className="text-sm text-muted">No readings in this period. Try other days.</p>
  </div>
);

export default ChartsEmpty;
