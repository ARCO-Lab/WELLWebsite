// This file defines the Modal component for displaying fullscreen metric/graph views and AI analysis.
// It uses Radix Dialog for modal behavior and conditionally renders AIAnalysis except for 'sampling' type.

import React, { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/animations/dialog";
import AIAnalysis from "./AIAnalysis"; // Make sure this path is correct

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  // 1. Add 'sampling' to the allowed types
  type: "weather" | "logger" | "quality" | "sampling";
  subtypes?: string[];
  analysisType: "recent" | "alltime";
  data: any;
  weatherTab?: "graph" | "windrose";
  setWeatherTab?: (tab: "graph" | "windrose") => void;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, type, subtypes, analysisType, weatherTab, setWeatherTab }) => {
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
      <DialogContent className="max-w-[90vw] max-h-[95vh] overflow-y-auto mcmaster-card">
        <DialogHeader>
          <DialogTitle className="text-2xl font-poppins font-bold text-primary flex items-center justify-between">
            {/* Show group type and context in modal title */}
            {`${type === "gauges" /* Error Necessary */ ? "Logger" : type.charAt(0).toUpperCase() + type.slice(1)} ${analysisType === "recent" ? "Metrics" : "Graph"}`}
          </DialogTitle>
        </DialogHeader>
        
        <div className="mt-4">
          {/* Main content: inject modal props if children is a valid React element */}
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<any>, { modalOpen: isOpen, inModal: true, weatherTab, setWeatherTab, })
            : children}

          {/* Conditionally render AI Analysis only if type is NOT 'sampling' */}
          {type !== 'sampling' && (
            <AIAnalysis 
              type={type}
              subtypes={subtypes}
              analysisType={analysisType}
              weatherTab={weatherTab}
              modalOpen={isOpen}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default Modal;