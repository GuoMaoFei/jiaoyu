import React, { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Tag, Progress, Breadcrumb, Alert, message, Spin, Modal, Select, Dropdown } from 'antd';
import { ReloadOutlined, CalendarOutlined, AimOutlined, ClockCircleOutlined, LeftOutlined, RightOutlined, DeleteOutlined, DownOutlined } from '@ant-design/icons';
import { getStudyPlans, generateStudyPlan, clearStudyPlans, startLesson } from '../../api/lessons';
import { getBookshelf } from '../../api/students';
import { useAuthStore } from '../../stores/useAuthStore';
import { useLessonStore } from '../../stores/useLessonStore';
import type { PlanItem, TaskType } from '../../types/lesson';
import type { BookshelfItem } from '../../types/student';

const TASK_STYLE: Record<TaskType, { color: string; icon: string; tagColor: string }> = {
    LEARN_NEW: { color: 'border-blue-200 bg-blue-50/50', icon: '📖', tagColor: 'blue' },
    DO_QUIZ: { color: 'border-orange-200 bg-orange-50/50', icon: '📝', tagColor: 'orange' },
    REVIEW_VARIANT: { color: 'border-red-200 bg-red-50/50', icon: '🔄', tagColor: 'red' },
};

const SUBJECT_COLORS = [
    { bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-700', dot: 'bg-blue-500' },
    { bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-700', dot: 'bg-green-500' },
    { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-700', dot: 'bg-purple-500' },
    { bg: 'bg-orange-100', border: 'border-orange-300', text: 'text-orange-700', dot: 'bg-orange-500' },
    { bg: 'bg-pink-100', border: 'border-pink-300', text: 'text-pink-700', dot: 'bg-pink-500' },
    { bg: 'bg-cyan-100', border: 'border-cyan-300', text: 'text-cyan-700', dot: 'bg-cyan-500' },
];

const getSubjectColor = (index: number) => SUBJECT_COLORS[index % SUBJECT_COLORS.length];

const StudyPlan: React.FC = () => {
    const { materialId: _materialIdParam } = useParams<{ materialId: string }>();
    // materialId kept for potential future use, currently using selectedMaterialForGenerate
    const { user } = useAuthStore();
    const navigate = useNavigate();
    
    const [allTasks, setAllTasks] = useState<PlanItem[]>([]);
    const [bookshelf, setBookshelf] = useState<BookshelfItem[]>([]);
    const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null);
    const [selectedMaterialForGenerate, setSelectedMaterialForGenerate] = useState<string | null>(null);
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [currentMonth, setCurrentMonth] = useState(() => {
        const now = new Date();
        return { year: now.getFullYear(), month: now.getMonth() + 1 };
    });
    const [dateRange, setDateRange] = useState<{ start?: string; end?: string }>({});

    const materials = useMemo(() => {
        return bookshelf.map((item, index) => ({
            material_id: item.material_id,
            subject: item.subject,
            colorIndex: index,
        }));
    }, [bookshelf]);

    const materialColorMap = useMemo(() => {
        const map = new Map<string, number>();
        materials.forEach((m, i) => map.set(m.material_id, i));
        return map;
    }, [materials]);

    const filteredTasks = useMemo(() => {
        if (!selectedMaterialId) return allTasks;
        return allTasks.filter(t => t.material_id === selectedMaterialId);
    }, [allTasks, selectedMaterialId]);

    const loadPlans = async () => {
        if (!user) return;
        setLoading(true);
        try {
            const [plansData, bookshelfData] = await Promise.all([
                getStudyPlans(user.id),
                getBookshelf(user.id),
            ]);
            setAllTasks(plansData.items);
            setBookshelf(bookshelfData.books);
            setDateRange({ start: plansData.start_date, end: plansData.end_date });
            
            if (plansData.items.length > 0) {
                const firstDate = new Date(plansData.items[0].date);
                setCurrentMonth({ year: firstDate.getFullYear(), month: firstDate.getMonth() + 1 });
            }
            
            const today = new Date().toISOString().split('T')[0];
            const todayTask = plansData.items.find(t => t.date === today);
            if (todayTask) {
                setSelectedDate(today);
            } else if (plansData.items.length > 0) {
                setSelectedDate(plansData.items[0].date);
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
        const targetMaterialId = selectedMaterialForGenerate || selectedMaterialId;
        if (!targetMaterialId) {
            message.warning('请先选择要生成计划的教材');
            return;
        }
        setGenerating(true);
        try {
            await clearStudyPlans(user.id, targetMaterialId);
            const today = new Date().toISOString().split('T')[0];
            await generateStudyPlan(user.id, targetMaterialId, today);
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
            content: selectedMaterialId 
                ? `将重新生成「${materials.find(m => m.material_id === selectedMaterialId)?.subject}」的学习计划。`
                : 'Planner Agent 将会根据您目前的知识掌握情况动态更新接下来的学习计划。',
            onOk: handleGenerate,
            okText: '确认生成',
            cancelText: '取消'
        });
    }

    const handleDeleteMaterialPlan = (materialIdToDelete: string) => {
        if (!user) return;
        const materialInfo = materials.find(m => m.material_id === materialIdToDelete);
        Modal.confirm({
            title: '删除教材计划',
            content: `确定要删除「${materialInfo?.subject}」的学习计划吗？此操作不可恢复。`,
            okText: '确认删除',
            okButtonProps: { danger: true },
            cancelText: '取消',
            onOk: async () => {
                try {
                    await clearStudyPlans(user.id, materialIdToDelete);
                    message.success('计划已删除');
                    loadPlans();
                } catch (e) {
                    message.error('删除失败');
                }
            }
        });
    };

    const monthData = useMemo(() => {
        const daysMap = new Map<string, PlanItem[]>();
        filteredTasks.forEach(item => {
            if (!daysMap.has(item.date)) {
                daysMap.set(item.date, []);
            }
            daysMap.get(item.date)!.push(item);
        });
        return Array.from(daysMap.entries())
            .map(([date, tasks]) => ({ date, tasks }))
            .sort((a, b) => a.date.localeCompare(b.date));
    }, [filteredTasks]);

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
        const total = filteredTasks.length;
        const completed = filteredTasks.filter(t => t.completed).length;
        const totalMinutes = filteredTasks.reduce((sum, t) => sum + t.duration_min, 0);
        return { total, completed, pct: total ? Math.round((completed / total) * 100) : 0, totalMinutes };
    }, [filteredTasks]);

    const materialStats = useMemo(() => {
        const stats = new Map<string, { subject: string; total: number; completed: number; colorIndex: number }>();
        allTasks.forEach(t => {
            if (!t.material_id || !t.subject) return;
            const existing = stats.get(t.material_id);
            if (existing) {
                existing.total++;
                if (t.completed) existing.completed++;
            } else {
                stats.set(t.material_id, {
                    subject: t.subject,
                    total: 1,
                    completed: t.completed ? 1 : 0,
                    colorIndex: stats.size,
                });
            }
        });
        return Array.from(stats.entries()).map(([material_id, data]) => ({
            material_id,
            ...data,
            pct: data.total ? Math.round((data.completed / data.total) * 100) : 0,
        }));
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
            // 设置 lesson store 状态
            useLessonStore.getState().setLesson(res);
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
                    <div className="flex items-center gap-2">
                        {materials.length > 0 && (
                            <Dropdown
                                menu={{
                                    items: materials.map(m => ({
                                        key: m.material_id,
                                        label: (
                                            <div className="flex items-center justify-between gap-4">
                                                <span>{m.subject}</span>
                                                <DeleteOutlined 
                                                    className="text-red-400 hover:text-red-600"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDeleteMaterialPlan(m.material_id);
                                                    }}
                                                />
                                            </div>
                                        ),
                                    })),
                                }}
                            >
                                <Button size="small" className="rounded-lg">
                                    管理计划 <DownOutlined />
                                </Button>
                            </Dropdown>
                        )}
                        </div>
                    <div className="flex items-center gap-2">
                        {materials.length > 0 && (
                            <Select
                                value={selectedMaterialForGenerate}
                                onChange={setSelectedMaterialForGenerate}
                                allowClear
                                placeholder="选择教材生成计划"
                                className="w-40"
                                options={materials.map(m => ({
                                    value: m.material_id,
                                    label: (
                                        <div className="flex items-center gap-2">
                                            <span className={`w-2 h-2 rounded-full ${getSubjectColor(m.colorIndex).dot}`} />
                                            <span>{m.subject}</span>
                                        </div>
                                    ),
                                }))}
                            />
                        )}
                        <Button
                            icon={<ReloadOutlined />}
                            type="primary"
                            ghost
                            className="rounded-lg"
                            loading={generating}
                            onClick={confirmGenerate}
                        >
                            {selectedMaterialForGenerate ? '重新规划当前' : '重新规划'}
                        </Button>
                    </div>
                </div>
                {materials.length > 1 && (
                    <div className="mt-3 flex items-center gap-2">
                        <span className="text-sm text-slate-500">筛选教材：</span>
                        <Select
                            value={selectedMaterialId}
                            onChange={setSelectedMaterialId}
                            allowClear
                            placeholder="全部教材"
                            className="w-48"
                            options={materials.map(m => ({
                                value: m.material_id,
                                label: (
                                    <div className="flex items-center gap-2">
                                        <span className={`w-2 h-2 rounded-full ${getSubjectColor(m.colorIndex).dot}`} />
                                        {m.subject}
                                    </div>
                                ),
                            }))}
                        />
                    </div>
                )}
            </div>

            <div className="flex-1 overflow-auto p-4">
                {loading ? (
                    <div className="flex justify-center items-center h-48"><Spin size="large" /></div>
                ) : filteredTasks.length === 0 ? (
                    <div className="max-w-4xl mx-auto">
                        <Card className="rounded-xl shadow-sm border-0">
                            <div className="text-center py-12">
                                <CalendarOutlined className="text-6xl text-slate-300 mb-4" />
                                <h3 className="text-lg font-semibold text-slate-600 mb-2">
                                    {selectedMaterialId ? '当前教材暂无学习计划' : '暂无学习计划'}
                                </h3>
                                <p className="text-slate-400 mb-6">
                                    点击下方按钮，Planner Agent 将为您生成个性化的学习计划
                                </p>
                                <Button
                                    type="primary"
                                    size="large"
                                    icon={<ReloadOutlined />}
                                    onClick={confirmGenerate}
                                    loading={generating}
                                    className="rounded-lg"
                                >
                                    生成学习计划
                                </Button>
                            </div>
                        </Card>
                    </div>
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
                                                const colorIdx = task.material_id ? (materialColorMap.get(task.material_id) ?? 0) : 0;
                                                const subjectColor = getSubjectColor(colorIdx);
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
                                                                    {task.subject && (
                                                                        <span className={`text-xs px-2 py-0.5 rounded-full ${subjectColor.bg} ${subjectColor.text}`}>
                                                                            {task.subject}
                                                                        </span>
                                                                    )}
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

                        {materialStats.length > 0 && (
                            <Card className="rounded-xl shadow-sm border-0" title={
                                <span className="text-base font-semibold text-slate-700">📚 教材计划概览</span>
                            }>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {materialStats.map(stat => {
                                        const color = getSubjectColor(stat.colorIndex);
                                        return (
                                            <div
                                                key={stat.material_id}
                                                className={`p-3 rounded-xl ${color.bg} border ${color.border}`}
                                            >
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className={`w-3 h-3 rounded-full ${color.dot}`} />
                                                        <span className={`font-medium ${color.text}`}>{stat.subject}</span>
                                                    </div>
                                                    <span className={`text-sm ${color.text}`}>
                                                        {stat.completed}/{stat.total} 完成
                                                    </span>
                                                </div>
                                                <Progress
                                                    percent={stat.pct}
                                                    size="small"
                                                    strokeColor={stat.pct === 100 ? '#22c55e' : '#3b82f6'}
                                                    showInfo={false}
                                                />
                                                <div className="flex justify-between mt-1 text-xs text-slate-500">
                                                    <span>进度 {stat.pct}%</span>
                                                    <span
                                                        className="cursor-pointer hover:text-blue-500"
                                                        onClick={() => handleDeleteMaterialPlan(stat.material_id)}
                                                    >
                                                        🗑️ 删除
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </Card>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default StudyPlan;
