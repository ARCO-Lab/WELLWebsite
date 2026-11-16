// This file defines the Modal component for displaying fullscreen metric/graph views and AI analysis.
// It uses Radix Dialog for modal behavior and conditionally renders AIAnalysis except for 'sampling' type.

import React, { useEffect, useLayoutEffect, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/animations/dialog";
// AI ANALYSIS DISABLED: AI panel in the chart modal (uncomment here and below to restore)
// import AIAnalysis from "./AIAnalysis"; // Make sure this path is correct
import type { Metric } from "@/hooks/useLatestMetrics";
import type { RecentSample } from "@/hooks/useRecentSamples";
import type { SampledData } from "@/hooks/useSampledData";

// Props the modal passes to its content (the metric and graph components accept some or all of them).
interface ModalContentProps {
  modalOpen?: boolean;
  inModal?: boolean;
  weatherTab?: "graph" | "windrose";
  setWeatherTab?: (tab: "graph" | "windrose") => void;
}

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  header?: React.ReactNode; // shown above the content, e.g. the charts' window bar
  // "gauges" and "logger" both mean the water logger graphs (titled "Logger")
  type: "weather" | "logger" | "gauges" | "quality" | "sampling";
  subtypes?: string[];
  analysisType: "recent" | "alltime";
  // What the content shows: latest readings, latest samples or sampling rows (null for the sensor graphs). Not read here
  // while the AI panel is disabled.
  data: Metric[] | RecentSample[] | SampledData[] | null;
  weatherTab?: "graph" | "windrose";
  setWeatherTab?: (tab: "graph" | "windrose") => void;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, header, type, subtypes, analysisType, weatherTab, setWeatherTab }) => {
  // What had focus when the modal opened (a card's "open in a larger view" button), so focus goes back there when
  // it closes. Radix only does that for its own trigger, and this modal is opened from code. A layout effect runs
  // before the dialog moves focus into itself.
  const opener = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    if (isOpen) opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }, [isOpen]);

  useEffect(() => {
    // Close modal on Escape key press
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      {/* Only the body scrolls, and never sideways: the title and the close button stay where they are.
          (When the whole dialog scrolled, wide content dragged the close button off to the side.) */}
      <DialogContent
        aria-describedby={undefined}
        onCloseAutoFocus={(e) => {
          if (opener.current?.isConnected) {
            e.preventDefault();
            opener.current.focus();
          }
        }}
        className="flex max-h-[95vh] max-w-[90vw] flex-col overflow-hidden mcmaster-card max-sm:h-[100dvh] max-sm:max-h-none max-sm:w-screen max-sm:max-w-none max-sm:rounded-none max-sm:p-4">
        <DialogHeader className="shrink-0 pr-10">
          <DialogTitle className="text-2xl font-poppins font-bold text-primary flex items-center justify-between">
            {/* Show group type and context in modal title */}
            {`${type === "gauges" ? "Logger" : type.charAt(0).toUpperCase() + type.slice(1)} ${analysisType === "recent" ? "Metrics" : "Graph"}`}
          </DialogTitle>
        </DialogHeader>
        
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1">
          {header}
          {/* Main content: inject modal props if children is a valid React element. modalOpen is always true here,
              not isOpen: this copy only exists inside the dialog, so if it is still shown while the dialog fades out
              (isOpen already false) it keeps its modal layout rather than switching to the card's (hidden axes). */}
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<ModalContentProps>, { modalOpen: true, inModal: true, weatherTab, setWeatherTab, })
            : children}

          {/* AI ANALYSIS DISABLED: AI panel in the chart modal. Uncomment to restore.
          {type !== 'sampling' && (
            <AIAnalysis
              type={type}
              subtypes={subtypes}
              analysisType={analysisType}
              weatherTab={weatherTab}
              modalOpen={isOpen}
            />
          )}
          */}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default Modal;