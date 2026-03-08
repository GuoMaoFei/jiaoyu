import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Spin, Button, Alert, Card } from 'antd';
import { PrinterOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { generateReport } from '../../api/reports';
import { useAuthStore } from '../../stores/useAuthStore';



const ParentReport: React.FC = () => {
    const { materialId: materialIdParam } = useParams<{ materialId: string }>();
    const materialId = materialIdParam || "test_material_id_123";
    const user = useAuthStore((s) => s.user);
    const [reportMd, setReportMd] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchReport = async () => {
        if (!user?.id) return;
        setLoading(true);
        try {
            const res: any = await generateReport(user.id, materialId);
            setReportMd(res.report_md || '生成空报告');
            setError(null);
        } catch {
            setReportMd('生成报告失败，请检查网络或后端状态。');
            setError('后端接口报错');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReport();
    }, [user?.id]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Spin size="large" tip="生成学情周报…" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* 顶部 */}
            <div className="px-6 pt-4 pb-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-slate-800">📊 学情周报</h1>
                    <p className="text-sm text-slate-500 mt-1">由 AI 学情观察员自动生成</p>
                </div>
                <div className="flex gap-2">
                    <Button icon={<ReloadOutlined />} onClick={fetchReport} className="rounded-lg">
                        重新生成
                    </Button>
                    <Button icon={<PrinterOutlined />} type="primary" className="rounded-lg">
                        打印 / 分享
                    </Button>
                </div>
            </div>

            {error && (
                <div className="mx-6 mt-3">
                    <Alert type="info" showIcon message={error} closable />
                </div>
            )}

            {/* 报告正文 */}
            <div className="flex-1 overflow-auto px-6 py-6">
                <Card className="rounded-xl max-w-4xl mx-auto shadow-sm">
                    <div className="prose prose-slate max-w-none
            prose-h1:text-2xl prose-h1:font-bold prose-h1:text-slate-800
            prose-h2:text-lg prose-h2:font-semibold prose-h2:text-slate-700 prose-h2:border-b prose-h2:pb-2
            prose-table:text-sm prose-th:bg-slate-50
            prose-li:text-sm prose-p:text-sm
            prose-strong:text-slate-800
            prose-hr:border-slate-200
          ">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {reportMd}
                        </ReactMarkdown>
                    </div>
                </Card>
            </div>
        </div>
    );
};

export default ParentReport;
