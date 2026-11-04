<<<<<<< HEAD
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
=======
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface AnalystContextValue {
  isOpen: boolean;
  activePropertyId: number | null;
  activePropertyAddress: string | null;
  openAnalyst: (
    propertyId?: number,
    propertyAddress?: string,
    pendingPrompt?: string,
  ) => void;
  closeAnalyst: () => void;
  clearPropertyScope: () => void;
  consumePendingPrompt: () => string | null;
}

const AnalystContext = createContext<AnalystContextValue | null>(null);

export function AnalystProvider({ children }: { children: ReactNode }) {
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a
  const [isOpen, setIsOpen] = useState(false);
  const [activePropertyId, setActivePropertyId] = useState<number | null>(null);
  const [activePropertyAddress, setActivePropertyAddress] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const openAnalyst = useCallback(
<<<<<<< HEAD
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
=======
    (propertyId?: number, propertyAddress?: string, prompt?: string) => {
      if (propertyId !== undefined) {
        setActivePropertyId(propertyId);
        setActivePropertyAddress(propertyAddress ?? null);
      }
      setPendingPrompt(prompt ?? null);
      setIsOpen(true);
    },
    [],
  );

  const closeAnalyst = useCallback(() => setIsOpen(false), []);
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a

  const clearPropertyScope = useCallback(() => {
    setActivePropertyId(null);
    setActivePropertyAddress(null);
  }, []);

  const consumePendingPrompt = useCallback(() => {
<<<<<<< HEAD
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
=======
    const prompt = pendingPrompt;
    setPendingPrompt(null);
    return prompt;
  }, [pendingPrompt]);

  const value = useMemo(
    () => ({
      isOpen,
      activePropertyId,
      activePropertyAddress,
      openAnalyst,
      closeAnalyst,
      clearPropertyScope,
      consumePendingPrompt,
    }),
    [
      isOpen,
      activePropertyId,
      activePropertyAddress,
      openAnalyst,
      closeAnalyst,
      clearPropertyScope,
      consumePendingPrompt,
    ],
  );

  return <AnalystContext.Provider value={value}>{children}</AnalystContext.Provider>;
}

export function useAnalyst(): AnalystContextValue {
  const context = useContext(AnalystContext);
  if (!context) {
    throw new Error("useAnalyst must be used within an AnalystProvider");
  }
  return context;
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a
}
