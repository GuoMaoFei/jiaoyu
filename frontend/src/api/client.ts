import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '../stores/useAuthStore';
import { message } from 'antd';

const baseURL = '/api';

export const apiClient = axios.create({
    baseURL,
    timeout: 90000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// 请求拦截器：注入 Token
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        const token = useAuthStore.getState().token;
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// 响应拦截器：统一错误处理与 Token 刷新逻辑 (待完善自动刷新)
apiClient.interceptors.response.use(
    (response) => response.data,
    (error: AxiosError) => {
        if (error.response) {
            if (error.response.status === 401) {
                useAuthStore.getState().logout();
                message.error('登录已过期，请重新登录');
                window.location.href = '/login';
            } else {
                message.error((error.response.data as any)?.detail || '请求失败');
            }
        } else if (error.request) {
            message.error('网络连接失败，请检查网络设置');
        }
        return Promise.reject(error);
    }
);
