import { create } from 'zustand';
import type { BookshelfItem } from '../types/student';

interface BookshelfStoreState {
    books: BookshelfItem[];
    currentMaterialId: string | null;
    isLoading: boolean;
    setBooks: (books: BookshelfItem[]) => void;
    setCurrentMaterial: (id: string) => void;
    setLoading: (loading: boolean) => void;
}

export const useBookshelfStore = create<BookshelfStoreState>((set) => ({
    books: [],
    currentMaterialId: null,
    isLoading: false,
    setBooks: (books) => set((state) => ({
        books,
        currentMaterialId: state.currentMaterialId || (books.length > 0 ? books[0].material_id : null)
    })),
    setCurrentMaterial: (id) => set({ currentMaterialId: id }),
    setLoading: (loading) => set({ isLoading: loading }),
}));
