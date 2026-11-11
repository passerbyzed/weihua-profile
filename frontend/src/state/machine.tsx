import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { listMachines } from '../api/client';
import type { Machine } from '../types';

interface MachineContextValue {
  machines: Machine[];
  current: string;
  setCurrent: (value: string) => void;
  loading: boolean;
  machine: Machine | null;
}

const MachineContext = createContext<MachineContextValue | null>(null);

const STORAGE_KEY = 'qb_current_machine';

export function MachineProvider({ children }: { children: ReactNode }) {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [current, setCurrentState] = useState<string>(
    () => localStorage.getItem(STORAGE_KEY) || 'LD5-2024-0316'
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMachines()
      .then((list) => {
        setMachines(list);
        if (list.length && !list.some((m) => m.product_no === current)) {
          setCurrentState(list[0].product_no);
        }
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setCurrent = (value: string) => {
    setCurrentState(value);
    localStorage.setItem(STORAGE_KEY, value);
  };

  const machine = useMemo(
    () => machines.find((m) => m.product_no === current) ?? null,
    [machines, current]
  );

  return (
    <MachineContext.Provider value={{ machines, current, setCurrent, loading, machine }}>
      {children}
    </MachineContext.Provider>
  );
}

export function useMachines(): MachineContextValue {
  const ctx = useContext(MachineContext);
  if (!ctx) throw new Error('useMachines 必须在 MachineProvider 内使用');
  return ctx;
}
