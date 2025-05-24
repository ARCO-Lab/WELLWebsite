import React, { useState } from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

interface Props {
  startDate: Date | null | undefined;
  endDate: Date | null | undefined;
  onStartChange: (date: Date | null) => void;
  onEndChange: (date: Date | null) => void;
};

const Calendar: React.FC<Props> = ({ startDate, endDate, onStartChange, onEndChange }) => {
  return (
    <div className="flex flex-col">
      <div className="flex flex-col gap-2 md:flex-row">
        <div className="flex items-center flex-1 space-x-2">
          <label className="font-medium text-gray-800">From:</label>
          <DatePicker
            selected={startDate}
            onChange={onStartChange}
            selectsStart
            startDate={startDate}
            endDate={endDate}
            className="w-full p-2 border rounded"
          />
        </div>
        <div className="flex items-center flex-1 space-x-2">
          <label className="font-medium text-gray-800">To:</label>
          <DatePicker
            selected={endDate}
            onChange={onEndChange}
            selectsEnd
            startDate={startDate || undefined}
            endDate={endDate || undefined}
            minDate={startDate || undefined}
            className="w-full p-2 border rounded"
          />
        </div>
      </div>
    </div>
  );
};

export default Calendar;
