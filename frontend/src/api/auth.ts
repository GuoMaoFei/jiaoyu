import { apiClient } from './client';

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user_id: string;
    nickname: string;
    role: string;
}

/** 简单登录 (返回 Token 与用户基础信息) */
export const login = (username: string, password?: string, role: string = 'student') =>
    apiClient.post<any, LoginResponse>('/auth/login', { username, password, role });
