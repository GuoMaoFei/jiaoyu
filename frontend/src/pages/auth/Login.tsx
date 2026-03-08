import React, { useState } from 'react';
import { Card, Form, Input, Button, Tabs, message } from 'antd';
import { useAuthStore } from '../../stores/useAuthStore';
import { useNavigate, useLocation } from 'react-router-dom';
import { UserOutlined, LockOutlined, PhoneOutlined } from '@ant-design/icons';
import { login } from '../../api/auth';

const Login: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const setAuth = useAuthStore((state) => state.setAuth);
    const navigate = useNavigate();
    const location = useLocation();

    const handleFinish = async (values: any) => {
        setLoading(true);
        try {
            // 调用真实后端登录接口
            const username = values.username || values.phone;
            const password = values.password || 'default_demo_pwd';
            const res = await login(username, password);

            setAuth(res.access_token, {
                id: res.user_id,
                name: res.nickname,
                role: 'student',
                grade: undefined, // no longer returned by auth MVP logic
            });
            message.success('登录成功！');
            const from = (location.state as any)?.from?.pathname || '/bookshelf';
            navigate(from, { replace: true });
        } catch (e: any) {
            // 错误已在拦截器中处理，或者可以在这里通过 e.response.data 解析
            console.error('Login failed:', e);
        } finally {
            // 模拟延迟后关闭
            setTimeout(() => setLoading(false), 800);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
            <div className="sm:mx-auto sm:w-full sm:max-w-md">
                <h2 className="mt-6 text-center text-3xl font-extrabold text-slate-900">
                    智树 TreeEdu
                </h2>
                <p className="mt-2 text-center text-sm text-slate-600">
                    陪伴式 AI 学习导师
                </p>
            </div>

            <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
                <Card className="shadow-lg border-0 rounded-xl mx-4 sm:mx-0">
                    <Tabs defaultActiveKey="1" centered items={[
                        {
                            key: '1',
                            label: '账号密码登录',
                            children: (
                                <Form
                                    name="login_pwd"
                                    onFinish={handleFinish}
                                    layout="vertical"
                                    size="large"
                                    className="mt-4"
                                >
                                    <Form.Item
                                        name="username"
                                        rules={[{ required: true, message: '请输入账号！' }]}
                                    >
                                        <Input prefix={<UserOutlined className="text-slate-400" />} placeholder="手机号/账号" />
                                    </Form.Item>
                                    <Form.Item
                                        name="password"
                                        rules={[{ required: true, message: '请输入密码！' }]}
                                    >
                                        <Input.Password prefix={<LockOutlined className="text-slate-400" />} placeholder="密码" />
                                    </Form.Item>
                                    <Form.Item>
                                        <Button
                                            type="primary"
                                            htmlType="submit"
                                            loading={loading}
                                            className="w-full bg-primary-600 hover:bg-primary-500 font-medium"
                                        >
                                            登录
                                        </Button>
                                    </Form.Item>
                                </Form>
                            )
                        },
                        {
                            key: '2',
                            label: '验证码登录',
                            children: (
                                <Form
                                    name="login_code"
                                    onFinish={handleFinish}
                                    layout="vertical"
                                    size="large"
                                    className="mt-4"
                                >
                                    <Form.Item
                                        name="phone"
                                        rules={[{ required: true, message: '请输入手机号！' }]}
                                    >
                                        <Input prefix={<PhoneOutlined className="text-slate-400" />} placeholder="手机号" />
                                    </Form.Item>
                                    <Form.Item className="mb-0">
                                        <div className="flex gap-2">
                                            <Form.Item
                                                name="code"
                                                rules={[{ required: true, message: '请输入验证码！' }]}
                                                className="flex-1 mb-6"
                                            >
                                                <Input prefix={<LockOutlined className="text-slate-400" />} placeholder="验证码" />
                                            </Form.Item>
                                            <Button size="large">获取验证码</Button>
                                        </div>
                                    </Form.Item>
                                    <Form.Item>
                                        <Button
                                            type="primary"
                                            htmlType="submit"
                                            loading={loading}
                                            className="w-full bg-primary-600 hover:bg-primary-500 font-medium"
                                        >
                                            登录
                                        </Button>
                                    </Form.Item>
                                </Form>
                            )
                        }
                    ]} />

                    <div className="text-center mt-4">
                        <a href="/register" className="text-sm text-primary-600 hover:text-primary-500">
                            注册学生账号
                        </a>
                        <span className="mx-2 text-slate-300">|</span>
                        <a href="/parent/bindx" className="text-sm text-primary-600 hover:text-primary-500">
                            家长绑定入口
                        </a>
                    </div>
                </Card>
            </div>
        </div>
    );
};

export default Login;
