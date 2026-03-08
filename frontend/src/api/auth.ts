import { apiClient } from './client';

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user_id: string;
    nickname: string;
    role: string;
}

export interface RegisterRequest {
    phone_number: string;
    password: string;
    nickname?: string;
}

export const login = (username: string, password?: string, role: string = 'student') =>
    apiClient.post<any, LoginResponse>('/auth/login', { username, password, role });

export const registerParent = (phone_number: string, password: string, nickname?: string) =>
    apiClient.post<any, LoginResponse>('/auth/register/parent', { 
        phone_number, 
        password, 
        nickname 
    });
