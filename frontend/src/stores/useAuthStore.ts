import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { type AuthState } from '../types/auth';

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            token: null,
            user: null,
            isAuthenticated: false,
            setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
            logout: () => set({ token: null, user: null, isAuthenticated: false }),
        }),
        {
            name: 'tree-edu-auth', // 存在 localStorage 中的 key
        }
    )
);
