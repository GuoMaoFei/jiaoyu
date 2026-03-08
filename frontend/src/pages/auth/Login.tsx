import React, { useState } from 'react';
import { Card, Form, Input, Button, Tabs, message } from 'antd';
import { useAuthStore } from '../../stores/useAuthStore';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { UserOutlined, LockOutlined, PhoneOutlined } from '@ant-design/icons';
import { login } from '../../api/auth';

const Login: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('student');
    const setAuth = useAuthStore((state) => state.setAuth);
    const navigate = useNavigate();
    const location = useLocation();

    const handleFinish = async (values: any) => {
        setLoading(true);
        try {
            const username = values.username || values.phone;
            const password = values.password || undefined;
            const role = activeTab;
            const res = await login(username, password, role);

            setAuth(res.access_token, {
                id: res.user_id,
                name: res.nickname,
                role: res.role as 'student' | 'parent' | 'admin',
                grade: undefined,
            });
            message.success('登录成功！');
            const from = (location.state as any)?.from?.pathname || '/bookshelf';
            navigate(from, { replace: true });
        } catch (e: any) {
            // 错误已在拦截器中处理
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
            <Card className="w-full max-w-md shadow-xl">
                <div className="text-center mb-6">
                    <h1 className="text-2xl font-bold text-gray-800">TreeEdu Agent</h1>
                    <p className="text-gray-500">智能教育平台</p>
                </div>
                
                <Tabs
                    activeKey={activeTab}
                    onChange={(key) => setActiveTab(key)}
                    centered
                    items={[
                        {
                            key: 'student',
                            label: '学生登录',
                            children: (
                                <Form
                                    layout="vertical"
                                    onFinish={handleFinish}
                                    autoComplete="off"
                                >
                                    <Form.Item
                                        name="username"
                                        rules={[{ required: true, message: '请输入用户名' }]}
                                    >
                                        <Input
                                            prefix={<UserOutlined />}
                                            placeholder="用户名"
                                            size="large"
                                        />
                                    </Form.Item>
                                    <Form.Item
                                        name="password"
                                    >
                                        <Input.Password
                                            prefix={<LockOutlined />}
                                            placeholder="密码（选填）"
                                            size="large"
                                        />
                                    </Form.Item>
                                    <Form.Item>
                                        <Button
                                            type="primary"
                                            htmlType="submit"
                                            loading={loading}
                                            block
                                            size="large"
                                        >
                                            登录
                                        </Button>
                                    </Form.Item>
                                </Form>
                            ),
                        },
                        {
                            key: 'parent',
                            label: '家长登录',
                            children: (
                                <Form
                                    layout="vertical"
                                    onFinish={handleFinish}
                                    autoComplete="off"
                                >
                                    <Form.Item
                                        name="phone"
                                        rules={[
                                            { required: true, message: '请输入手机号' },
                                            { pattern: /^1[3-9]\d{9}$/, message: '请输入有效的手机号' },
                                        ]}
                                    >
                                        <Input
                                            prefix={<PhoneOutlined />}
                                            placeholder="手机号"
                                            size="large"
                                        />
                                    </Form.Item>
                                    <Form.Item
                                        name="password"
                                        rules={[
                                            { required: true, message: '请输入密码' },
                                            { min: 6, message: '密码至少6位' },
                                        ]}
                                    >
                                        <Input.Password
                                            prefix={<LockOutlined />}
                                            placeholder="密码"
                                            size="large"
                                        />
                                    </Form.Item>
                                    <Form.Item>
                                        <Button
                                            type="primary"
                                            htmlType="submit"
                                            loading={loading}
                                            block
                                            size="large"
                                        >
                                            登录
                                        </Button>
                                    </Form.Item>
                                </Form>
                            ),
                        },
                    ]}
                />

                <div className="text-center mt-4 pb-4">
                    <span className="text-gray-500">
                        家长没有账户？{' '}
                        <Link to="/register" className="text-blue-600 hover:text-blue-500">
                            立即注册
                        </Link>
                    </span>
                </div>
            </Card>
        </div>
    );
};

export default Login;
