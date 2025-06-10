import React, { useEffect, useState } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  type: "weather" | "logger" | "quality"; // to pass to the analysis API
  subtypes?: string[]; // optional, for future use
}

type AiAnalysisResponse = { analysis: string } | string | null;

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, type, subtypes }) => {
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalysisResponse>(null);
  const [loading, setLoading] = useState(false);
  const [analysisRequested, setAnalysisRequested] = useState(false);

  const fetchAnalysis = async () => {
    try {
      setLoading(true);
      setAnalysisRequested(true);

      // Build URL
      const params = new URLSearchParams();
      params.append("type", type);
      if (subtypes && subtypes.length > 0) {
        subtypes.forEach((s) => params.append("subtypes", s));
      }

      const res = await fetch(`/api/analysis?${params.toString()}`);
      const json = await res.json();
      setAiAnalysis(json);
    } catch (err) {
      console.error("Failed to fetch AI analysis:", err);
      setAiAnalysis("Failed to load analysis.");
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    // Reset analysis state whenever the type or selected metrics change
    setAiAnalysis(null);
    setAnalysisRequested(false);
    setLoading(false);
  }, [type, subtypes]);

  function renderFormattedAnalysis(analysis: string) {
    // Split by headings like **TRENDS**
    const sections = analysis.split(/\*\*(.*?)\*\*/g).filter(Boolean);

    // sections will be like: ["TRENDS", "\n- ...", "CORRELATIONS", "\n- ...", ...]
    const result = [];
    for (let i = 0; i < sections.length; i += 2) {
      const heading = sections[i]?.trim();
      const content = sections[i + 1]?.trim();
      if (heading && content) {
        result.push(
          <div key={heading} className="mb-4">
            <h4 className="font-semibold text-black">{heading.charAt(0) + heading.slice(1).toLowerCase()}:</h4>
            <pre className="whitespace-pre-wrap text-sm text-black">{content}</pre>
          </div>
        );
      }
    }
    return result;
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 transition-opacity bg-black/40"
      />

      {/* Modal content */}
      <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
        <div
          onClick={(e) => e.stopPropagation()}
          className="relative pointer-events-auto bg-white p-6 rounded-lg shadow-lg border border-gray-300
          w-full h-full max-w-[calc(100vw-40px)] max-h-[calc(100vh-40px)] m-0 overflow-y-auto"
        >
          {/* Main content */}
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<any>, { modalOpen: isOpen })
            : children}

          {/* AI Analysis trigger & output */}
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded">
            <h3 className="text-md text-black font-bold mb-2">AI Analysis</h3>

            {!analysisRequested ? (
              <button
                onClick={fetchAnalysis}
                className="px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded hover:bg-blue-700"
              >
                Run AI Analysis
              </button>
            ) : loading ? (
              <p className="text-sm text-gray-600">Analyzing data...</p>
            ) : (
              aiAnalysis && typeof aiAnalysis === "object" && aiAnalysis.analysis
                ? renderFormattedAnalysis(aiAnalysis.analysis)
                : <pre className="text-sm text-gray-800 whitespace-pre-wrap">{JSON.stringify(aiAnalysis, null, 2)}</pre>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default Modal;
