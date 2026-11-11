// This file defines a Calendar component for selecting start and end dates with popover date pickers.
// It uses custom Button, Popover, and Calendar components for consistent UI.

import React, { useEffect, useId, useState } from "react";
import { CalendarIcon } from "lucide-react";
import { Button } from "@/components/animations/button";
import { Calendar as CalendarComponent } from "@/components/animations/calendarPop";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/animations/popover";
import { Label } from "@/components/animations/Label";
import { format } from "date-fns";

interface Props {
  startDate: Date | null | undefined;
  endDate: Date | null | undefined;
  onStartChange: (date: Date | null) => void;
  onEndChange: (date: Date | null) => void;
}

// The first month with data (sensors from 2025-05-08, sampling from 2025-05-01): the month/year dropdowns
// start here, so older months can't be picked by accident.
const DATA_START = new Date(2025, 4, 1);

const Calendar: React.FC<Props> = ({ startDate, endDate, onStartChange, onEndChange }) => {
  const disabledStyles = {
    disabled: { opacity: 0.5 },
  };
  // Today in Toronto wall-clock time, like the default dates, so a viewer in another time zone can still pick
  // the default end date (and its month) late in the evening.
  const today = new Date(new Date().toLocaleString("en-US", { timeZone: "America/Toronto" }));

  // The page is prerendered once at build time, so the server HTML holds the default dates of the build day,
  // while the browser computes them for today. Showing the dates only after mounting keeps the first browser
  // render identical to the server HTML (no React hydration mismatch); the buttons keep their fixed height.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const label = (date: Date | null | undefined) => (!mounted ? "" : date ? format(date, "PPP") : "Pick a date");
  // Each button is named by its label plus its date ("Start Date November 10th, 2026"), so screen readers know
  // which date it is, and it still has a name ("Start Date") while the date is blank. useId keeps the ids unique
  // (this component is on both tabs) and the same on server and browser.
  const id = useId();

  // Shared by both pickers:
  // - fixedWeeks always draws six weeks, so the calendar keeps one size and the arrows stay put while you click
  //   through months (months with five weeks used to shrink it, and a quick click could land outside and close it);
  // - the month and year dropdowns jump straight to an older month;
  // - it opens on the month of the date already picked, and nothing after today can be picked.
  const pickerProps = {
    captionLayout: "dropdown" as const,
    fixedWeeks: true,
    startMonth: DATA_START,
    endMonth: today,
  };

  return (
    <div className="space-y-4">
      {/* Start Date Picker */}
      <div className="space-y-2">
        <Label id={`${id}-start-label`} className="font-poppins font-semibold text-primary">Start Date</Label>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className="w-full justify-start text-left font-normal mcmaster-input"
              aria-labelledby={`${id}-start-label ${id}-start-value`}
            >
              <CalendarIcon className="mr-2 h-4 w-4" aria-hidden="true" />
              <span id={`${id}-start-value`}>{label(startDate)}</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <CalendarComponent
              mode="single"
              required={false}
              selected={startDate || undefined}
              defaultMonth={startDate || undefined}
              onSelect={(date) => onStartChange(date ?? null)}
              disabled={(date) => date > today || (endDate ? date > endDate : false)}
              {...pickerProps}
              modifiersStyles={disabledStyles}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>

      {/* End Date Picker */}
      <div className="space-y-2">
        <Label id={`${id}-end-label`} className="font-poppins font-semibold text-primary">End Date</Label>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className="w-full justify-start text-left font-normal mcmaster-input"
              aria-labelledby={`${id}-end-label ${id}-end-value`}
            >
              <CalendarIcon className="mr-2 h-4 w-4" aria-hidden="true" />
              <span id={`${id}-end-value`}>{label(endDate)}</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <CalendarComponent
              mode="single"
              required={false}
              selected={endDate || undefined}
              defaultMonth={endDate || undefined}
              onSelect={(date) => onEndChange(date ?? null)}
              disabled={(date) => date > today || (startDate ? date < startDate : false)}
              {...pickerProps}
              modifiersStyles={disabledStyles}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
};

export default Calendar;