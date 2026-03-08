import React from 'react';
import { Layout as AntLayout, Menu, Dropdown, Avatar } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
    BookOutlined,
    CalendarOutlined,
    UserOutlined,
    LogoutOutlined,
    MenuFoldOutlined,
    MenuUnfoldOutlined,
    ApartmentOutlined,
    NodeIndexOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useBookshelfStore } from '../../stores/useBookshelfStore';
import { getBookshelf } from '../../api/students';

const { Header, Content, Sider } = AntLayout;

const MainLayout: React.FC = () => {
    const [collapsed, setCollapsed] = React.useState(false);
    const navigate = useNavigate();
    const location = useLocation();
    const { user, logout } = useAuthStore();
    const { currentMaterialId, setBooks, books } = useBookshelfStore();

    // Globally load bookshelf once to ensure currentMaterialId is set for navigation
    React.useEffect(() => {
        if (user?.id && books.length === 0) {
            getBookshelf(user.id)
                .then((data: any) => {
                    if (data.books && data.books.length > 0) {
                        setBooks(data.books);
                    }
                })
                .catch(() => { /* silent */ });
        }
    }, [user?.id]);

    // Get current material ID from the globally active book
    const mId = currentMaterialId || 'demo';

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const menuItems = [
        { key: '/today', icon: <CalendarOutlined />, label: '今日任务' },
        { key: '/bookshelf', icon: <BookOutlined />, label: '统一书架' },
        { key: `/outline/${mId}`, icon: <ApartmentOutlined />, label: '课程大纲' },
        { key: `/forest/${mId}`, icon: <NodeIndexOutlined />, label: '知识书林' },
        { key: '/mistakes', icon: <NodeIndexOutlined />, label: '错题枢纽' },
        { key: `/plan/${mId}`, icon: <CalendarOutlined />, label: '学习计划' },
        { key: '/report', icon: <BookOutlined />, label: '学情周报' },
        { key: '/profile', icon: <UserOutlined />, label: '个人中心' },
    ];

    return (
        <AntLayout className="min-h-screen bg-slate-50">
            {/* 侧边栏 */}
            <Sider
                trigger={null}
                collapsible
                collapsed={collapsed}
                breakpoint="md"
                onBreakpoint={(broken) => setCollapsed(broken)}
                className="shadow-sm z-10"
                theme="light"
            >
                <div className="h-16 flex items-center justify-center p-4">
                    {/* Logo 区域 */}
                    <div className="w-8 h-8 rounded-lg bg-primary-500 flex items-center justify-center text-white font-bold text-xl mr-2">T</div>
                    {!collapsed && <span className="text-lg font-bold text-slate-800 whitespace-nowrap overflow-hidden transition-all duration-300">Tree Edu</span>}
                </div>

                <Menu
                    theme="light"
                    mode="inline"
                    selectedKeys={[location.pathname]}
                    items={menuItems}
                    onClick={({ key }) => navigate(key)}
                    className="border-r-0 mt-2"
                />
            </Sider>

            <AntLayout>
                {/* 顶栏 */}
                <Header className="bg-white px-4 flex items-center justify-between shadow-sm z-0">
                    <div
                        className="cursor-pointer text-lg hover:text-primary-500 transition-colors w-10 h-10 flex items-center justify-center rounded-md hover:bg-slate-100"
                        onClick={() => setCollapsed(!collapsed)}
                    >
                        {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                    </div>

                    <div className="flex flex-1 items-center px-4 breadcrumbs-portal" id="breadcrumbs-portal">
                        {/* 各子路由将通过 Portal 把面包屑传送到这里 */}
                    </div>

                    <div className="flex items-center">
                        <Dropdown
                            menu={{
                                items: [
                                    { key: 'profile', icon: <UserOutlined />, label: '当前身份: ' + user?.role },
                                    { type: 'divider' },
                                    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true, onClick: handleLogout },
                                ]
                            }}
                            placement="bottomRight"
                        >
                            <div className="flex items-center cursor-pointer hover:bg-slate-50 px-3 py-1 rounded-full transition-colors border border-transparent hover:border-slate-200">
                                <Avatar icon={<UserOutlined />} className="bg-primary-100 text-primary-600" />
                                <span className="ml-2 font-medium text-slate-700 hidden sm:block">{user?.name}</span>
                            </div>
                        </Dropdown>
                    </div>
                </Header>

                {/* 内容区 */}
                <Content className="m-4 md:m-6 mt-4">
                    <div className="bg-white rounded-xl shadow-sm min-h-[calc(100vh-112px)] relative overflow-hidden flex flex-col">
                        <Outlet />
                    </div>
                </Content>
            </AntLayout>
        </AntLayout>
    );
};

export default MainLayout;
