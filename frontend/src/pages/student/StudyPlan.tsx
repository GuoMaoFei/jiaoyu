import React, { useState, useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Button, Tag, Progress, Breadcrumb, Alert, message, Spin, Modal } from 'antd';
import { ReloadOutlined, CalendarOutlined, AimOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { getStudyPlans, generateStudyPlan } from '../../api/lessons';
import { useAuthStore } from '../../stores/useAuthStore';
import type { PlanItem, TaskType } from '../../types/lesson';

interface DayData {
    date: string;
    tasks: PlanItem[];
}

const TASK_STYLE: Record<TaskType, { color: string; icon: string; tagColor: string }> = {
    LEARN_NEW: { color: 'border-blue-200 bg-blue-50/50', icon: '📖', tagColor: 'blue' },
    DO_QUIZ: { color: 'border-orange-200 bg-orange-50/50', icon: '📝', tagColor: 'orange' },
    REVIEW_VARIANT: { color: 'border-red-200 bg-red-50/50', icon: '🔄', tagColor: 'red' },
};

/** 日历格子 */
function CalendarCell({
    day,
    isSelected,
    onClick,
}: {
    day: DayData;
    isSelected: boolean;
    onClick: () => void;
}) {
    const total = day.tasks.length;
    const completed = day.tasks.filter((t) => t.completed).length;
    const ratio = total > 0 ? completed / total : -1; // -1 = 无任务
    const dateNum = parseInt(day.date.split('-')[2]);

    let bgColor = 'bg-white';
    if (ratio >= 1) bgColor = 'bg-green-100 text-green-800';
    else if (ratio >= 0.5) bgColor = 'bg-yellow-100 text-yellow-800';
    else if (ratio >= 0) bgColor = 'bg-red-50 text-red-700';
    else bgColor = 'bg-slate-50 text-slate-300';

    return (
        <button
            onClick={onClick}
            className={`
        w-full aspect-square rounded-lg flex flex-col items-center justify-center gap-0.5
        text-sm font-medium transition-all cursor-pointer border
        ${bgColor}
        ${isSelected ? 'ring-2 ring-blue-400 border-blue-400 scale-105 shadow' : 'border-transparent hover:border-slate-200'}
      `}
        >
            <span>{dateNum}</span>
            {total > 0 && (
                <span className="text-[10px]">{completed}/{total}</span>
            )}
        </button>
    );
}

const StudyPlan: React.FC = () => {
    const { materialId: materialIdParam } = useParams<{ materialId: string }>();
    const materialId = materialIdParam || "test_material_id_123";
    const { user } = useAuthStore();
    const [monthData, setMonthData] = useState<DayData[]>([]);
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);

    const loadPlans = async () => {
        if (!user) return;
        setLoading(true);
        try {
            const data = await getStudyPlans(user.id);
            // Group items by date
            const daysMap = new Map<string, PlanItem[]>();
            data.items.forEach(item => {
                if (!daysMap.has(item.date)) {
                    daysMap.set(item.date, []);
                }
                daysMap.get(item.date)!.push(item);
            });
            const newMonthData = Array.from(daysMap.entries()).map(([date, tasks]) => ({ date, tasks }));
            // sort by date
            newMonthData.sort((a, b) => a.date.localeCompare(b.date));
            setMonthData(newMonthData);

            // Auto-select today or first day
            if (newMonthData.length > 0 && !selectedDate) {
                const today = new Date().toISOString().split('T')[0];
                const todayData = newMonthData.find(d => d.date === today);
                setSelectedDate(todayData ? today : newMonthData[0].date);
            }
        } catch (error) {
            message.error("无法加载学习计划");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadPlans();
    }, [user]);

    const handleGenerate = async () => {
        if (!user) return;
        setGenerating(true);
        try {
            await generateStudyPlan(user.id, materialId);
            message.success("学习计划生成中...");
            setTimeout(loadPlans, 2000); // 暂定延时重载
        } catch (e) {
            message.error("生成计划失败");
        } finally {
            setGenerating(false);
        }
    };

    const confirmGenerate = () => {
        Modal.confirm({
            title: '需要重新规划吗？',
            content: 'Planner Agent 将会根据您目前的知识掌握情况动态更新接下来的学习计划。',
            onOk: handleGenerate,
            okText: '确认生成',
            cancelText: '取消'
        });
    }

    const selectedDay = useMemo(
        () => monthData.find((d) => d.date === selectedDate) || null,
        [monthData, selectedDate]
    );

    // 总进度
    const totalStats = useMemo(() => {
        const allTasks = monthData.flatMap((d) => d.tasks);
        const total = allTasks.length;
        const completed = allTasks.filter((t) => t.completed).length;
        const totalMinutes = allTasks.filter((t) => t.completed).reduce((sum, t) => sum + t.duration_min, 0);
        return { total, completed, pct: total ? Math.round((completed / total) * 100) : 0, totalMinutes };
    }, [monthData]);

    const weekDays = ['一', '二', '三', '四', '五', '六', '日'];

    return (
        <div className="flex flex-col h-full">
            {/* 顶部 */}
            <div className="px-6 pt-4 pb-3 border-b border-slate-100">
                <Breadcrumb items={[
                    { title: '书架', href: '/bookshelf' },
                    { title: '学习计划' },
                ]} />
                <div className="flex items-center justify-between mt-2">
                    <h1 className="text-xl font-bold text-slate-800">📅 学习计划</h1>
                    <Button
                        icon={<ReloadOutlined />}
                        type="primary"
                        ghost
                        className="rounded-lg"
                        loading={generating}
                        onClick={confirmGenerate}
                    >
                        重新规划
                    </Button>
                </div>
            </div>

            <div className="flex-1 overflow-auto">
                {loading ? (
                    <div className="flex justify-center items-center h-48"><Spin size="large" /></div>
                ) : (
                    <>                {/* 计划元数据 */}
                        <div className="px-6 pt-4 grid grid-cols-3 gap-4">
                            <Card size="small" className="rounded-xl text-center">
                                <AimOutlined className="text-blue-500 text-lg" />
                                <div className="text-sm text-slate-500 mt-1">目标考期</div>
                                <div className="text-lg font-bold text-slate-800">2026-06-15</div>
                            </Card>
                            <Card size="small" className="rounded-xl text-center">
                                <ClockCircleOutlined className="text-green-500 text-lg" />
                                <div className="text-sm text-slate-500 mt-1">总学习时长</div>
                                <div className="text-lg font-bold text-slate-800">{totalStats.totalMinutes} 分钟</div>
                            </Card>
                            <Card size="small" className="rounded-xl text-center">
                                <CalendarOutlined className="text-purple-500 text-lg" />
                                <div className="text-sm text-slate-500 mt-1">总进度</div>
                                <Progress
                                    type="circle"
                                    percent={totalStats.pct}
                                    size={48}
                                    strokeColor={{ '0%': '#3b82f6', '100%': '#22c55e' }}
                                />
                            </Card>
                        </div>

                        {/* 日历热力图 */}
                        <div className="px-6 pt-4">
                            <h3 className="text-sm font-semibold text-slate-700 mb-2">2026 年 3 月</h3>

                            {/* 图例 */}
                            <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-100 inline-block border border-green-200" /> 全完成</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-100 inline-block border border-yellow-200" /> 部分</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-50 inline-block border border-red-100" /> 未开始</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-50 inline-block border border-slate-100" /> 空闲</span>
                            </div>

                            {/* 星期标头 */}
                            <div className="grid grid-cols-7 gap-1.5 mb-1">
                                {weekDays.map((d) => (
                                    <div key={d} className="text-center text-xs text-slate-400 font-medium py-1">{d}</div>
                                ))}
                            </div>

                            {/* 日期格子 */}
                            <div className="grid grid-cols-7 gap-1.5">
                                {/* 3月1日是周日，前6格留空 */}
                                {Array.from({ length: 6 }).map((_, i) => (
                                    <div key={`empty-${i}`} />
                                ))}
                                {monthData.map((day) => (
                                    <CalendarCell
                                        key={day.date}
                                        day={day}
                                        isSelected={selectedDate === day.date}
                                        onClick={() => setSelectedDate(day.date)}
                                    />
                                ))}
                            </div>
                        </div>

                        {/* 当日任务列表 */}
                        <div className="px-6 pt-4 pb-6">
                            {selectedDay ? (
                                <>
                                    <h3 className="text-sm font-semibold text-slate-700 mb-3">
                                        📋 {selectedDay.date} 的任务 ({selectedDay.tasks.filter(t => t.completed).length}/{selectedDay.tasks.length})
                                    </h3>
                                    {selectedDay.tasks.length === 0 ? (
                                        <Alert type="info" showIcon message="此日为空闲日，没有安排任务" />
                                    ) : (
                                        selectedDay.tasks.map((task) => {
                                            const style = TASK_STYLE[task.type];
                                            return (
                                                <div
                                                    key={task.id}
                                                    className={`flex items-center justify-between p-3 mb-2 rounded-xl border ${style.color} transition-all`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <span className="text-lg">{style.icon}</span>
                                                        <div>
                                                            <p className={`text-sm font-medium ${task.completed ? 'line-through text-slate-400' : 'text-slate-800'}`}>
                                                                {task.title}
                                                            </p>
                                                            <p className="text-xs text-slate-400">预计 {task.duration_min} 分钟</p>
                                                        </div>
                                                    </div>
                                                    <Tag color={task.completed ? 'green' : style.tagColor} className="rounded-full">
                                                        {task.completed ? '✅ 已完成' : '待完成'}
                                                    </Tag>
                                                </div>
                                            );
                                        })
                                    )}
                                </>
                            ) : (
                                <div className="text-center text-slate-400 py-8">
                                    👆 点击日历中的某一天查看当日任务
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default StudyPlan;
