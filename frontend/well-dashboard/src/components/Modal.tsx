import React, { useEffect } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Transparent overlay to detect outside click */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 transition-opacity bg-black/40"
      />

      {/* Modal content */}
      <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
        <div
          onClick={(e) => e.stopPropagation()} // prevent inside clicks from closing
          className="relative pointer-events-auto w-[90%] max-w-4xl h-[90vh] max-h-[90vh] overflow-auto bg-white p-6 rounded-lg shadow-lg border border-gray-300"
        >
          {children}
        </div>
      </div>
    </>
  );
};

export default Modal;
