// A card of independent charts (the water loggers, the weather station, the water quality probe): its heading, and a
// "Link charts in this card" switch, off by default. While it is on, moving or zooming one chart moves the others in
// the card to the same window (useful to line a storm up across loggers); off, each chart keeps its own.

import React, { useState } from "react";
import { ChartLinkContext, ChartLinkGroup } from "@/hooks/useChartWindow";

interface Props {
  title: string;
  chartCount: number; // the switch is shown only when there is more than one chart
  children: React.ReactNode;
  above?: React.ReactNode; // e.g. the weather card's tabs in the larger view
}

const ChartGroup: React.FC<Props> = ({ title, chartCount, children, above }) => {
  const [group] = useState(() => new ChartLinkGroup());
  const [linked, setLinked] = useState(false);
  return (
    <ChartLinkContext.Provider value={group}>
      <div className="@container rounded bg-white p-4 shadow max-sm:p-0 max-sm:shadow-none">
        {above}
        <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <h3 className="text-lg font-bold">{title}</h3>
          {chartCount > 1 && (
            <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 accent-[var(--color-primary,#7a003c)]"
                checked={linked}
                onChange={(e) => {
                  setLinked(e.target.checked);
                  group.setLinked(e.target.checked);
                }}
              />
              Link charts in this card
            </label>
          )}
        </div>
        {children}
      </div>
    </ChartLinkContext.Provider>
  );
};

export default ChartGroup;
