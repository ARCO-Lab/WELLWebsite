// This file defines a Calendar component for selecting start and end dates with popover date pickers.
// It uses custom Button, Popover, and Calendar components for consistent UI.

import React from "react";
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
  const today = new Date();

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
        <Label className="font-poppins font-semibold text-primary">Start Date</Label>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className="w-full justify-start text-left font-normal mcmaster-input"
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {startDate ? format(startDate, "PPP") : "Pick a date"}
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
        <Label className="font-poppins font-semibold text-primary">End Date</Label>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className="w-full justify-start text-left font-normal mcmaster-input"
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {endDate ? format(endDate, "PPP") : "Pick a date"}
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