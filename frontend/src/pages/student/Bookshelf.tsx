import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Progress, Button, Spin, Alert, Empty, Modal, Input, message, Upload, Tag } from 'antd';
import { PlusOutlined, BookOutlined, ApartmentOutlined, NodeIndexOutlined, InboxOutlined, DeleteOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useBookshelfStore } from '../../stores/useBookshelfStore';
import { getBookshelf, activateBook } from '../../api/students';
import { createMaterial, uploadMaterialPdf, deleteMaterial } from '../../api/materials';
import type { BookshelfItem } from '../../types/student';


const PROCESSING_STATES = new Set(['pending', 'processing']);

function BookCard({
    book,
    onGoOutline,
    onGoForest,
    onActivate,
    onDelete,
    activating,
}: {
    book: BookshelfItem;
    onGoOutline: (materialId: string) => void;
    onGoForest: (materialId: string) => void;
    onActivate: (materialId: string) => void;
    onDelete: (materialId: string, title: string) => void;
    activating: boolean;
}) {
    const healthColor = book.health_score > 85 ? '#22c55e' : book.health_score >= 60 ? '#eab308' : '#ef4444';
    const isActive = book.is_activated;
    const isProcessing = PROCESSING_STATES.has(book.processing_status || '');
    const isFailed = book.processing_status === 'failed';

    return (
        <Card
            hoverable
            className={`rounded-xl transition-all hover:shadow-lg ${!isActive && !isProcessing ? 'border-dashed border-slate-300' : ''}`}
            styles={{ body: { padding: '20px' } }}
        >
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={`w-12 h-16 rounded-lg flex items-center justify-center shadow-sm ${isActive
                        ? 'bg-gradient-to-b from-blue-400 to-blue-600'
                        : 'bg-gradient-to-b from-slate-300 to-slate-400'
                        }`}>
                        <BookOutlined className="text-white text-xl" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-slate-800 leading-tight">{book.material_title}</h3>
                        <p className="text-xs text-slate-400 mt-1">
                            {book.grade && book.subject
                                ? `${book.grade} · ${book.subject}`
                                : '教材'}
                            {book.node_count > 0 && ` · ${book.node_count} 个知识节点`}
                        </p>
                    </div>
                </div>
                {isProcessing && (
                    <Tag icon={<LoadingOutlined spin />} color="processing">解析中</Tag>
                )}
                {isFailed && (
                    <Tag icon={<CloseCircleOutlined />} color="error">构建失败</Tag>
                )}
                {isActive && !isProcessing && !isFailed && (
                    <div className="text-center">
                        <Progress
                            type="circle"
                            percent={book.health_score}
                            size={48}
                            strokeColor={healthColor}
                            format={(pct) => <span className="text-xs font-bold">{pct}</span>}
                        />
                        <div className="text-[10px] text-slate-400 mt-0.5">健康度</div>
                    </div>
                )}
                {!isActive && !isProcessing && !isFailed && (
                    <span className="px-2 py-0.5 text-[10px] rounded bg-slate-100 text-slate-500">未激活</span>
                )}
            </div>

            {isActive && !isProcessing && !isFailed && (
                <div className="mb-4">
                    <div className="flex justify-between text-xs text-slate-500 mb-1">
                        <span>学习进度</span>
                        <span className="font-medium text-slate-700">{book.progress_pct}%</span>
                    </div>
                    <Progress
                        percent={book.progress_pct}
                        showInfo={false}
                        strokeColor={{ '0%': '#3b82f6', '100%': '#22c55e' }}
                        className="mb-0"
                    />
                </div>
            )}

            <div className="flex gap-2 items-center">
                {isProcessing ? (
                    <span className="text-xs text-blue-500 flex-1">正在后台构建知识树，请稍候...</span>
                ) : isFailed ? (
                    <span className="text-xs text-red-500 flex-1">知识树构建失败，可删除后重试</span>
                ) : isActive ? (
                    <>
                        <Button
                            type="primary"
                            icon={<ApartmentOutlined />}
                            className="rounded-lg flex-1"
                            onClick={() => onGoOutline(book.material_id)}
                        >
                            课程大纲
                        </Button>
                        <Button
                            icon={<NodeIndexOutlined />}
                            className="rounded-lg flex-1"
                            onClick={() => onGoForest(book.material_id)}
                        >
                            知识书林
                        </Button>
                    </>
                ) : (
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        className="rounded-lg flex-1"
                        onClick={() => onActivate(book.material_id)}
                        loading={activating}
                    >
                        加入我的书架
                    </Button>
                )}
                <Button
                    danger
                    icon={<DeleteOutlined />}
                    size="small"
                    onClick={(e) => { e.stopPropagation(); onDelete(book.material_id, book.material_title); }}
                />
            </div>
        </Card>
    );
}

