export interface User {
    id: string;
    name: string;
    role: 'student' | 'parent' | 'admin';
    grade?: string;
}

export interface AuthState {
    token: string | null;
    user: User | null;
    isAuthenticated: boolean;
    setAuth: (token: string, user: User) => void;
    logout: () => void;
}
