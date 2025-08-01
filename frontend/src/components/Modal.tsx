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
  type: "weather" | "logger" | "quality";
  subtypes?: string[];
  analysisType: "recent" | "alltime";
  data: any;
  weatherTab?: "graph" | "windrose";
  setWeatherTab?: (tab: "graph" | "windrose") => void;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, type, subtypes, analysisType, weatherTab, setWeatherTab }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // All AI analysis state and functions have been moved to the AIAnalysis component.

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[90vw] max-h-[95vh] overflow-y-auto mcmaster-card">
        <DialogHeader>
          <DialogTitle className="text-2xl font-poppins font-bold text-primary flex items-center justify-between">
            {type.charAt(0).toUpperCase() + type.slice(1)} Analysis ({analysisType})
          </DialogTitle>
        </DialogHeader>
        
        <div className="mt-4">
          {/* Main content */}
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<any>, { modalOpen: isOpen, inModal: true, weatherTab, setWeatherTab, })
            : children}

          {/* AI Analysis is now a self-contained component */}
          <AIAnalysis 
            type={type}
            subtypes={subtypes}
            analysisType={analysisType}
            weatherTab={weatherTab}
            modalOpen={isOpen}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default Modal;