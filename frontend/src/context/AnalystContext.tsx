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
  const [isOpen, setIsOpen] = useState(false);
  const [activePropertyId, setActivePropertyId] = useState<number | null>(null);
  const [activePropertyAddress, setActivePropertyAddress] = useState<string | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const openAnalyst = useCallback(
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

  const clearPropertyScope = useCallback(() => {
    setActivePropertyId(null);
    setActivePropertyAddress(null);
  }, []);

  const consumePendingPrompt = useCallback(() => {
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
}
