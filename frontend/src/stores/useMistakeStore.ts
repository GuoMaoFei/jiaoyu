import { create } from 'zustand';
import { type StudentMistake, type MistakeStatus } from '../types/mistake';

interface MistakeStoreState {
    mistakes: StudentMistake[];
    filterStatus: MistakeStatus | 'ALL';
    filterMaterialId: string | null;
    isLoading: boolean;
    setMistakes: (mistakes: StudentMistake[]) => void;
    setFilterStatus: (status: MistakeStatus | 'ALL') => void;
    setFilterMaterialId: (id: string | null) => void;
    setLoading: (loading: boolean) => void;
}

export const useMistakeStore = create<MistakeStoreState>((set) => ({
    mistakes: [],
    filterStatus: 'ALL',
    filterMaterialId: null,
    isLoading: false,
    setMistakes: (mistakes) => set({ mistakes }),
    setFilterStatus: (status) => set({ filterStatus: status }),
    setFilterMaterialId: (id) => set({ filterMaterialId: id }),
    setLoading: (loading) => set({ isLoading: loading }),
}));
