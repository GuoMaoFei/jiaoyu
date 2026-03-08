import React from 'react';
import { Card, Statistic, Row, Col, Progress, Button } from 'antd';
import { BookOutlined, RocketOutlined, ClockCircleOutlined, TrophyOutlined, ExperimentOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useBookshelfStore } from '../../stores/useBookshelfStore';

const TodayTasks: React.FC = () => {
    const navigate = useNavigate();
    const { currentMaterialId } = useBookshelfStore();
    const safeMaterialId = currentMaterialId || 'demo-material-id';

    return (
        <div className="p-6">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-800">早安，伴读小神仙！</h1>
                    <p className="text-slate-500 mt-1">
                        2026年2月28日 · 周六 | 这是你坚持学习的第 <strong>29</strong> 天
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    <Statistic title="今日学习时常" value={25} suffix="分钟" prefix={<ClockCircleOutlined />} />
                    <div className="w-px h-10 bg-slate-200" />
                    <Statistic title="获得知识点" value={13} prefix={<TrophyOutlined className="text-yellow-500" />} />
                </div>
            </div>

            <Row gutter={[24, 24]}>
                <Col xs={24} md={16}>
                    <Card title="🎯 今日智能推卷" className="shadow-sm border-slate-100 rounded-xl h-full" extra={<a onClick={() => navigate('/plan')}>全量计划</a>}>
                        <div className="space-y-4">

                            {/* 学习新知 → 学习舱 */}
                            <div className="flex items-center p-4 border border-blue-100 bg-blue-50/50 rounded-lg hover:bg-blue-50 transition-colors cursor-pointer" onClick={() => navigate(`/cabin/${safeMaterialId}`)}>
                                <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 mr-4">
                                    <BookOutlined className="text-xl" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-semibold text-slate-800">学习新知：全等三角形的概念</h3>
                                    <p className="text-sm text-slate-500">初二数学上册 · 预计 15 分钟</p>
                                </div>
                                <Button type="primary" shape="round">开始学习</Button>
                            </div>

                            {/* 知识巩固 → 考试 */}
                            <div className="flex items-center p-4 border border-orange-100 bg-orange-50/50 rounded-lg hover:bg-orange-50 transition-colors cursor-pointer" onClick={() => navigate(`/exam/${safeMaterialId}`)}>
                                <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 mr-4">
                                    <RocketOutlined className="text-xl" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-semibold text-slate-800">知识巩固：判定定理微测</h3>
                                    <p className="text-sm text-slate-500">变式出题机发起 · 3 道题</p>
                                </div>
                                <Button type="default" shape="round" className="border-orange-200 text-orange-600">接受测验</Button>
                            </div>

                            {/* 入学诊断 → 诊断 */}
                            <div className="flex items-center p-4 border border-purple-100 bg-purple-50/50 rounded-lg hover:bg-purple-50 transition-colors cursor-pointer" onClick={() => navigate(`/diagnostic/${safeMaterialId}`)}>
                                <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center text-purple-600 mr-4">
                                    <ExperimentOutlined className="text-xl" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-semibold text-slate-800">入学诊断：全量摸底测试</h3>
                                    <p className="text-sm text-slate-500">快速定位知识薄弱点 · 约 10 分钟</p>
                                </div>
                                <Button type="default" shape="round" className="border-purple-200 text-purple-600">开始诊断</Button>
                            </div>

                        </div>
                    </Card>
                </Col>

                {/* 侧边仪表盘 */}
                <Col xs={24} md={8}>
                    <Card className="shadow-sm border-slate-100 rounded-xl h-full flex flex-col justify-center items-center text-center">
                        <Progress type="dashboard" percent={75} strokeColor="#3b82f6" />
                        <h3 className="mt-4 font-semibold text-slate-700">这周计划达成率 75%</h3>
                        <p className="text-sm text-slate-400 mt-2 px-4 mb-4">
                            还差一节课就可以解锁本周的【勤学王者】徽章啦！
                        </p>
                        <Button className="font-medium text-primary-600" type="dashed" block onClick={() => navigate('/report')}>查看学情周报</Button>
                    </Card>
                </Col>
            </Row>
        </div>
    );
};

export default TodayTasks;