const Bookshelf: React.FC = () => {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const { books, isLoading, setBooks, setLoading, setCurrentMaterial } = useBookshelfStore();
    const [error, setError] = useState<string | null>(null);
    const [addModalOpen, setAddModalOpen] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [activatingId, setActivatingId] = useState<string | null>(null);
    const [formData, setFormData] = useState({ title: '', grade: '', subject: '', version: '' });
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const reloadBookshelf = useCallback(async () => {
        if (!user?.id) return;
        try {
            const data: any = await getBookshelf(user.id);
            setBooks(data.books || data.data?.books || []);
        } catch { /* 静默 */ }
    }, [user?.id, setBooks]);

    // Auto-poll while any book is processing
    useEffect(() => {
        const hasProcessing = books.some(b => PROCESSING_STATES.has(b.processing_status || ''));
        if (!hasProcessing) {
            if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null; }
            return;
        }

        const completed = books.find(b => b.processing_status === 'completed');
        const failed = books.find(b => b.processing_status === 'failed');

        if (completed) message.success('知识树构建完成！');
        if (failed) message.error('知识树构建失败，可删除后重试');

        pollRef.current = setTimeout(reloadBookshelf, 30000);
        return () => { if (pollRef.current) clearTimeout(pollRef.current); };
    }, [books, reloadBookshelf]);

    const handleActivateBook = async (materialId: string) => {
        if (!user?.id) return;
        setActivatingId(materialId);
        try {
            await activateBook(user.id, materialId);
            message.success('教材已加入书架！');
            await reloadBookshelf();
        } catch (e: any) {
            message.error(e.response?.data?.detail || '激活失败');
        } finally {
            setActivatingId(null);
        }
    };

    const handleAddMaterial = async () => {
        if (!formData.title || !formData.grade || !formData.subject || !formData.version || !selectedFile) {
            message.warning('请填写完整信息并上传教材 PDF');
            return;
        }

        try {
            setSubmitting(true);

            const materialRes = await createMaterial(formData);
            const materialId = (materialRes as any).id || (materialRes as any).data?.id;

            if (!materialId) {
                throw new Error("未能获取教材 ID");
            }

            await uploadMaterialPdf(materialId, selectedFile);

            message.success('PDF 已上传，知识树正在后台构建中');
            setAddModalOpen(false);
            setFormData({ title: '', grade: '', subject: '', version: '最新版' });
            setSelectedFile(null);

            await reloadBookshelf();
        } catch (e: any) {
            console.error('Add material error:', e);
            message.error(e.response?.data?.detail || e.message || '添加教材失败');
        } finally {
            setSubmitting(false);
        }
    };

    useEffect(() => {
        if (!user?.id) return;
        setLoading(true);
        getBookshelf(user.id)
            .then((data: any) => {
                setBooks(data.books || []);
                setError(null);
            })
            .catch((e) => {
                setError(e.response?.data?.detail || '无法获取书架数据');
            })
            .finally(() => setLoading(false));
    }, [user?.id, setBooks, setLoading]);

    const handleGoOutline = (materialId: string) => {
        setCurrentMaterial(materialId);
        navigate(`/outline/${materialId}`);
    };
    const handleGoForest = (materialId: string) => {
        setCurrentMaterial(materialId);
        navigate(`/forest/${materialId}`);
    };

    const handleDelete = (materialId: string, title: string) => {
        Modal.confirm({
            title: '确认删除',
            content: `确定要删除教材「${title}」吗？所有知识节点和学习数据将被清除，此操作不可撤销。`,
            okText: '删除',
            okType: 'danger',
            cancelText: '取消',
            onOk: async () => {
                try {
                    await deleteMaterial(materialId);
                    message.success('教材已删除');
                    await reloadBookshelf();
                } catch (e: any) {
                    message.error(e.response?.data?.detail || '删除失败');
                }
            },
        });
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Spin size="large" tip="加载书架…" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            <div className="px-6 pt-4 pb-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-slate-800">📚 统一书架</h1>
                    <p className="text-sm text-slate-500 mt-1">共 {books.length} 本教材</p>
                </div>
                <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setAddModalOpen(true)}
                    className="rounded-lg"
                >
                    添加教材
                </Button>
            </div>

            {error && (
                <div className="mx-6 mt-3">
                    <Alert type="info" showIcon message={error} closable />
                </div>
            )}

            <div className="flex-1 overflow-auto px-6 py-4">
                {books.length === 0 ? (
                    <Empty description="还没有添加教材，点击上方按钮开始吧！" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {books.map((book) => (
                            <BookCard
                                key={book.material_id}
                                book={book}
                                onGoOutline={handleGoOutline}
                                onGoForest={handleGoForest}
                                onActivate={handleActivateBook}
                                onDelete={handleDelete}
                                activating={activatingId === book.material_id}
                            />
                        ))}
                    </div>
                )}
            </div>

            <Modal
                title="添加教材"
                open={addModalOpen}
                onCancel={() => {
                    if (!submitting) {
                        setAddModalOpen(false);
                        setFormData({ title: '', grade: '', subject: '', version: '' });
                        setSelectedFile(null);
                    }
                }}
                onOk={handleAddMaterial}
                okText="确认添加"
                cancelText="取消"
                confirmLoading={submitting}
                maskClosable={!submitting}
                closable={!submitting}
            >
                <p className="text-sm text-slate-500 mb-4">输入教材信息并上传 PDF 将其加入你的书架</p>
                <Input
                    placeholder="教材名称"
                    className="mb-3"
                    value={formData.title}
                    onChange={e => setFormData(p => ({ ...p, title: e.target.value }))}
                    disabled={submitting}
                />
                <Input
                    placeholder="年级"
                    className="mb-3"
                    value={formData.grade}
                    onChange={e => setFormData(p => ({ ...p, grade: e.target.value }))}
                    disabled={submitting}
                />
                <Input
                    placeholder="科目 (例如: 语文, 数学)"
                    className="mb-4"
                    value={formData.subject}
                    onChange={e => setFormData(p => ({ ...p, subject: e.target.value }))}
                    disabled={submitting}
                />
                <Input
                    placeholder="版本 (例如: 2024年版，人教版...)"
                    className="mb-4"
                    value={formData.version}
                    onChange={e => setFormData(p => ({ ...p, version: e.target.value }))}
                    disabled={submitting}
                />

                <Upload.Dragger
                    name="file"
                    multiple={false}
                    beforeUpload={file => {
                        setSelectedFile(file);
                        return false;
                    }}
                    onRemove={() => setSelectedFile(null)}
                    fileList={selectedFile ? [selectedFile as any] : []}
                    disabled={submitting}
                    maxCount={1}
                >
                    <p className="ant-upload-drag-icon">
                        <InboxOutlined />
                    </p>
                    <p className="ant-upload-text">点击或将 PDF 拖拽到此区域上传</p>
                    <p className="ant-upload-hint">支持单个 PDF 文件上传，后台会自动提取章节大纲</p>
                </Upload.Dragger>
            </Modal>
        </div>
    );
};

export default Bookshelf;
