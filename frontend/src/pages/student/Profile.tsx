import React, { useEffect, useState } from 'react';
import { Card, Progress, Spin, Alert, Statistic, Row, Col, Avatar, Tag } from 'antd';
import {
    UserOutlined,
    BookOutlined,
    ExperimentOutlined,
    TrophyOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../stores/useAuthStore';
import { getStudentProfile } from '../../api/students';
import type { StudentProfile as StudentProfileType } from '../../types/student';

const Profile: React.FC = () => {
    const user = useAuthStore((s) => s.user);
    const [profile, setProfile] = useState<StudentProfileType | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!user?.id) return;
        setLoading(true);
        getStudentProfile(user.id)
            .then((data: any) => {
                setProfile(data);
                setError(null);
            })
            .catch((e) => {
                setError(e.response?.data?.detail || '无法获取个人档案数据');
            })
            .finally(() => setLoading(false));
    }, [user?.id]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Spin size="large" tip="加载学习档案…" />
            </div>
        );
    }

    if (!profile) return null;

    const healthColor = profile.avg_health_score! > 85 ? '#22c55e' : profile.avg_health_score! >= 60 ? '#eab308' : '#ef4444';

    return (
        <div className="flex flex-col h-full overflow-auto">
            <div className="px-6 pt-4 pb-3 border-b border-slate-100">
                <h1 className="text-xl font-bold text-slate-800">👤 个人中心</h1>
            </div>

            {error && (
                <div className="mx-6 mt-3">
                    <Alert type="info" showIcon message={error} closable />
                </div>
            )}

            <div className="px-6 py-6 max-w-3xl mx-auto w-full">
                {/* 头像卡片 */}
                <Card className="rounded-xl mb-6 overflow-hidden">
                    <div className="flex items-center gap-5">
                        <Avatar
                            size={72}
                            icon={<UserOutlined />}
                            className="bg-gradient-to-br from-blue-400 to-indigo-500 shadow-lg"
                        />
                        <div>
                            <h2 className="text-xl font-bold text-slate-800">{profile.nickname}</h2>
                            <div className="flex items-center gap-3 mt-1">
                                <Tag color="blue" className="rounded-full">{profile.grade}</Tag>
                                <span className="text-sm text-slate-500">学习旅程进行中 🌱</span>
                            </div>
                        </div>
                    </div>
                </Card>

                {/* 学习仪表盘 */}
                <Card title="📈 学习仪表盘" className="rounded-xl mb-6">
                    <Row gutter={[24, 24]} justify="center">
                        <Col span={6} className="text-center">
                            <Progress
                                type="dashboard"
                                percent={profile.avg_health_score}
                                strokeColor={healthColor}
                                format={(pct) => <span style={{ color: healthColor, fontWeight: 'bold' }}>{pct}</span>}
                                size={80}
                            />
                            <div className="text-xs text-slate-500 mt-1">平均健康度</div>
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title="已学节点"
                                value={profile.total_nodes_studied}
                                prefix={<BookOutlined className="text-blue-500" />}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title="活跃错题"
                                value={profile.active_mistakes_count}
                                prefix={<ExperimentOutlined className="text-red-500" />}
                                valueStyle={{ color: profile.active_mistakes_count! > 0 ? '#ef4444' : '#22c55e' }}
                            />
                        </Col>
                        <Col span={6}>
                            <Statistic
                                title="成就徽章"
                                value={3}
                                prefix={<TrophyOutlined className="text-amber-500" />}
                            />
                        </Col>
                    </Row>
                </Card>

                {/* 薄弱知识点 */}
                {profile.weak_nodes && profile.weak_nodes.length > 0 && (
                    <Card title="⚠️ 薄弱知识点 TOP 3" className="rounded-xl mb-6">
                        {profile.weak_nodes.map((node) => {
                            const color = node.health_score > 85 ? '#22c55e' : node.health_score >= 60 ? '#eab308' : '#ef4444';
                            return (
                                <div key={node.node_id} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                                    <span className="text-sm text-slate-700">{node.node_title || node.node_id}</span>
                                    <div className="flex items-center gap-3">
                                        <Progress
                                            percent={node.health_score}
                                            strokeColor={color}
                                            size="small"
                                            className="w-24"
                                            format={(pct) => <span className="text-xs">{pct}</span>}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </Card>
                )}

                {/* 学习成就 */}
                <Card title="🏆 学习成就" className="rounded-xl">
                    <div className="flex gap-4 flex-wrap">
                        {[
                            { icon: '🔥', label: '连续学习 7 天', color: 'bg-orange-50 border-orange-200' },
                            { icon: '🌟', label: '全等三角形一把通', color: 'bg-blue-50 border-blue-200' },
                            { icon: '📚', label: '点亮 10 个知识点', color: 'bg-green-50 border-green-200' },
                        ].map((badge) => (
                            <div
                                key={badge.label}
                                className={`flex items-center gap-2 px-4 py-2 rounded-xl border ${badge.color} text-sm text-slate-700`}
                            >
                                <span className="text-lg">{badge.icon}</span>
                                {badge.label}
                            </div>
                        ))}
                    </div>
                </Card>
            </div>
        </div>
    );
};

export default Profile;
