import React, { useState } from 'react';
import { Card, Form, Input, Button, message } from 'antd';
import { useNavigate, Link } from 'react-router-dom';
import { UserOutlined, LockOutlined, PhoneOutlined } from '@ant-design/icons';
import { registerParent } from '../../api/auth';

const Register: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleFinish = async (values: any) => {
        setLoading(true);
        try {
            const res = await registerParent(
                values.phone_number,
                values.password,
                values.nickname
            );
            message.success('注册成功！请登录');
            navigate('/login');
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
                    <h1 className="text-2xl font-bold text-gray-800">家长注册</h1>
                    <p className="text-gray-500">创建家长账户，与孩子一起成长</p>
                </div>
                <Form
                    layout="vertical"
                    onFinish={handleFinish}
                    autoComplete="off"
                >
                    <Form.Item
                        name="phone_number"
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
                            placeholder="密码（至少6位）"
                            size="large"
                        />
                    </Form.Item>
                    <Form.Item
                        name="nickname"
                    >
                        <Input
                            prefix={<UserOutlined />}
                            placeholder="昵称（选填）"
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
                            注册
                        </Button>
                    </Form.Item>
                </Form>
                <div className="text-center mt-4">
                    <span className="text-gray-500">
                        已有账户？{' '}
                        <Link to="/login" className="text-blue-600 hover:text-blue-500">
                            登录
                        </Link>
                    </span>
                </div>
            </Card>
        </div>
    );
};

export default Register;
