import React, { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Tag, Progress, Breadcrumb, Alert, message, Spin, Modal } from 'antd';
import { ReloadOutlined, CalendarOutlined, AimOutlined, ClockCircleOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { getStudyPlans, generateStudyPlan, clearStudyPlans, startLesson } from '../../api/lessons';
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

const StudyPlan: React.FC = () => {
    const { materialId: materialIdParam } = useParams<{ materialId: string }>();
    const materialId = materialIdParam || "test_material_id_123";
    const { user } = useAuthStore();
    const navigate = useNavigate();
    
    const [allTasks, setAllTasks] = useState<PlanItem[]>([]);
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [currentMonth, setCurrentMonth] = useState(() => {
        const now = new Date();
        return { year: now.getFullYear(), month: now.getMonth() + 1 };
    });
    const [dateRange, setDateRange] = useState<{ start?: string; end?: string }>({});

    const loadPlans = async () => {
        if (!user) return;
        setLoading(true);
        try {
            const data = await getStudyPlans(user.id);
            setAllTasks(data.items);
            setDateRange({ start: data.start_date, end: data.end_date });
            
            if (data.items.length > 0) {
                const firstDate = new Date(data.items[0].date);
                setCurrentMonth({ year: firstDate.getFullYear(), month: firstDate.getMonth() + 1 });
            }
            
            const today = new Date().toISOString().split('T')[0];
            const todayTask = data.items.find(t => t.date === today);
            if (todayTask) {
                setSelectedDate(today);
            } else if (data.items.length > 0) {
                setSelectedDate(data.items[0].date);
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
            await clearStudyPlans(user.id);
            const today = new Date().toISOString().split('T')[0];
            await generateStudyPlan(user.id, materialId, today);
            message.success("学习计划生成中...");
            setTimeout(loadPlans, 2000);
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

    const monthData = useMemo(() => {
        const daysMap = new Map<string, PlanItem[]>();
        allTasks.forEach(item => {
            if (!daysMap.has(item.date)) {
                daysMap.set(item.date, []);
            }
            daysMap.get(item.date)!.push(item);
        });
        return Array.from(daysMap.entries())
            .map(([date, tasks]) => ({ date, tasks }))
            .sort((a, b) => a.date.localeCompare(b.date));
    }, [allTasks]);

    const currentMonthTasks = useMemo(() => {
        return monthData.filter(t => {
            const d = new Date(t.date);
            return d.getFullYear() === currentMonth.year && d.getMonth() + 1 === currentMonth.month;
        });
    }, [monthData, currentMonth]);

    const selectedDay = useMemo(() => {
        if (!selectedDate) return null;
        const d = new Date(selectedDate);
        if (d.getFullYear() === currentMonth.year && d.getMonth() + 1 === currentMonth.month) {
            return monthData.find(t => t.date === selectedDate) || null;
        }
        return null;
    }, [monthData, selectedDate, currentMonth]);

    const totalStats = useMemo(() => {
        const total = allTasks.length;
        const completed = allTasks.filter(t => t.completed).length;
        const totalMinutes = allTasks.reduce((sum, t) => sum + t.duration_min, 0);
        return { total, completed, pct: total ? Math.round((completed / total) * 100) : 0, totalMinutes };
    }, [allTasks]);

    const weekDays = ['一', '二', '三', '四', '五', '六', '日'];

    const getMonthFirstDayOffset = () => {
        const firstDay = new Date(currentMonth.year, currentMonth.month - 1, 1);
        const dayOfWeek = firstDay.getDay();
        return dayOfWeek === 0 ? 6 : dayOfWeek - 1;
    };

    const getMonthDays = () => {
        const daysInMonth = new Date(currentMonth.year, currentMonth.month, 0).getDate();
        return Array.from({ length: daysInMonth }, (_, i) => i + 1);
    };

    const prevMonth = () => {
        if (currentMonth.month === 1) {
            setCurrentMonth({ year: currentMonth.year - 1, month: 12 });
        } else {
            setCurrentMonth({ year: currentMonth.year, month: currentMonth.month - 1 });
        }
    };

    const nextMonth = () => {
        if (currentMonth.month === 12) {
            setCurrentMonth({ year: currentMonth.year + 1, month: 1 });
        } else {
            setCurrentMonth({ year: currentMonth.year, month: currentMonth.month + 1 });
        }
    };

    const handleTaskClick = async (task: PlanItem) => {
        if (!user) return;
        try {
            const res = await startLesson(user.id, task.node_id);
            navigate(`/cabin/${res.lesson_id}`);
        } catch (e) {
            message.error("无法开始学习");
        }
    };

    const formatDateRange = () => {
        if (dateRange.start && dateRange.end) {
            return `${dateRange.start} ~ ${dateRange.end}`;
        }
        return '待生成';
    };

    return (
        <div className="flex flex-col h-full bg-gradient-to-b from-slate-50 to-white">
            <div className="px-6 pt-4 pb-3 border-b border-slate-100 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
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

            <div className="flex-1 overflow-auto p-4">
                {loading ? (
                    <div className="flex justify-center items-center h-48"><Spin size="large" /></div>
                ) : (
                    <div className="max-w-4xl mx-auto space-y-4">
                        <div className="grid grid-cols-3 gap-3">
                            <Card size="small" className="rounded-xl text-center shadow-sm">
                                <AimOutlined className="text-blue-500 text-xl mb-1" />
                                <div className="text-xs text-slate-500">目标考期</div>
                                <div className="text-sm font-bold text-slate-800">{formatDateRange()}</div>
                            </Card>
                            <Card size="small" className="rounded-xl text-center shadow-sm">
                                <ClockCircleOutlined className="text-green-500 text-xl mb-1" />
                                <div className="text-xs text-slate-500">总学习时长</div>
                                <div className="text-sm font-bold text-slate-800">{totalStats.totalMinutes} 分钟</div>
                            </Card>
                            <Card size="small" className="rounded-xl text-center shadow-sm">
                                <CalendarOutlined className="text-purple-500 text-xl mb-1" />
                                <div className="text-xs text-slate-500">总进度</div>
                                <Progress
                                    percent={totalStats.pct}
                                    size="small"
                                    strokeColor={{ '0%': '#3b82f6', '100%': '#22c55e' }}
                                />
                            </Card>
                        </div>

                        <Card className="rounded-xl shadow-sm border-0">
                            <div className="flex items-center justify-between mb-4">
                                <Button icon={<LeftOutlined />} onClick={prevMonth} size="small" />
                                <h3 className="text-base font-semibold text-slate-700">
                                    {currentMonth.year} 年 {currentMonth.month} 月
                                </h3>
                                <Button icon={<RightOutlined />} onClick={nextMonth} size="small" />
                            </div>

                            <div className="flex items-center gap-2 text-xs text-slate-500 mb-3">
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-100 border border-green-200" /> 已完成</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-50 border border-blue-200" /> 待完成</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-100 border border-slate-200" /> 无任务</span>
                            </div>

                            <div className="grid grid-cols-7 gap-1 mb-1">
                                {weekDays.map(d => (
                                    <div key={d} className="text-center text-xs text-slate-400 font-medium py-2">{d}</div>
                                ))}
                            </div>

                            <div className="grid grid-cols-7 gap-1">
                                {Array.from({ length: getMonthFirstDayOffset() }).map((_, i) => (
                                    <div key={`empty-${i}`} className="aspect-square" />
                                ))}
                                {getMonthDays().map(day => {
                                    const dateStr = `${currentMonth.year}-${String(currentMonth.month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                                    const task = currentMonthTasks.find(t => t.date === dateStr);
                                    const isSelected = selectedDate === dateStr;
                                    const completed = task ? task.tasks.filter(t => t.completed).length : 0;
                                    const total = task ? task.tasks.length : 0;
                                    
                                    let bgColor = 'bg-slate-50 hover:bg-slate-100';
                                    if (total > 0) {
                                        if (completed === total) bgColor = 'bg-green-100 text-green-800 hover:bg-green-200';
                                        else if (completed > 0) bgColor = 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200';
                                        else bgColor = 'bg-blue-50 text-blue-700 hover:bg-blue-100';
                                    }
                                    
                                    return (
                                        <button
                                            key={day}
                                            onClick={() => total > 0 && setSelectedDate(dateStr)}
                                            disabled={total === 0}
                                            className={`
                                                aspect-square rounded-lg flex flex-col items-center justify-center text-sm font-medium transition-all
                                                ${bgColor} ${isSelected ? 'ring-2 ring-blue-500 scale-105 shadow-md' : 'hover:shadow-sm'}
                                                ${total === 0 ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                                            `}
                                        >
                                            <span>{day}</span>
                                            {total > 0 && <span className="text-[10px]">{completed}/{total}</span>}
                                        </button>
                                    );
                                })}
                            </div>
                        </Card>

                        <Card className="rounded-xl shadow-sm border-0">
                            {selectedDay ? (
                                <>
                                    <h3 className="text-base font-semibold text-slate-700 mb-3 flex items-center gap-2">
                                        📋 {selectedDay.date} 的任务
                                        <Tag color="blue" className="rounded-full text-xs">
                                            {selectedDay.tasks.filter(t => t.completed).length}/{selectedDay.tasks.length}
                                        </Tag>
                                    </h3>
                                    {selectedDay.tasks.length === 0 ? (
                                        <Alert type="info" showIcon message="此日为空闲日，没有安排任务" />
                                    ) : (
                                        <div className="space-y-2">
                                            {selectedDay.tasks.map(task => {
                                                const style = TASK_STYLE[task.type];
                                                return (
                                                    <div
                                                        key={task.id}
                                                        onClick={() => !task.completed && handleTaskClick(task)}
                                                        className={`
                                                            flex items-center justify-between p-4 rounded-xl border-2 transition-all
                                                            ${style.color}
                                                            ${task.completed 
                                                                ? 'opacity-60 cursor-default' 
                                                                : 'cursor-pointer hover:shadow-lg hover:scale-[1.02] active:scale-[0.98] border-transparent hover:border-blue-300'}
                                                        `}
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <span className="text-2xl">{style.icon}</span>
                                                            <div>
                                                                <p className={`text-sm font-medium ${task.completed ? 'line-through text-slate-400' : 'text-slate-800'}`}>
                                                                    {task.title}
                                                                </p>
                                                                <div className="flex items-center gap-2 mt-1">
                                                                    <span className="text-xs text-slate-400">⏱️ {task.duration_min} 分钟</span>
                                                                    {!task.completed && <span className="text-xs text-blue-500 font-medium">点击开始 →</span>}
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <Tag color={task.completed ? 'green' : style.tagColor} className="rounded-full">
                                                            {task.completed ? '✅ 已完成' : '待完成'}
                                                        </Tag>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="text-center text-slate-400 py-8">
                                    👆 选择日历中有任务的日期查看详情
                                </div>
                            )}
                        </Card>
                    </div>
                )}
            </div>
        </div>
    );
};

export default StudyPlan;
