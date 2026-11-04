import React, { createContext, useContext, useState, useCallback } from "react";

interface AnalystContextType {
  isOpen: boolean;
  activePropertyId: number | null;
  activePropertyAddress: string | null;
  openAnalyst: (propertyId?: number | null, address?: string | null, initialPrompt?: string) => void;
  closeAnalyst: () => void;
  clearPropertyScope: () => void;
  pendingPrompt: string | null;
  consumePendingPrompt: () => string | null;
}

const AnalystContext = createContext<AnalystContextType | undefined>(undefined);

export function AnalystProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activePropertyId, setActivePropertyId] = useState<number | null>(null);
  const [activePropertyAddress, setActivePropertyAddress] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const openAnalyst = useCallback(
    (propertyId?: number | null, address?: string | null, initialPrompt?: string) => {
      if (propertyId != null) {
        setActivePropertyId(propertyId);
        setActivePropertyAddress(address || `Lot #${propertyId}`);
      }
      if (initialPrompt) {
        setPendingPrompt(initialPrompt);
      }
      setIsOpen(true);
    },
    []
  );

  const closeAnalyst = useCallback(() => {
    setIsOpen(false);
  }, []);

  const clearPropertyScope = useCallback(() => {
    setActivePropertyId(null);
    setActivePropertyAddress(null);
  }, []);

  const consumePendingPrompt = useCallback(() => {
    const p = pendingPrompt;
    setPendingPrompt(null);
    return p;
  }, [pendingPrompt]);

  return (
    <AnalystContext.Provider
      value={{
        isOpen,
        activePropertyId,
        activePropertyAddress,
        openAnalyst,
        closeAnalyst,
        clearPropertyScope,
        pendingPrompt,
        consumePendingPrompt,
      }}
    >
      {children}
    </AnalystContext.Provider>
  );
}

export function useAnalyst() {
  const ctx = useContext(AnalystContext);
  if (!ctx) {
    throw new Error("useAnalyst must be used within an AnalystProvider");
  }
  return ctx;
}
