// This file defines the AIAnalysis component for running and displaying AI-generated analysis of environmental data.
// It handles API requests, loading state, and formatting of the AI response for display.

import React, { useState, useEffect } from "react";
import { Button } from "@/components/animations/button";
import { Brain, Loader2 } from "lucide-react";

// Define a type for the complex filter state for the 'complete' analysis
export interface ActiveFilters {
  [group: string]: string[]; // e.g., { gauges: ["All Loggers", "Logger 1"], weather: ["All Weather"] }
}

interface AIAnalysisProps {
  // Props for 'complete' analysis
  analysisType: "recent" | "alltime" | "complete";
  activeFilters?: ActiveFilters;
  dashboardTab?: "sensors" | "sampling";

  // Props for simple 'alltime'/'recent' analysis (used in modals)
  type?: "weather" | "logger" | "quality";
  subtypes?: string[];
  
  // Other props
  weatherTab?: "graph" | "windrose";
  modalOpen?: boolean;
  disabled?: boolean;
}

type AiAnalysisResponse = { analysis: string } | string | null;

const AIAnalysis: React.FC<AIAnalysisProps> = ({
  analysisType: initialAnalysisType,
  activeFilters,
  dashboardTab,
  type,
  subtypes,
  weatherTab,
  modalOpen,
  disabled,
}) => {
  const [tabAnalysis, setTabAnalysis] = useState<{ [tab: string]: AiAnalysisResponse }>({});
  const [tabLoading, setTabLoading] = useState<{ [tab: string]: boolean }>({});
  const [tabRequested, setTabRequested] = useState<{ [tab: string]: boolean }>({});

  const analysisType = !modalOpen ? 'complete' : initialAnalysisType;

  const tab = weatherTab || "graph";

  useEffect(() => {
    // Reset analysis state when dependencies change
    setTabAnalysis({});
    setTabLoading({});
    setTabRequested({});
  }, [type, subtypes, analysisType, weatherTab, modalOpen, activeFilters]);

  const fetchAnalysis = async () => {
    // Build API request and handle loading/response state
    try {
      setTabLoading(prev => ({ ...prev, [tab]: true }));
      setTabRequested(prev => ({ ...prev, [tab]: true }));

      const params = new URLSearchParams();
      let endpoint = '';

      if (analysisType === 'complete') {
        endpoint = '/api/analysis/complete';
        if (!activeFilters || Object.keys(activeFilters).length === 0) {
          // This prevents the "No active groups" error by checking before fetching
          throw new Error("No active filters provided for complete analysis.");
        }

        // Add the dashboard tab state
        if (dashboardTab) {
          params.append('dashboardTab', dashboardTab);
        }

        // Build the new, robust URL
        for (const group in activeFilters) {
          // Append the active group type (e.g., 'type=gauges')
          params.append('type', group);
          
          // Append the subtypes for that specific group with a unique key
          const groupSubtypes = activeFilters[group];
          if (groupSubtypes && groupSubtypes.length > 0) {
            groupSubtypes.forEach(subtype => {
              params.append(`${group}_subtypes`, subtype); // e.g., 'gauges_subtypes=All Loggers'
            });
          }
        }
      } else {
        // --- Existing logic for simple analysis (alltime, recent) ---
        endpoint = `/api/analysis/${analysisType}`;
        if (type) {
          params.append("type", type);
        }
        if (
          analysisType === "alltime" &&
          type === "weather" &&
          weatherTab === "windrose"
        ) {
          endpoint = "/api/analysis/wind";
          const hasWind = subtypes?.some(s => s.toLowerCase().includes("wind speed"));
          const hasGust = subtypes?.some(s => s.toLowerCase().includes("gust speed"));
          if (hasWind) params.append("subtypes", "wind");
          if (hasGust) params.append("subtypes", "gust");
        } else if (subtypes && subtypes.length > 0) {
          subtypes.forEach((s) => params.append("subtypes", s));
        }
      }

      const res = await fetch(`${endpoint}?${params.toString()}`);
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Analysis request failed");
      }
      const json = await res.json();
      setTabAnalysis(prev => ({ ...prev, [tab]: json }));
    } catch (err: any) {
      setTabAnalysis(prev => ({ ...prev, [tab]: err.message || "Failed to load analysis." }));
    } finally {
      setTabLoading(prev => ({ ...prev, [tab]: false }));
    }
  };

  function renderFormattedAnalysis(analysis: string) {
    // Format the AI response into sections and bullet points for display
    const sectionRegex = /\*\*([A-Z -]+):\*\*\s*([\s\S]*?)(?=\n\*\*|$)/g;
    const result = [];
    let match;
  
    while ((match = sectionRegex.exec(analysis)) !== null) {
      const heading = match[1].trim();
      const content = match[2].trim();
  
      result.push(
        <div key={heading} className="mb-4">
          <h4 className="font-poppins font-bold text-base text-accent">{heading}:</h4>
          {content.split('\n').map((line, idx) => {
            const trimmed = line.trim();
            if (!trimmed) return null;
  
            const bulletRegex = /^\s*-\s*\*\*(.+?):\*\*\s*(.+)$/;
            const bulletMatch = bulletRegex.exec(trimmed);
  
            if (bulletMatch) {
              const subsection = bulletMatch[1].trim();
              const description = bulletMatch[2].trim();
  
              return (
                <div key={idx} className="flex items-start text-sm text-white font-poppins mb-1 ml-2">
                  <span className="mr-2">•</span>
                  <span>
                    <span className="font-semibold">{subsection}:</span> {description}
                  </span>
                </div>
              );
            }
  
            const html = trimmed.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
            return (
              <div key={idx} className="text-sm text-white font-poppins mb-1 ml-2" dangerouslySetInnerHTML={{ __html: html }} />
            );
          })}
        </div>
      );
    }
  
    if (result.length === 0) {
      // FIX: Update the fallback regex to match the main one for consistency
      let html = analysis.replace(/\*\*([A-Z &\\-]+):\*\*/g, '<strong class="text-accent">$1:</strong>');
      html = html.replace(/\*\*(.+?):\*\*/g, "<b>$1:</b>");
      return (
        <pre className="whitespace-pre-wrap text-sm text-white font-poppins" dangerouslySetInnerHTML={{ __html: html }} />
      );
    }
  
    return result;
  }
  
  const aiAnalysis = tabAnalysis[tab];
  const loading = tabLoading[tab];
  const analysisRequested = tabRequested[tab];

  return (
    <div className="mt-6 p-4 bg-primary border border-muted rounded">
      {/* Show heading in modal */}
      {modalOpen && <h3 className="text-lg text-white font-poppins font-bold mb-2">AI Analysis</h3>}

      {/* Show analysis or button to trigger analysis */}
      {analysisRequested && !loading ? (
        aiAnalysis && typeof aiAnalysis === "object" && aiAnalysis.analysis
          ? renderFormattedAnalysis(aiAnalysis.analysis)
          : <pre className="text-sm text-white font-poppins whitespace-pre-wrap">{JSON.stringify(aiAnalysis, null, 2)}</pre>
      ) : (
        <Button
          onClick={fetchAnalysis}
          disabled={loading || disabled}
          className={`px-4 py-2 text-sm font-poppins font-semibold text-primary rounded bg-gray-100 flex items-center transition-opacity ${(loading || disabled) ? 'opacity-50 cursor-not-allowed' : 'hover:bg-accent'}`}
        >
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Brain className="mr-2 h-4 w-4" />
          )}
          {loading ? 'Analyzing...' : 'Run AI Analysis'}
        </Button>
      )}
    </div>
  );
};

export default AIAnalysis;