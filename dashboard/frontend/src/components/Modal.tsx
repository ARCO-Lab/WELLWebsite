// This file defines the Modal component for displaying fullscreen metric/graph views and AI analysis.
// It uses Radix Dialog for modal behavior and conditionally renders AIAnalysis except for 'sampling' type.

import React, { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/animations/dialog";
// AI ANALYSIS DISABLED: AI panel in the chart modal (uncomment here and below to restore)
// import AIAnalysis from "./AIAnalysis"; // Make sure this path is correct

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  header?: React.ReactNode; // shown above the content, e.g. the charts' window bar
  // "gauges" and "logger" both mean the water logger graphs (titled "Logger")
  type: "weather" | "logger" | "gauges" | "quality" | "sampling";
  subtypes?: string[];
  analysisType: "recent" | "alltime";
  data: any;
  weatherTab?: "graph" | "windrose";
  setWeatherTab?: (tab: "graph" | "windrose") => void;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, header, type, subtypes, analysisType, weatherTab, setWeatherTab }) => {
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
      <DialogContent aria-describedby={undefined} className="flex max-h-[95vh] max-w-[90vw] flex-col overflow-hidden mcmaster-card max-sm:h-[100dvh] max-sm:max-h-none max-sm:w-screen max-sm:max-w-none max-sm:rounded-none max-sm:p-4">
        <DialogHeader className="shrink-0 pr-10">
          <DialogTitle className="text-2xl font-poppins font-bold text-primary flex items-center justify-between">
            {/* Show group type and context in modal title */}
            {`${type === "gauges" ? "Logger" : type.charAt(0).toUpperCase() + type.slice(1)} ${analysisType === "recent" ? "Metrics" : "Graph"}`}
          </DialogTitle>
        </DialogHeader>
        
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1">
          {header}
          {/* Main content: inject modal props if children is a valid React element */}
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<any>, { modalOpen: isOpen, inModal: true, weatherTab, setWeatherTab, })
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