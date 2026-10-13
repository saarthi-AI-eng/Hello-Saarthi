import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import './AppShell.css';

export default function AppShell() {
    return (
        <div className="app-shell">
            <Sidebar />
            <div className="app-main">
                <Topbar />
                <main className="app-content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
