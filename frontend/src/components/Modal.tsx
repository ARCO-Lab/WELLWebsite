import React, { useEffect, useState } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  type: "weather" | "logger" | "quality"; // to pass to the analysis API
  subtypes?: string[]; // optional, for future use
  analysisType: "recent" | "alltime"
  data: any;
}

type AiAnalysisResponse = { analysis: string } | string | null;

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, type, subtypes, analysisType}) => {
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

      const res = await fetch(`/api/analysis/${analysisType}?${params.toString()}`);
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
  // Normalize headings: ensure all headings are surrounded by **
  let normalized = analysis.replace(
    /^([A-Z ]{3,}):/gm,
    (_, heading) => `**${heading.trim()}**:`
  );

  // Match headings like **ALERTS:** or **KEY FINDINGS:** and their content
  const regex = /\*\*(.+?)\*\*\s*:?([\s\S]*?)(?=(\*\*|$))/g;
  const result = [];
  let match;
  while ((match = regex.exec(normalized)) !== null) {
    const headingRaw = match[1].trim().replace(/:$/, "");
    const heading = headingRaw.charAt(0).toUpperCase() + headingRaw.slice(1).toLowerCase();
    const content = match[2].trim();
    result.push(
      <div key={heading} className="mb-4">
        <h4 className="font-bold text-base text-black">{heading}</h4>
        <pre className="whitespace-pre-wrap text-sm text-black">{content}</pre>
      </div>
    );
  }
  // If nothing matched, just show the raw analysis
  if (result.length === 0) {
    return <pre className="whitespace-pre-wrap text-sm text-black">{analysis}</pre>;
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
