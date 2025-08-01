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

const Calendar: React.FC<Props> = ({ startDate, endDate, onStartChange, onEndChange }) => {
  const disabledStyles = {
    disabled: { opacity: 0.5 },
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
              selected={startDate || undefined}
              onSelect={onStartChange}
              disabled={(date) => (endDate ? date > endDate : false)}
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
              selected={endDate || undefined}
              onSelect={onEndChange}
              disabled={(date) => (startDate ? date < startDate : false)}
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